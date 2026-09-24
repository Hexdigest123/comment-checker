"""Comment mention model for linking comments to referenced external accounts."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .comment import Comment
    from .external_account import ExternalAccount


class CommentMention(Base):
    """
    Represents an @mention in a comment that references a registered external account.

    Mentions are only linked when the referenced account exists in the system
    on the same platform as the comment; unresolvable mentions are ignored.
    """

    __tablename__ = "comment_mentions"
    __table_args__ = (
        UniqueConstraint("comment_id", "external_account_id", name="uq_comment_mention"),
    )

    # The comment containing the mention
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    comment: Mapped["Comment"] = relationship(
        "Comment",
        back_populates="mentions",
        foreign_keys=[comment_id],
    )

    # The referenced account (registered on the same platform)
    external_account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("external_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_account: Mapped["ExternalAccount"] = relationship(
        "ExternalAccount",
        back_populates="mentions",
        foreign_keys=[external_account_id],
    )

    # The handle as it appeared in the comment text (without the leading '@')
    mentioned_username: Mapped[Optional[str]] = mapped_column(String(255))
    # Platform used for the same-platform check
    platform: Mapped[Optional[str]] = mapped_column(String(20))

    def __repr__(self) -> str:
        return (
            f"<CommentMention(comment_id={self.comment_id}, "
            f"external_account_id={self.external_account_id})>"
        )
