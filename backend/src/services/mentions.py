"""
Mention service

Parses @mentions in comment text and links them to registered external
accounts. A mention is only linked when the referenced entity is registered
in the system on the same platform as the comment; otherwise it is ignored.
"""

import logging
import re
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Comment, CommentMention, ExternalAccount
from ..db.models.external_account import PlatformEnum as PE

if TYPE_CHECKING:
    from ..db.models import Comment as CommentModel

logger = logging.getLogger(__name__)

# @handle pattern: leading '@' not preceded by a word character (excludes
# email addresses like user@example.com), followed by handle characters
MENTION_PATTERN = re.compile(r"(?<![A-Za-z0-9._%+-])@([A-Za-z0-9][A-Za-z0-9._-]{0,254})")


def extract_mentions(text: Optional[str]) -> List[str]:
    """
    Extract @handles from text, preserving original casing.

    Consecutive mentions are deduplicated case-insensitively (first
    occurrence wins) and order of appearance is preserved. Trailing
    punctuation ('.', '_', '-') that is usually sentence punctuation is
    trimmed from the handle.

    Args:
        text: Comment text

    Returns:
        List of handles without the leading '@'
    """
    if not text:
        return []

    handles: List[str] = []
    seen = set()
    for match in MENTION_PATTERN.finditer(text):
        handle = match.group(1).rstrip("._-")
        if not handle or handle.lower() in seen:
            continue
        seen.add(handle.lower())
        handles.append(handle)
    return handles


def _comment_platform(comment: "CommentModel") -> Optional[str]:
    """Get the platform a comment was posted on (for the same-platform check)."""
    if comment.platform:
        return str(comment.platform)
    if comment.source_platform:
        return str(comment.source_platform)
    return None


async def resolve_comment_mentions(
    db: AsyncSession,
    comment: "CommentModel",
) -> List[ExternalAccount]:
    """
    Resolve @mentions in a comment to registered external accounts.

    Mentions are matched case-insensitively by username against accounts
    on the same platform as the comment. Mentions of the comment's own
    author are excluded (a comment references *other* entities).
    Unresolvable mentions are ignored.

    Args:
        db: Database session
        comment: The comment whose text is inspected

    Returns:
        List of referenced external accounts
    """
    handles = extract_mentions(comment.text)
    platform = _comment_platform(comment)
    if not handles or not platform:
        return []

    try:
        platform_enum = PE(platform.lower())
    except ValueError:
        return []

    result = await db.execute(
        select(ExternalAccount).where(
            ExternalAccount.platform == platform_enum,
            func.lower(ExternalAccount.username).in_(
                [h.lower() for h in handles]
            ),
        )
    )
    accounts = result.scalars().all()

    if comment.external_account_id:
        accounts = [a for a in accounts if a.id != comment.external_account_id]

    return accounts


async def sync_comment_mentions(
    db: AsyncSession,
    comment: "CommentModel",
) -> List[CommentMention]:
    """
    (Re)compute the mention links for a comment.

    Replaces the existing mention rows with the current set of resolved
    mentions. The caller is responsible for committing the session.

    Args:
        db: Database session
        comment: The comment whose mentions should be synced

    Returns:
        List of CommentMention rows added (not yet committed)
    """
    await db.execute(
        delete(CommentMention).where(CommentMention.comment_id == comment.id)
    )

    accounts = await resolve_comment_mentions(db, comment)
    if not accounts:
        return []

    # Map lowercased handle (as typed) back for storing the raw mention
    handle_by_lower = {h.lower(): h for h in extract_mentions(comment.text)}
    platform = _comment_platform(comment)

    mentions = [
        CommentMention(
            comment_id=comment.id,
            external_account_id=account.id,
            mentioned_username=handle_by_lower.get(
                (account.username or "").lower(), account.username
            ),
            platform=platform,
        )
        for account in accounts
    ]
    db.add_all(mentions)

    logger.debug(
        f"Linked {len(mentions)} mention(s) for comment {comment.id}"
    )
    return mentions
