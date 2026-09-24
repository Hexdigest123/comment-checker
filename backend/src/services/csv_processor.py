"""
CSV processing service
Handles CSV file upload and comment extraction

Updated to support:
- Extracting username and link from CSV
- Creating or finding external accounts
- Auto-clustering by username/platform
- Auto-generating embeddings for comments
"""

import csv
import io
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import get_settings
from ..db.models import CommentStatus, ExternalAccount
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


def extract_comment_from_row(
    row: Dict[str, str],
    column_mapping: Dict[str, str],
    user_id: str,
    batch_id: str,
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
                    comment_data["source_url"] = value
                elif model_field == "platform":
                    extracted_platform = value.lower()
                elif model_field == "platform_user_id":
                    extracted_platform_user_id = value
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


async def process_csv_file(
    db: AsyncSession,
    file: UploadFile,
    user_id: str,
    batch_id: str = None,
) -> Dict[str, Any]:
    """
    Process a CSV file and create comments with external accounts and clustering.
    
    This updated version:
    1. Extracts username and link from CSV
    2. Creates or finds external accounts
    3. Auto-clusters accounts by username/platform
    4. Creates comments with external account associations
    5. Optionally generates embeddings for comments
    
    Args:
        db: Database session
        file: Uploaded CSV file
        user_id: User ID who uploaded the file
        batch_id: Optional batch ID (generated if not provided)
        
    Returns:
        Dictionary with processing results:
        - total_rows: Total rows in CSV
        - valid_rows: Valid rows processed
        - invalid_rows: Invalid rows skipped
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
            "comments": [],
            "accounts_created": 0,
            "clusters_created": 0,
        }
    column_mapping = map_csv_columns(csv_reader.fieldnames)
    
    logger.info(f"CSV columns mapped: {column_mapping}")
    clustering_service = ClusteringService(db)
    
    valid_comments = []
    invalid_rows = 0
    accounts_created = 0
    clusters_created = set()  # Track unique cluster IDs
    
    for i, row in enumerate(rows):
        comment_data = extract_comment_from_row(row, column_mapping, user_id, batch_id)
        
        if comment_data:
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
        else:
            invalid_rows += 1
            logger.warning(f"Skipping invalid row {i + 1}")
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
