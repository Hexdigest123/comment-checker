"""AI conversation model for per-user assistant chat history."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .user import User


class MessageRoleEnum(str, Enum):
    """Role of message in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ToolTypeEnum(str, Enum):
    """Available AI tools."""
    NONE = "none"
    SEARCH = "search"           # Search comments/accounts
    CLASSIFY = "classify"       # Classify comments
    EXPORT = "export"           # Export data
    MOVE = "move"               # Navigate/move in app
    SUMMARIZE = "summarize"     # Summarize data
    ANALYZE = "analyze"         # Analyze patterns


class AIConversation(Base):
    """
    Stores conversation history for the per-user AI assistant.
    
    Each conversation maintains context for that user's session.
    The assistant can use tools to interact with the system.
    """
    
    __tablename__ = "ai_conversations"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    
    # User who owns this conversation
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Session identifier (for grouping related messages)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    
    # Message content
    role: Mapped[MessageRoleEnum] = mapped_column(
        String(20),
        nullable=False,
        default=MessageRoleEnum.USER
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Tool usage (if any)
    tool_used: Mapped[ToolTypeEnum] = mapped_column(
        String(20),
        nullable=False,
        default=ToolTypeEnum.NONE
    )
    tool_input: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    tool_output: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    
    # Response metadata
    response_model: Mapped[Optional[str]] = mapped_column(String(50))  # mistral-medium-3.5
    response_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="ai_conversations"
    )
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    def __repr__(self) -> str:
        role_str = self.role.value
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<AIConversation(id={self.id}, role={role_str}, content={content_preview})>"
    
    @property
    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.role == MessageRoleEnum.USER
    
    @property
    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == MessageRoleEnum.ASSISTANT
    
    @property
    def used_tool(self) -> bool:
        """Check if a tool was used."""
        return self.tool_used != ToolTypeEnum.NONE
