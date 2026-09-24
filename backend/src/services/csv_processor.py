"""
CSV processing service
Handles CSV file upload and comment extraction

Updated to support:
- Extracting username and link from CSV
- Creating or finding external accounts
- Auto-clustering by username/platform
- Auto-generating embeddings for comments
- Skipping comments that already exist (duplicate detection before AI processing)
"""

import csv
import io
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from ..config import get_settings
from ..db.models import Comment, CommentStatus, ExternalAccount
from ..db.models.external_account import PlatformEnum as PE
from ..services.comment import create_comment_batch
from ..services.clustering import ClusteringService
from ..services.embedding import EmbeddingService

settings = get_settings()

logger = logging.getLogger(__name__)

# CSV column mappings - maps common CSV column names to our model fields
CSV_COLUMN_MAPPINGS = {
    # Comment text
    "comment": "text",
    "comment text": "text",
    "text": "text",
    "comment_content": "text",
    "content": "text",
    
    # Original author
    "username": "username",
    "user": "username",
    "author": "username",
    "name": "username",
    "user name": "username",
    
    # Author display name
    "display name": "display_name",
    "display_name": "display_name",
    "full name": "display_name",
    "full_name": "display_name",
    "link": "link",
    "url": "link",
    "profile url": "link",
    "profile_url": "link",
    "user url": "link",
    "user_url": "link",
    "source": "link",
    "source url": "link",
    "source_url": "link",
    
    # Platform
    "platform": "platform",
    "social media": "platform",
    "social_media": "platform",
    "network": "platform",
    
    # Author ID
    "user id": "platform_user_id",
    "author id": "platform_user_id",
    "profile id": "platform_user_id",
    "user_id": "platform_user_id",
    
    # Context
    "context": "context",
    "situation": "context",
    "description": "context",
    
    # Priority
    "priority": "priority",
    "priorit\u00e4t": "priority",  # Handle German umlaut

    # Date the comment was written on the platform (from the export)
    "date": "posted_at",
    "comment date": "posted_at",
    "posted at": "posted_at",
    "posted_at": "posted_at",
    "published at": "posted_at",
    "publication date": "posted_at",
    "datum": "posted_at",

    # Direct link to the comment itself (not the author profile)
    "comment url": "comment_url",
    "comment link": "comment_url",
    "permalink": "comment_url",

    # Platform identifier of the comment
    "comment id": "platform_comment_id",

    # Like count on the comment
    "likes": "likes",
}


def normalize_column_name(column_name: str) -> str:
    """
    Normalize CSV column name for matching.
    
    Args:
        column_name: Raw column name from CSV
        
    Returns:
        Normalized column name
    """
    normalized = column_name.strip().lower()
    
    normalized = "".join(c if c.isalnum() or c in [" ", "_"] else "" for c in normalized)
    
    return normalized


def map_csv_columns(csv_columns: List[str]) -> Dict[str, str]:
    """
    Map CSV columns to our model fields.
    
    Args:
        csv_columns: List of column names from CSV
        
    Returns:
        Dictionary mapping CSV column names to model field names
    """
    mapping = {}
    normalized_columns = [normalize_column_name(col) for col in csv_columns]
    
    for csv_col, normalized in zip(csv_columns, normalized_columns):
        for csv_pattern, model_field in CSV_COLUMN_MAPPINGS.items():
            if normalize_column_name(csv_pattern) == normalized:
                mapping[csv_col] = model_field
                break
    
    return mapping


def extract_url_platform(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract platform and username from a URL.
    
    Args:
        url: URL string
        
    Returns:
        Tuple of (platform, username) or (None, None) if not extractable
    """
    if not url:
        return None, None
    
    url_lower = url.lower().strip()
    
    # Twitter/X
    twitter_patterns = [
        r"twitter\.com/([^/]+)",
        r"x\.com/([^/]+)",
        r"twitter\.com/i/web/status/(\d+)",
        r"x\.com/i/web/status/(\d+)",
    ]
    
    # Facebook
    facebook_patterns = [
        r"facebook\.com/([^/]+)",
        r"fb\.me/([^/]+)",
        r"facebook\.com/profile\.php\?id=(\d+)",
    ]
    
    # Instagram
    instagram_patterns = [
        r"instagram\.com/([^/]+)",
        r"instagr\.am/([^/]+)",
    ]
    
    # YouTube
    youtube_patterns = [
        r"youtube\.com/c/([^/]+)",
        r"youtube\.com/user/([^/]+)",
        r"youtube\.com/channel/([^/]+)",
        r"youtu\.be/([^/]+)",
    ]
    
    # TikTok
    tiktok_patterns = [
        r"tiktok\.com/@([^/]+)",
    ]
    
    # Reddit
    reddit_patterns = [
        r"reddit\.com/user/([^/]+)",
        r"reddit\.com/r/([^/]+)",
    ]
    
    # LinkedIn
    linkedin_patterns = [
        r"linkedin\.com/in/([^/]+)",
    ]
    
    # Try to match patterns
    patterns = [
        (twitter_patterns, "twitter"),
        (facebook_patterns, "facebook"),
        (instagram_patterns, "instagram"),
        (youtube_patterns, "youtube"),
        (tiktok_patterns, "tiktok"),
        (reddit_patterns, "reddit"),
        (linkedin_patterns, "linkedin"),
    ]
    
    for pattern_list, platform in patterns:
        for pattern in pattern_list:
            match = re.search(pattern, url_lower)
            if match:
                username = match.group(1)
                # Clean up username
                username = username.strip("/@ ")
                if username:
                    return platform, username
    
    return None, None


def _parse_csv_datetime(value: str) -> Optional[datetime]:
    """
    Parse a CSV date/datetime value.

    Handles ISO 8601 (as provided by exports) and a few common fallback
    formats. Returns None when the value cannot be parsed.
    """
    value = value.strip()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    logger.warning("Could not parse CSV date value: %r", value)
    return None


def extract_comment_from_row(
    row: Dict[str, str],
    column_mapping: Dict[str, str],
    user_id: str,
    batch_id: str,
    default_context: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Extract comment data from a CSV row.
    
    This updated version:
    1. Extracts username and link from CSV
    2. Determines platform from URL or explicit platform column
    3. Creates external account info for clustering
    
    Args:
        row: Dictionary of CSV row data
        column_mapping: Mapping of CSV columns to model fields
        user_id: User ID who uploaded the CSV
        batch_id: Batch ID for tracking
        default_context: Context supplied at upload time, used when the row
            has no context column value

    Returns:
        Dictionary with comment data including external_account_info
    """
    comment_data = {
        "user_id": user_id,
        "status": CommentStatus.PENDING,
        "metadata": {"batch_id": batch_id},
    }
    
    # Track extracted fields
    extracted_username = None
    extracted_display_name = None
    extracted_link = None
    extracted_platform = None
    extracted_platform_user_id = None
    for csv_col, model_field in column_mapping.items():
        if csv_col in row:
            value = row[csv_col].strip() if row[csv_col] else None
            
            if value:
                if model_field == "text":
                    comment_data["text"] = value
                elif model_field == "username":
                    extracted_username = value
                    comment_data["original_author"] = value
                elif model_field == "display_name":
                    extracted_display_name = value
                elif model_field == "link":
                    extracted_link = value
                    comment_data["original_author_url"] = value
                elif model_field == "platform":
                    extracted_platform = value.lower()
                elif model_field == "platform_user_id":
                    extracted_platform_user_id = value
                    comment_data["original_author_id"] = value
                elif model_field == "comment_url":
                    comment_data["source_url"] = value
                elif model_field == "platform_comment_id":
                    comment_data["platform_comment_id"] = value
                elif model_field == "posted_at":
                    parsed_date = _parse_csv_datetime(value)
                    if parsed_date:
                        comment_data["posted_at"] = parsed_date
                elif model_field == "likes":
                    try:
                        comment_data["metadata"]["likes"] = int(value)
                    except ValueError:
                        logger.warning("Could not parse CSV likes value: %r", value)
                elif model_field == "context":
                    comment_data["context"] = value
                elif model_field == "priority":
                    # Try to map priority
                    priority_map = {
                        "high": "high",
                        "medium": "medium",
                        "low": "low",
                        "hoch": "high",
                        "mittel": "medium",
                        "niedrig": "low",
                    }
                    comment_data["priority"] = priority_map.get(value.lower(), "medium")

    # Files without a dedicated comment link keep the previous behaviour of
    # treating the author/profile link as the source URL
    if not comment_data.get("source_url") and extracted_link:
        comment_data["source_url"] = extracted_link

    # Preserve columns the mapping does not know (analyst assessments,
    # evaluation fields, thumbnails, ...) so no export data is lost
    source_columns = {
        csv_col: row[csv_col].strip()
        for csv_col in row
        if csv_col and csv_col not in column_mapping
        and row.get(csv_col) and row[csv_col].strip()
    }
    if source_columns:
        comment_data["metadata"]["source_columns"] = source_columns

    # Fall back to the context supplied at upload time when the row has none
    if not comment_data.get("context") and default_context:
        comment_data["context"] = default_context

    # Try to extract platform and username from link if not explicitly provided
    if not extracted_platform and extracted_link:
        platform, username = extract_url_platform(extracted_link)
        if platform:
            extracted_platform = platform
        if username and not extracted_username:
            extracted_username = username
    
    # If we have a username or link, create external account info
    if extracted_username or extracted_link:
        comment_data["external_account_info"] = {
            "platform": extracted_platform or "other",
            "username": extracted_username,
            "display_name": extracted_display_name,
            "profile_url": extracted_link,
            "platform_user_id": extracted_platform_user_id,
        }
        if extracted_platform:
            comment_data["source_platform"] = extracted_platform
            try:
                comment_data["platform"] = PE(extracted_platform).value
            except ValueError:
                comment_data["platform"] = "other"
    if "text" not in comment_data or not comment_data["text"]:
        return None
    
    return comment_data


def normalize_comment_text(text: Optional[str]) -> str:
    """
    Normalize comment text for duplicate detection.

    Case-insensitive and insensitive to whitespace differences.

    Args:
        text: Raw comment text
        
    Returns:
        Normalized comment text
    """
    if not text:
        return ""
    return " ".join(text.split()).lower()


def _duplicate_key(comment_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Build a duplicate-detection key from a comment's author and text.

    Args:
        comment_data: Comment data dictionary from extract_comment_from_row
        
    Returns:
        Tuple of (author, normalized text)
    """
    account_info = comment_data.get("external_account_info") or {}
    author = account_info.get("username") or comment_data.get("original_author") or ""
    return (author.strip().lower(), normalize_comment_text(comment_data.get("text")))


async def _existing_duplicate_keys(
    db: AsyncSession,
    user_id: str,
    texts: List[str],
) -> Set[Tuple[str, str]]:
    """
    Fetch duplicate keys of comments already stored for this user.

    Only comments whose (lowercased) text matches one of the given texts
    are fetched, to keep the query cheap on large comment tables.

    Args:
        db: Database session
        user_id: User ID the existing comments belong to
        texts: Candidate comment texts from the current import
        
    Returns:
        Set of (author, normalized text) keys already in the database
    """
    lowered_texts = list({text.lower() for text in texts if text})
    if not lowered_texts:
        return set()
    
    result = await db.execute(
        select(Comment.text, Comment.original_author, ExternalAccount.username)
        .outerjoin(ExternalAccount, Comment.external_account_id == ExternalAccount.id)
        .where(
            Comment.user_id == user_id,
            func.lower(Comment.text).in_(lowered_texts),
        )
    )
    keys: Set[Tuple[str, str]] = set()
    for text, original_author, username in result:
        author = username or original_author or ""
        keys.add((author.strip().lower(), normalize_comment_text(text)))
    return keys


async def process_csv_file(
    db: AsyncSession,
    file: UploadFile,
    user_id: str,
    batch_id: str = None,
    default_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a CSV file and create comments with external accounts and clustering.
    
    This updated version:
    1. Extracts username and link from CSV
    2. Skips duplicate comments (same author + same text) already ingested
       for this user, before any AI processing
    3. Creates or finds external accounts
    4. Auto-clusters accounts by username/platform
    5. Creates comments with external account associations
    6. Optionally generates embeddings for comments
    
    Args:
        db: Database session
        file: Uploaded CSV file
        user_id: User ID who uploaded the file
        batch_id: Optional batch ID (generated if not provided)
        default_context: Optional context supplied at upload time, applied to
            comments that have no context of their own
        
    Returns:
        Dictionary with processing results:
        - total_rows: Total rows in CSV
        - valid_rows: Valid rows processed (duplicates excluded)
        - invalid_rows: Invalid rows skipped
        - duplicates_skipped: Rows skipped because the comment already exists
        - comments: List of created comment IDs
        - accounts_created: Number of new external accounts created
        - clusters_created: Number of new clusters created
    """
    if batch_id is None:
        batch_id = str(uuid.uuid4().hex)
    
    # Read file content
    content = await file.read()
    try:
        # Try UTF-8
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            # Try Latin-1
            text_content = content.decode("latin-1")
        except Exception:
            text_content = content.decode("utf-8", errors="replace")
    
    # Use StringIO to read CSV
    string_io = io.StringIO(text_content)
    delimiter = settings.csv_delimiter
    
    try:
        csv_reader = csv.DictReader(string_io, delimiter=delimiter)
        rows = list(csv_reader)
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        raise ValueError(f"Invalid CSV format: {e}")
    
    if not rows:
        return {
            "total_rows": 0,
            "valid_rows": 0,
            "invalid_rows": 0,
            "duplicates_skipped": 0,
            "comments": [],
            "accounts_created": 0,
            "clusters_created": 0,
        }
    column_mapping = map_csv_columns(csv_reader.fieldnames)
    
    logger.info(f"CSV columns mapped: {column_mapping}")
    clustering_service = ClusteringService(db)
    
    extracted_comments = []
    invalid_rows = 0
    
    for i, row in enumerate(rows):
        comment_data = extract_comment_from_row(
            row, column_mapping, user_id, batch_id, default_context=default_context
        )
        
        if comment_data:
            extracted_comments.append(comment_data)
        else:
            invalid_rows += 1
            logger.warning(f"Skipping invalid row {i + 1}")
    
    # Duplicate detection: skip comments that already exist for this user
    # (same author + same text) before any AI tooling (classification,
    # embeddings) or account/clustering work runs on them.
    existing_keys = await _existing_duplicate_keys(
        db, user_id, [cd["text"] for cd in extracted_comments]
    )
    
    valid_comments = []
    duplicates_skipped = 0
    accounts_created = 0
    clusters_created = set()  # Track unique cluster IDs
    seen_keys: Set[Tuple[str, str]] = set()
    
    for comment_data in extracted_comments:
        key = _duplicate_key(comment_data)
        if key in existing_keys or key in seen_keys:
            duplicates_skipped += 1
            logger.info(f"Skipping duplicate comment: {comment_data['text'][:50]}")
            continue
        seen_keys.add(key)
        
        external_account_info = comment_data.pop("external_account_info", None)
        
        if external_account_info:
            platform = external_account_info.get("platform", "other")
            username = external_account_info.get("username")
            
            try:
                platform_enum = PE(platform.lower())
            except ValueError:
                platform_enum = PE.OTHER
            result = await db.execute(
                select(ExternalAccount).where(
                    ExternalAccount.platform == platform_enum,
                    ExternalAccount.username == username
                )
            )
            account = result.scalar_one_or_none()
            
            if not account:
                account = ExternalAccount(
                    id=str(uuid.uuid4()),
                    platform=platform_enum,
                    username=username,
                    display_name=external_account_info.get("display_name"),
                    profile_url=external_account_info.get("profile_url"),
                    platform_user_id=external_account_info.get("platform_user_id"),
                    is_active=True,
                )
                db.add(account)
                await db.commit()
                await db.refresh(account)
                accounts_created += 1
                
                logger.info(f"Created external account: {account.id} ({platform}/{username})")
            
            # Auto-cluster by username/platform
            cluster = await clustering_service.auto_cluster_by_username(
                platform=platform,
                username=username or "",
                user_id=user_id
            )
            clusters_created.add(cluster.id)
            
            # Assign account to cluster
            if account.cluster_id != cluster.id:
                account.cluster_id = cluster.id
                db.add(account)
                await db.commit()
            comment_data["external_account_id"] = account.id
            
            await clustering_service._update_cluster_metadata(cluster.id)
        
        valid_comments.append(comment_data)
    
    if duplicates_skipped:
        logger.info(f"Skipped {duplicates_skipped} duplicate comment(s) already ingested")
    
    if valid_comments:
        comments = await create_comment_batch(db, valid_comments)
        comment_ids = [c.id for c in comments]
        
        # Optionally generate embeddings for comments
        if settings.mistral_api_key and settings.generate_embeddings:
            try:
                embedding_service = EmbeddingService(db)
                await embedding_service.generate_embeddings_batch(comments)
                logger.info(f"Generated embeddings for {len(comments)} comments")
            except Exception as e:
                logger.warning(f"Failed to generate embeddings: {e}")
    else:
        comment_ids = []
    
    return {
        "total_rows": len(rows),
        "valid_rows": len(valid_comments),
        "invalid_rows": invalid_rows,
        "duplicates_skipped": duplicates_skipped,
        "comments": comment_ids,
        "accounts_created": accounts_created,
        "clusters_created": len(clusters_created),
    }


async def process_csv_file_async(
    db: AsyncSession,
    file_path: str,
    user_id: str,
    batch_id: str = None,
) -> Dict[str, Any]:
    """
    Process a CSV file from disk path.
    
    This is for async background processing.
    
    Args:
        db: Database session
        file_path: Path to CSV file
        user_id: User ID who uploaded the file
        batch_id: Optional batch ID
        
    Returns:
        Dictionary with processing results
    """
    import aiofiles
    from io import BytesIO
    
    async with aiofiles.open(file_path, mode="rb") as f:
        content = await f.read()
        upload_file = UploadFile(
            filename=file_path.split("/")[-1],
            file=BytesIO(content),
        )
        
        return await process_csv_file(db, upload_file, user_id, batch_id)
