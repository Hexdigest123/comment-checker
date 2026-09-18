"""
AI Assistant API router
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from ..config import get_settings
from ..db.session import get_async_db
from ..db.models import AIConversation
from ..schemas import (
    AIChatRequest,
    AIChatResponse,
    AIConversationResponse,
    AIConversationListResponse,
    AIStatsResponse,
    AISearchRequest,
    AISearchResponse,
    AIAnalyzeRequest,
    AIAnalyzeResponse,
    PageParams,
    PageResponse,
)
from ..services.ai_assistant import AIAssistantService
from ..api.auth import get_current_user, get_current_active_user

# Get settings
settings = get_settings()

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.post("/chat", response_model=AIChatResponse)
async def chat_with_ai(
    request: AIChatRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> AIChatResponse:
    """
    Chat with the AI assistant.
    
    The AI assistant can:
    - Answer questions about comments, classifications, and clusters
    - Search through data using natural language
    - Classify comments for toxicity and categories
    - Export data to CSV or JSON
    - Guide users through the application (move/navigate)
    - Summarize data and generate reports
    - Analyze patterns in the data
    
    Tools available:
    - search: Find comments, accounts, or clusters
    - classify: Classify text or comments
    - export: Export data to CSV/JSON
    - move: Navigate to specific pages in the app
    - summarize: Summarize data or generate reports
    - analyze: Analyze patterns in the data
    """
    ai_service = AIAssistantService(db)
    
    try:
        result = await ai_service.chat(
            user_id=current_user.id,
            message=request.message,
            session_id=request.session_id,
            use_tools=request.use_tools
        )
        
        return AIChatResponse(
            response=result["response"],
            tool_used=result["tool_used"],
            tool_input=result["tool_input"],
            tool_output=result["tool_output"],
            conversation_id=result["conversation_id"],
            session_id=result["session_id"],
            model=result["model"],
            tokens=result["tokens"],
            latency_ms=result["latency_ms"]
        )
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing your request: {str(e)}"
        )


@router.get("/conversations", response_model=PageResponse[AIConversationResponse])
async def list_ai_conversations(
    params: PageParams = Depends(),
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
) -> PageResponse[AIConversationResponse]:
    """
    List AI conversation history for the current user.
    
    Supports pagination and filtering by session ID.
    """
    # Build query
    query = select(AIConversation).where(
        AIConversation.user_id == current_user.id
    )
    
    if session_id:
        query = query.where(AIConversation.session_id == session_id)
    
    # Sort by created_at descending
    query = query.order_by(desc(AIConversation.created_at))
    
    # Count total
    from sqlalchemy import func
    count_query = select(func.count()).select_from(AIConversation).where(
        AIConversation.user_id == current_user.id
    )
    if session_id:
        count_query = count_query.where(AIConversation.session_id == session_id)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # Get paginated results
    query = query.limit(params.page_size).offset((params.page - 1) * params.page_size)
    result = await db.execute(query)
    conversations = result.scalars().all()
    
    # Build response
    items = []
    for conv in conversations:
        items.append(AIConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            session_id=conv.session_id,
            role=conv.role.value,
            content=conv.content,
            tool_used=conv.tool_used.value,
            tool_input=conv.tool_input,
            tool_output=conv.tool_output,
            response_model=conv.response_model,
            response_tokens=conv.response_tokens,
            latency_ms=conv.latency_ms,
            created_at=conv.created_at
        ))
    
    return PageResponse[AIConversationResponse](
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=(total + params.page_size - 1) // params.page_size if total > 0 else 0
    )


@router.get("/sessions", response_model=list[str])
async def list_ai_sessions(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = Query(default=20, description="Maximum number of sessions to return"),
) -> list[str]:
    """
    List AI conversation sessions for the current user.
    
    Returns a list of session IDs.
    """
    from sqlalchemy import distinct
    
    result = await db.execute(
        select(distinct(AIConversation.session_id))
        .where(AIConversation.user_id == current_user.id)
        .order_by(desc(AIConversation.created_at))
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
    
    Returns:
    - Total conversations
    - Total sessions
    - Total tokens used
    - Average latency
    - Tools used breakdown
    """
    from sqlalchemy import func, or_
    
    # Count conversations
    result = await db.execute(
        select(func.count())
        .select_from(AIConversation)
        .where(AIConversation.user_id == current_user.id)
    )
    total_conversations = result.scalar() or 0
    
    # Count sessions
    result = await db.execute(
        select(func.count(distinct(AIConversation.session_id)))
        .select_from(AIConversation)
        .where(AIConversation.user_id == current_user.id)
    )
    total_sessions = result.scalar() or 0
    
    # Sum tokens
    result = await db.execute(
        select(func.coalesce(func.sum(AIConversation.response_tokens), 0))
        .select_from(AIConversation)
        .where(AIConversation.user_id == current_user.id)
    )
    total_tokens = result.scalar() or 0
    
    # Average latency
    result = await db.execute(
        select(func.coalesce(func.avg(AIConversation.latency_ms), 0))
        .select_from(AIConversation)
        .where(AIConversation.user_id == current_user.id)
    )
    avg_latency = result.scalar() or 0.0
    
    # Tools used breakdown
    result = await db.execute(
        select(
            AIConversation.tool_used,
            func.count()
        )
        .where(AIConversation.user_id == current_user.id)
        .where(AIConversation.tool_used != "none")
        .group_by(AIConversation.tool_used)
    )
    tools_used = {row[0].value: row[1] for row in result.all()}
    
    return AIStatsResponse(
        total_conversations=total_conversations,
        total_sessions=total_sessions,
        total_tokens=total_tokens,
        avg_latency_ms=float(avg_latency),
        tools_used=tools_used
    )


@router.post("/search", response_model=AISearchResponse)
async def ai_search(
    request: AISearchRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> AISearchResponse:
    """
    Perform AI-powered search.
    
    Uses semantic search (Mistral embeddings + PGVector) combined with
    keyword and fuzzy search for comprehensive results.
    
    Args:
        query: Search query text
        search_type: Type of items to search (comments, accounts, clusters, all)
        limit: Maximum number of results
        use_semantic: Whether to use semantic search
        use_fuzzy: Whether to use fuzzy search
    """
    ai_service = AIAssistantService(db)
    
    try:
        # Build search input
        search_input = {
            "query": request.query,
            "type": request.search_type,
            "limit": request.limit
        }
        
        # Execute search tool
        result = await ai_service._tool_search(search_input, current_user.id)
        
        return AISearchResponse(
            query=result["query"],
            search_type=result["type"],
            results=result["results"],
            total=result["total"],
            limit=result["limit"]
        )
    except Exception as e:
        logger.error(f"AI search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search error: {str(e)}"
        )


@router.post("/analyze", response_model=AIAnalyzeResponse)
async def ai_analyze(
    request: AIAnalyzeRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> AIAnalyzeResponse:
    """
    Perform AI-powered analysis.
    
    Analyze patterns in the data including:
    - Toxicity patterns across clusters
    - Activity trends over time
    - Connection patterns between clusters
    
    Args:
        analysis_type: Type of analysis (toxicity, activity, connections, trends)
        target: Target of analysis (cluster, account, platform, all)
        period: Time period for analysis
    """
    ai_service = AIAssistantService(db)
    
    try:
        # Build analysis input
        analysis_input = {
            "type": request.analysis_type,
            "target": request.target or "all"
        }
        
        # Execute analyze tool
        result = await ai_service._tool_analyze(analysis_input, current_user.id)
        
        return AIAnalyzeResponse(
            type=result["type"],
            target=result["target"],
            data=result
        )
    except Exception as e:
        logger.error(f"AI analyze error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis error: {str(e)}"
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_session(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete all conversations in a session."""
    # Delete conversations in this session
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
