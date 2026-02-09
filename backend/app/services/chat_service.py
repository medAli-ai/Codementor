from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.models import User, Conversation, Message
from app.services.llm import llm_service


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


def process_chat_message(
    user_message: str,
    conversation_id: Optional[int],
    user_id: int,
    temperature: float,
    db: Session
) -> tuple[int, int, str]:
    """
    Process a chat message: save user message, get LLM response, save assistant message.
    
    Args:
        user_message: User's message content
        conversation_id: Optional existing conversation ID
        user_id: User making the request
        temperature: LLM temperature parameter
        db: Database session
    
    Returns:
        Tuple of (conversation_id, message_id, assistant_response)
    """
    # 1. Get or create conversation
    conversation = get_or_create_conversation(conversation_id, user_id, db)
    
    # 2. Save user message
    user_msg = save_message(
        conversation_id=conversation.id,
        role="user",
        content=user_message,
        db=db
    )
    
    # 3. Get LLM response
    messages = [{"role": "user", "content": user_message}]
    assistant_response = llm_service.chat(messages, temperature)
    
    # 4. Save assistant message
    assistant_msg = save_message(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_response,
        db=db
    )
    
    return conversation.id, assistant_msg.id, assistant_response


async def process_chat_message_stream(
    user_message: str,
    conversation_id: Optional[int],
    user_id: int,
    temperature: float,
    db: Session
):
    """
    Process a streaming chat message: save user message, stream LLM response, save assistant message.
    
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
    
    # 2. Save user message
    user_msg = save_message(
        conversation_id=conversation.id,
        role="user",
        content=user_message,
        db=db
    )
    
    # 3. Stream LLM response and accumulate
    messages = [{"role": "user", "content": user_message}]
    accumulated_response = ""
    
    async for chunk in llm_service.chat_stream(messages, temperature):
        accumulated_response += chunk
        yield {"type": "chunk", "content": chunk}  # Yield chunks
    
    # 4. Save complete assistant message
    assistant_msg = save_message(
        conversation_id=conversation.id,
        role="assistant",
        content=accumulated_response,
        db=db
    )
    
    # 5. Yield final metadata (conversation_id and message_id)
    yield {
        "type": "done",
        "conversation_id": conversation.id,
        "message_id": assistant_msg.id
    }