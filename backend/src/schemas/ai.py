"""
Pydantic schemas for AI assistant
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class AIChatRequest(BaseModel):
    """Schema for AI chat request."""
    message: str = Field(..., description="User's message to the AI assistant")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation context")


class AIChatResponse(BaseModel):
    """Schema for AI chat response."""
    response: str = Field(..., description="Assistant's response text")
    tool_used: Optional[str] = Field(None, description="Tool that was used (if any)")
    tool_calls: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Trace of tool calls made while answering: [{tool, input, output}]",
    )
    conversation_id: str = Field(..., description="ID of the assistant's message in the database")
    session_id: str = Field(..., description="Current session ID")
    model: str = Field(..., description="Model used for response")
    tokens: int = Field(..., description="Number of tokens in response")
    latency_ms: int = Field(..., description="Latency in milliseconds")


class AIConversationResponse(BaseModel):
    """Schema for AI conversation history item."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    user_id: int
    session_id: str
    role: str  # user, assistant, system
    content: str
    tool_used: str
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Dict[str, Any]] = None
    response_model: Optional[str] = None
    response_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    created_at: datetime


class AIConversationListResponse(BaseModel):
    """Schema for AI conversation list request."""
    session_id: Optional[str] = Field(None, description="Filter by session ID")
    limit: int = Field(default=50, description="Maximum number of conversations to return")


class AIStatsResponse(BaseModel):
    """Schema for AI usage statistics."""
    total_conversations: int
    total_sessions: int
    total_tokens: int
    avg_latency_ms: float
    tools_used: Dict[str, int]

