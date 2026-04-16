import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.conversation import Conversation, Message
from app.services.llm import llm_service
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)

END_OF_MESSAGE = "[END_OF_MESSAGE]"

rag_service = get_rag_service()

RAG_PROMPT_TEMPLATE = """Based on the following reference materials from your uploaded documents:

{context}

---

Question: {question}

Please answer using the information from these materials when relevant.
If the materials don't fully cover the question, supplement with your general knowledge."""

TITLE_PROMPT_TEMPLATE = """Generate a short title (4-6 words) for a conversation that starts with this message:
"{user_message}"
Reply with the title only. No quotes, no punctuation at the end."""


def count_tokens(text: str) -> int:
    return len(text) // 4


def condense_messages(messages: list[dict], system_prompt: str, max_tokens: int) -> list[dict]:
    system_tokens = count_tokens(system_prompt)

    def total_tokens(msgs):
        return system_tokens + sum(count_tokens(m["content"]) for m in msgs)

    original_count = len(messages)
    while total_tokens(messages) > max_tokens and len(messages) > 1:
        messages = messages[1:]

    dropped = original_count - len(messages)
    if dropped:
        logger.warning(
            f"⚠️ Context window: dropped {dropped} oldest message(s) "
            f"to fit within {max_tokens} tokens"
        )
    return messages


def build_rag_enhanced_message(context: str, question: str) -> str:
    return RAG_PROMPT_TEMPLATE.format(context=context, question=question)


def generate_conversation_title(user_message: str) -> str:
    try:
        prompt = TITLE_PROMPT_TEMPLATE.format(user_message=user_message[:200])
        title = llm_service.chat(messages=[{"role": "user", "content": prompt}], temperature=0.7)
        title = title.strip().strip("\"'").strip()
        title = title[:100]
        logger.info(f"✅ Generated title: '{title}'")
        return title
    except Exception as e:
        logger.warning(f"⚠️ Title generation failed: {e}")
        return "New Chat"


async def get_or_create_conversation(
    conversation_id: Optional[int], user_id: int, db: AsyncSession
) -> Conversation:
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found or doesn't belong to user")
        return conversation
    else:
        conversation = Conversation(user_id=user_id, title="New Chat")
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation


async def save_message(
    conversation_id: int,
    role: str,
    content: str,
    db: AsyncSession,
    sources: Optional[list] = None,
    rag_used: bool = False,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources=sources,
        rag_used=rag_used,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if conversation:
        conversation.updated_at = datetime.utcnow()
        await db.commit()

    return message


async def load_conversation_history(conversation_id: int, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(settings.MAX_HISTORY_MESSAGES)
    )
    messages = list(reversed(result.scalars().all()))
    history = [
        {"role": msg.role, "content": msg.content, "rag_used": msg.rag_used} for msg in messages
    ]
    logger.info(f"📜 Loaded {len(history)} history messages for conversation {conversation_id}")
    return history


async def process_chat_message(
    user_message: str,
    conversation_id: Optional[int],
    user_id: int,
    temperature: float,
    use_rag: bool,
    db: AsyncSession = None,
) -> tuple[int, int, str, Optional[Dict]]:
    conversation = await get_or_create_conversation(conversation_id, user_id, db)
    history = await load_conversation_history(conversation.id, db)
    recent_rag_active = any(msg.get("rag_used", False) for msg in history[-3:])

    await save_message(conversation_id=conversation.id, role="user", content=user_message, db=db)

    rag_result = None
    enhanced_message = user_message

    if use_rag:
        try:
            rag_context = rag_service.get_context(
                query=user_message, user_id=user_id, conversation_context=recent_rag_active
            )
            if rag_context:
                enhanced_message = build_rag_enhanced_message(
                    context=rag_context["context"], question=user_message
                )
                rag_result = {
                    "sources": rag_context["sources"],
                    "chunks_count": rag_context["chunks_count"],
                    "detected_topic": rag_context["detected_topic"],
                }
        except Exception as e:
            logger.warning(f"⚠️ RAG context retrieval failed: {e}")

    messages = [{"role": m["role"], "content": m["content"]} for m in history] + [
        {"role": "user", "content": enhanced_message}
    ]
    messages = condense_messages(
        messages,
        system_prompt=llm_service.SYSTEM_PROMPT,
        max_tokens=settings.OLLAMA_CONTEXT_WINDOW - settings.CONTEXT_WINDOW_BUFFER,
    )
    assistant_response = llm_service.chat(messages, temperature)

    assistant_msg = await save_message(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_response,
        db=db,
        sources=rag_result["sources"] if rag_result else None,
        rag_used=bool(rag_result),
    )

    return conversation.id, assistant_msg.id, assistant_response, rag_result


async def process_chat_message_stream(
    user_message: str,
    conversation_id: Optional[int],
    user_id: int,
    temperature: float,
    use_rag: bool = True,
    db: AsyncSession = None,
) -> AsyncGenerator:
    conversation = await get_or_create_conversation(conversation_id, user_id, db)
    history = await load_conversation_history(conversation.id, db)
    recent_rag_active = any(msg.get("rag_used", False) for msg in history[-3:])

    await save_message(conversation_id=conversation.id, role="user", content=user_message, db=db)

    rag_result = None
    enhanced_message = user_message

    if use_rag:
        try:
            rag_context = await rag_service.aget_context(
                query=user_message, user_id=user_id, conversation_context=recent_rag_active
            )
            if rag_context:
                enhanced_message = build_rag_enhanced_message(
                    context=rag_context["context"], question=user_message
                )
                rag_result = {
                    "sources": rag_context["sources"],
                    "chunks_count": rag_context["chunks_count"],
                    "detected_topic": rag_context["detected_topic"],
                }
        except Exception as e:
            logger.warning(f"⚠️ RAG context retrieval failed: {e}")

    messages = [{"role": m["role"], "content": m["content"]} for m in history] + [
        {"role": "user", "content": enhanced_message}
    ]
    messages = condense_messages(
        messages,
        system_prompt=llm_service.SYSTEM_PROMPT,
        max_tokens=settings.OLLAMA_CONTEXT_WINDOW - settings.CONTEXT_WINDOW_BUFFER,
    )
    accumulated_response = ""

    async for chunk in llm_service.chat_stream(messages, temperature):
        accumulated_response += chunk
        yield {"type": "chunk", "content": chunk}

    assistant_msg = await save_message(
        conversation_id=conversation.id,
        role="assistant",
        content=accumulated_response,
        db=db,
        sources=rag_result["sources"] if rag_result else None,
        rag_used=bool(rag_result),
    )

    conversation_title = None
    if len(history) == 0:
        logger.info("📝 First message — generating conversation title...")
        conversation_title = generate_conversation_title(user_message)
        conversation.title = conversation_title
        conversation.updated_at = datetime.utcnow()
        await db.commit()
        logger.info(f"✅ Conversation {conversation.id} title set to: '{conversation_title}'")

    yield {
        "type": "done",
        "conversation_id": conversation.id,
        "message_id": assistant_msg.id,
        "rag_result": rag_result,
        "conversation_title": conversation_title,
    }
