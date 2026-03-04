from sqlalchemy.orm import Session
from typing import Optional, Dict
from datetime import datetime
import logging

from app.core.config import settings
from app.models import Conversation, Message
from app.services.llm import llm_service
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)

# Initialize RAG service
rag_service = get_rag_service()


# At the top of chat_service.py, after imports
RAG_PROMPT_TEMPLATE = """Based on the following reference materials from your uploaded documents:

{context}

---

Question: {question}

Please answer using the information from these materials when relevant. If the materials don't fully cover the question, supplement with your general knowledge."""


def build_rag_enhanced_message(context: str, question: str) -> str:
    """Format user message with RAG context for the LLM."""
    return RAG_PROMPT_TEMPLATE.format(context=context, question=question)


def get_or_create_conversation(
    conversation_id: Optional[int],
    user_id: int,
    db: Session
) -> Conversation:
    """
    Get existing conversation or create a new one.
    
    Args:
        conversation_id: Optional existing conversation ID
        user_id: User who owns the conversation
        db: Database session
    
    Returns:
        Conversation object
    """
    if conversation_id:
        # Get existing conversation
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        ).first()
        
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found or doesn't belong to user")
        
        return conversation
    else:
        # Create new conversation
        conversation = Conversation(
            user_id=user_id,
            title="New Chat"
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation


def save_message(
    conversation_id: int,
    role: str,
    content: str,
    db: Session
) -> Message:
    """
    Save a message to the database.
    
    Args:
        conversation_id: Conversation this message belongs to
        role: 'user' or 'assistant'
        content: Message content
        db: Database session
    
    Returns:
        Created Message object
    """
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content
    )
    
    db.add(message)
    db.commit()
    db.refresh(message)
    
    # Update conversation's updated_at timestamp
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation:
        conversation.updated_at = datetime.utcnow()
        db.commit()
    
    return message


def load_conversation_history(
    conversation_id: int,
    db: Session
) -> list[dict[str, str]]:
    """
    Load recent messages from a conversation for LLM context.
    
    Returns messages in chronological order (oldest first),
    formatted as the role/content dicts that Ollama expects.
    
    Args:
        conversation_id: Conversation to load history from
        db: Database session
    
    Returns:
        List of {"role": "user"|"assistant", "content": "..."} dicts
    """
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(settings.MAX_HISTORY_MESSAGES)
        .all()
    )
    
    # Reverse to chronological order (oldest first)
    messages.reverse()
    
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]
    
    logger.info(f"📜 Loaded {len(history)} history messages for conversation {conversation_id}")
    
    return history


def process_chat_message(
    user_message: str,
    conversation_id: Optional[int],
    user_id: int,
    temperature: float,
    use_rag: bool,
    db: Session = None
) -> tuple[int, int, str, Optional[Dict]]:
    """
    Process a chat message with RAG integration.
    
    🆕 NEW: Integrates RAG context from user's uploaded documents
    
    Args:
        user_message: User's message content
        conversation_id: Optional existing conversation ID
        user_id: User making the request
        temperature: LLM temperature parameter
        use_rag: Whether to use RAG context from uploaded documents
        db: Database session
    
    Returns:
        Tuple of (conversation_id, message_id, assistant_response, rag_result)
    """
    # 1. Get or create conversation
    conversation = get_or_create_conversation(conversation_id, user_id, db)

    # 2. Load conversation history (before saving current message)
    history = load_conversation_history(conversation.id, db)
    
    # 2. Save user message
    save_message(
        conversation_id=conversation.id,
        role="user",
        content=user_message,
        db=db
    )
    
    # 🆕 3. Get RAG context (if applicable)
    rag_result = None
    enhanced_message = user_message
    
    if use_rag:
        try:
            logger.info(f"🔍 Checking for RAG context...")
            rag_context = rag_service.get_context(
                query=user_message,
                user_id=user_id
            )
            if rag_context:
                logger.info(f"✅ RAG context retrieved: {rag_context['chunks_count']} chunks from {len(rag_context['sources'])} documents")
                enhanced_message = build_rag_enhanced_message(
                    context=rag_context['context'],
                    question=user_message
                )
                rag_result = {
                    "sources": rag_context['sources'],
                    "chunks_count": rag_context['chunks_count'],
                    "detected_topic": rag_context['detected_topic']
                }
            else:
                logger.info(f"ℹ️  No RAG context (not programming-related or no matching docs)")
        except Exception as e:
            logger.warning(f"⚠️  RAG context retrieval failed: {e}")
    else:
        logger.info(f"⏭️  RAG skipped (toggle off)")
        # Continue without RAG if it fails - graceful degradation
    
    # 4. Get LLM response (with enhanced message if RAG was used)
    messages = history + [{"role": "user", "content": enhanced_message}]
    assistant_response = llm_service.chat(messages, temperature)
    
    # 5. Save assistant message
    assistant_msg = save_message(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_response,
        db=db
    )
    
    return conversation.id, assistant_msg.id, assistant_response, rag_result


async def process_chat_message_stream(
    user_message: str,
    conversation_id: Optional[int],
    user_id: int,
    temperature: float,
    use_rag: bool = True,   
    db: Session = None
):
    """
    Process a streaming chat message with RAG integration.
    
    🆕 NEW: Integrates RAG context from user's uploaded documents
    
    Args:
        user_message: User's message content
        conversation_id: Optional existing conversation ID
        user_id: User making the request
        temperature: LLM temperature parameter
        db: Database session
    
    Yields:
        Chunks of assistant response, then final metadata
    """
    # 1. Get or create conversation
    conversation = get_or_create_conversation(conversation_id, user_id, db)

    # 2. Load conversation history (before saving current message)
    history = load_conversation_history(conversation.id, db)
    
    # 3. Save user message
    save_message(
        conversation_id=conversation.id,
        role="user",
        content=user_message,
        db=db
    )
    
    # 🆕 3. Get RAG context (if applicable)
    rag_result = None
    enhanced_message = user_message
    
    if use_rag:
        try:
            logger.info(f"🔍 Checking for RAG context...")
            rag_context = rag_service.get_context(
                query=user_message,
                user_id=user_id
            )
            if rag_context:
                logger.info(f"✅ RAG context retrieved: {rag_context['chunks_count']} chunks")
                enhanced_message = f"""Based on your uploaded documents:

{rag_context['context']}

Question: {user_message}
"""
                rag_result = {
                    "sources": rag_context['sources'],
                    "chunks_count": rag_context['chunks_count'],
                    "detected_topic": rag_context['detected_topic']
                }
            else:
                logger.info(f"ℹ️  No RAG context")
        except Exception as e:
            logger.warning(f"⚠️  RAG context retrieval failed: {e}")
    else:
        logger.info(f"⏭️  RAG skipped (toggle off)")
        # Continue without RAG if it fails
    
    # 4. Stream LLM response and accumulate
    messages = history + [{"role": "user", "content": enhanced_message}]
    accumulated_response = ""
    
    async for chunk in llm_service.chat_stream(messages, temperature):
        accumulated_response += chunk
        yield {"type": "chunk", "content": chunk}  # Yield chunks
    
    # 5. Save complete assistant message
    assistant_msg = save_message(
        conversation_id=conversation.id,
        role="assistant",
        content=accumulated_response,
        db=db
    )
    
    # 6. Yield final metadata (conversation_id, message_id, and RAG sources)
    yield {
        "type": "done",
        "conversation_id": conversation.id,
        "message_id": assistant_msg.id,
        "rag_result": rag_result  # 🆕 NEW: Include RAG metadata
    }
