"""
AI Assistant API router
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import get_current_active_user
from ..db.models import AIConversation, User
from ..db.session import get_async_db
from ..schemas import (
    AIChatRequest,
    AIChatResponse,
    AIConversationResponse,
    AIStatsResponse,
    PageParams,
    PageResponse,
)
from ..services.ai_assistant import AIAssistantService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Assistant"])


@router.post("/chat", response_model=AIChatResponse)
async def chat_with_ai(
    request: AIChatRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> AIChatResponse:
    """
    Chat with the AI assistant.

    The assistant answers in natural language and can call tools while
    composing its answer:
    - filter_comments: structured search by classification category, severity,
      status, date range or harmful score
    - semantic_search_comments: find comments by meaning (embeddings)
    - classify_text: classify a text through the moderation pipeline
    - get_dashboard_stats: aggregate statistics about the dataset
    """
    ai_service = AIAssistantService(db)

    try:
        result = await ai_service.chat(
            user_id=current_user.id,
            message=request.message,
            session_id=request.session_id,
            is_admin=current_user.is_admin,
        )
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing your request: {e!s}",
        )

    return AIChatResponse(
        response=result["response"],
        tool_used=result["tool_used"],
        tool_calls=result["tool_calls"],
        conversation_id=result["conversation_id"],
        session_id=result["session_id"],
        model=result["model"],
        tokens=result["tokens"],
        latency_ms=result["latency_ms"],
    )


@router.get("/conversations", response_model=PageResponse[AIConversationResponse])
async def list_ai_conversations(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    params: PageParams = Depends(),
    session_id: str | None = Query(None, description="Filter by session ID"),
) -> PageResponse[AIConversationResponse]:
    """
    List AI conversation history for the current user.

    Supports pagination and filtering by session ID.
    """
    query = select(AIConversation).where(
        AIConversation.user_id == current_user.id
    )

    if session_id:
        query = query.where(AIConversation.session_id == session_id)
    query = query.order_by(desc(AIConversation.created_at))

    count_query = select(func.count()).select_from(AIConversation).where(
        AIConversation.user_id == current_user.id
    )
    if session_id:
        count_query = count_query.where(AIConversation.session_id == session_id)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    query = query.limit(params.page_size).offset((params.page - 1) * params.page_size)
    result = await db.execute(query)
    conversations = result.scalars().all()

    items = []
    for conv in conversations:
        items.append(AIConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            session_id=conv.session_id,
            role=getattr(conv.role, "value", conv.role),
            content=conv.content,
            tool_used=getattr(conv.tool_used, "value", conv.tool_used),
            tool_input=conv.tool_input,
            tool_output=conv.tool_output,
            response_model=conv.response_model,
            response_tokens=conv.response_tokens,
            latency_ms=conv.latency_ms,
            created_at=conv.created_at
        ))

    total_pages = (total + params.page_size - 1) // params.page_size if total > 0 else 0

    return PageResponse[AIConversationResponse](
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_previous=params.page > 1,
    )


@router.get("/sessions", response_model=list[str])
async def list_ai_sessions(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = Query(default=20, description="Maximum number of sessions to return"),
) -> list[str]:
    """
    List AI conversation sessions for the current user.
    """
    result = await db.execute(
        select(AIConversation.session_id, func.max(AIConversation.created_at))
        .where(AIConversation.user_id == current_user.id)
        .group_by(AIConversation.session_id)
        .order_by(desc(func.max(AIConversation.created_at)))
        .limit(limit)
    )

    sessions = [row[0] for row in result.all() if row[0]]
    return sessions


@router.get("/stats", response_model=AIStatsResponse)
async def get_ai_stats(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> AIStatsResponse:
    """
    Get AI usage statistics for the current user.
    """
    result = await db.execute(
        select(func.count())
        .select_from(AIConversation)
        .where(AIConversation.user_id == current_user.id)
    )
    total_conversations = result.scalar() or 0

    result = await db.execute(
        select(func.count(distinct(AIConversation.session_id)))
        .select_from(AIConversation)
        .where(AIConversation.user_id == current_user.id)
    )
    total_sessions = result.scalar() or 0

    result = await db.execute(
        select(func.coalesce(func.sum(AIConversation.response_tokens), 0))
        .select_from(AIConversation)
        .where(AIConversation.user_id == current_user.id)
    )
    total_tokens = result.scalar() or 0

    result = await db.execute(
        select(func.coalesce(func.avg(AIConversation.latency_ms), 0))
        .select_from(AIConversation)
        .where(AIConversation.user_id == current_user.id)
    )
    avg_latency = result.scalar() or 0.0

    result = await db.execute(
        select(
            AIConversation.tool_used,
            func.count()
        )
        .where(AIConversation.user_id == current_user.id)
        .where(AIConversation.tool_used != "none")
        .group_by(AIConversation.tool_used)
    )
    tools_used = {getattr(row[0], "value", row[0]): row[1] for row in result.all()}

    return AIStatsResponse(
        total_conversations=total_conversations,
        total_sessions=total_sessions,
        total_tokens=total_tokens,
        avg_latency_ms=float(avg_latency),
        tools_used=tools_used
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_session(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete all conversations in a session."""
    result = await db.execute(
        select(AIConversation)
        .where(
            AIConversation.user_id == current_user.id,
            AIConversation.session_id == session_id
        )
    )
    conversations = result.scalars().all()

    for conv in conversations:
        await db.delete(conv)

    await db.commit()

    logger.info(f"Deleted AI session: {session_id}")


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_conversation(
    conversation_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete a single AI conversation."""
    result = await db.execute(
        select(AIConversation)
        .where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied"
        )

    await db.delete(conversation)
    await db.commit()

    logger.info(f"Deleted AI conversation: {conversation_id}")
