"""Comment embedding model for semantic search with PGVector."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey, Integer, Float, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .comment import Comment


class CommentEmbedding(Base):
    """
    Stores vector embeddings for comments to enable semantic search.
    
    Uses PGVector extension for efficient vector similarity search.
    Embeddings are generated using Mistral's embedding model (mistral-embed).
    """
    
    __tablename__ = "comment_embeddings"
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    
    # Reference to comment
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True  # One embedding per comment
    )
    
    # Vector embedding (768 dimensions for mistral-embed)
    # Stored as float array for PGVector
    embedding: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False
    )
    
    # Metadata about the embedding
    model: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="mistral-embed"
    )
    dimension: Mapped[int] = mapped_column(Integer, default=768)
    
    # Relationships
    comment: Mapped["Comment"] = relationship(
        "Comment",
        back_populates="embeddings"
    )
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    def __repr__(self) -> str:
        return f"<CommentEmbedding(id={self.id}, comment_id={self.comment_id}, model={self.model})>"
    
    @property
    def embedding_array(self) -> list[float]:
        """Get embedding as numpy-friendly array."""
        return list(self.embedding) if self.embedding else []
