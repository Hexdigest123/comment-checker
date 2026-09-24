"""
Classification service backed by the Mistral Moderation 2 API.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..config import get_settings
from ..db.models import Comment, CommentStatus, Classification, ClassificationBackend, ClassificationCategory, ClassificationSeverity
from ..schemas import PageResponse, ClassificationListResponse, ClassificationStatsResponse, ClassificationResponse

settings = get_settings()
logger = logging.getLogger(__name__)


class ClassificationError(Exception):
    """Custom exception for classification errors."""
    pass


def _enum_value(value: Any) -> str:
    """Return the string value of an enum member or the value itself."""
    return value.value if hasattr(value, "value") else value


def classification_to_response(c: Classification) -> ClassificationResponse:
    """Build a ClassificationResponse from a Classification model instance."""
    return ClassificationResponse(
        id=c.id,
        comment_id=c.comment_id,
        backend=_enum_value(c.backend),
        flagged=c.is_toxic,
        category=_enum_value(c.category) if c.category else None,
        severity=_enum_value(c.severity) if c.severity else None,
        confidence=c.confidence,
        harmful_score=c.harmful_score,
        details=c.details,
        created_at=c.created_at,
    )


async def classify_with_mistral(
    comment_text: str,
    context: Optional[str] = None,
    threshold: float = 0.3,
    fallback: bool = True,
) -> Dict[str, Any]:
    """
    Classify a comment using Mistral Moderation 2 API.
    
    Args:
        comment_text: Comment text to classify
        context: Context for classification
        threshold: Flagging threshold
        fallback: Whether to use fallback in-context check
        
    Returns:
        Dictionary with classification results
    """
    try:
        # Import here to avoid circular imports
        from .mistral_client import LLMClient
        
        client = LLMClient(context=context or "")
        
        # First pass: Mistral Moderation 2
        scores = client.classify(comment_text)
        flags = {label: score >= threshold for label, score in scores.items()}
        flagged_by = "mistral_moderation"
        
        # Second pass: In-context fallback if not flagged
        if not any(flags.values()) and fallback:
            second_opinion = client.check_with_context(comment_text)
            if second_opinion:
                flags["hate_speech"] = True
                scores["hate_speech"] = 1.0
                flagged_by = "mistral_fallback"
        
        return {
            "backend": "mistral",
            "scores": scores,
            "flagged": any(flags.values()),
            "flagged_by": flagged_by,
            "category": None,
            "confidence": None,
            "severity": None,
            "harmful": float(flags.get("hate_speech", False)),
        }
    except Exception as e:
        logger.error(f"Mistral classification error: {e}")
        raise ClassificationError(f"Mistral classification failed: {e}")


# Maps Mistral Moderation 2 labels (mistral-moderation-2603) plus the
# mistral-small fallback's injected "hate_speech" score to the
# classification categories we store.
# Moderation 2 labels without a matching category (financial, health, law,
# pii, jailbreaking) are intentionally unmapped and fall through to SAFE.
MODERATION_LABEL_TO_CATEGORY = {
    # Mistral Moderation 2 labels
    "hate_and_discrimination": ClassificationCategory.HATE,
    "violence_and_threats": ClassificationCategory.VIOLENCE,
    "dangerous": ClassificationCategory.VIOLENCE,
    "criminal": ClassificationCategory.ILLEGAL,
    "selfharm": ClassificationCategory.SELF_HARM,
    "sexual": ClassificationCategory.SEXUAL,
    # Injected by the mistral-small in-context fallback
    "hate_speech": ClassificationCategory.HATE,
}


def _category_from_scores(scores: Dict[str, float], threshold: float) -> ClassificationCategory:
    """Derive a category from Moderation 2 label scores (highest label above threshold)."""
    best_label = None
    best_score = 0.0
    for label, score in scores.items():
        if score >= threshold and score > best_score and label in MODERATION_LABEL_TO_CATEGORY:
            best_label = label
            best_score = score
    if best_label is None:
        return ClassificationCategory.SAFE
    return MODERATION_LABEL_TO_CATEGORY[best_label]


async def classify_comment(
    db: AsyncSession,
    comment_id: int,
    backend: str = None,
    context: Optional[str] = None,
    threshold: float = None,
    fallback: bool = True,
) -> Classification:
    """
    Classify a comment using the Mistral Moderation 2 pipeline.

    Args:
        db: Database session
        comment_id: Comment ID to classify
        backend: Backend to use (must be "mistral")
        context: Context for classification
        threshold: Flagging threshold
        fallback: Whether to use fallback

    Returns:
        Classification result
    """
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()

    if comment is None:
        raise ClassificationError(f"Comment not found: {comment_id}")

    backend = backend or "mistral"
    threshold = threshold or settings.classification_threshold
    context = context or comment.context

    from .comment import update_comment_status
    await update_comment_status(
        db=db,
        comment_id=comment_id,
        status=CommentStatus.PROCESSING,
        processing_started_at=datetime.utcnow(),
    )
    
    start_time = time.time()
    
    try:
        if backend == "mistral":
            result = await classify_with_mistral(comment.text, context, threshold, fallback)
        else:
            raise ClassificationError(f"Unknown backend: {backend}")

        classification = Classification(
            id=str(uuid.uuid4()),
            comment_id=comment_id,
            backend=ClassificationBackend(backend),
            category=_category_from_scores(result.get("scores", {}), threshold),
            severity=ClassificationSeverity(result.get("severity")) if result.get("severity") else ClassificationSeverity.LOW,
            confidence=result.get("confidence") or 0.0,
            harmful_score=result.get("harmful", 0.0),
            details={
                "scores": result.get("scores", {}),
                "flagged": result.get("flagged", False),
                "flagged_by": result.get("flagged_by"),
                "threshold": threshold,
                "processing_time_ms": round((time.time() - start_time) * 1000, 2),
            },
        )
        
        db.add(classification)
        await db.commit()
        await db.refresh(classification)

        await update_comment_status(
            db=db,
            comment_id=comment_id,
            status=CommentStatus.COMPLETED,
            processed_at=datetime.utcnow(),
        )
        
        logger.info(f"Comment classified: {comment_id} -> {result.get('flagged', False)}")
        
        return classification
        
    except ClassificationError as e:
        await update_comment_status(
            db=db,
            comment_id=comment_id,
            status=CommentStatus.FAILED,
            error_message=str(e),
        )
        raise


async def classify_comment_batch(
    db: AsyncSession,
    comment_ids: List[int],
    backend: str = None,
    threshold: float = None,
    max_concurrent: int = 5,
) -> List[Classification]:
    """
    Classify multiple comments concurrently.
    
    Args:
        db: Database session
        comment_ids: List of comment IDs to classify
        backend: Backend to use
        threshold: Flagging threshold
        max_concurrent: Maximum concurrent classifications
        
    Returns:
        List of classification results
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def classify_one(comment_id: int) -> Classification:
        async with semaphore:
            return await classify_comment(
                db=db,
                comment_id=comment_id,
                backend=backend,
                threshold=threshold,
            )
    
    tasks = [classify_one(cid) for cid in comment_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    classifications = [r for r in results if isinstance(r, Classification)]
    errors = [r for r in results if isinstance(r, Exception)]
    
    if errors:
        logger.error(f"Batch classification errors: {len(errors)}")
    
    return classifications


async def get_classification_by_id(
    db: AsyncSession,
    classification_id: int,
) -> Optional[Classification]:
    """Get classification by ID."""
    result = await db.execute(
        select(Classification)
        .where(Classification.id == classification_id)
        .options(joinedload(Classification.comment))
    )
    return result.scalar_one_or_none()


async def get_classifications_by_comment(
    db: AsyncSession,
    comment_id: int,
) -> List[Classification]:
    """Get all classifications for a comment."""
    result = await db.execute(
        select(Classification)
        .where(Classification.comment_id == comment_id)
        .order_by(desc(Classification.created_at))
    )
    return result.scalars().all()


async def get_classifications_paginated(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter_condition: Any = None,
) -> PageResponse[ClassificationListResponse]:
    """Get paginated list of classifications."""
    from sqlalchemy import func
    query = select(Classification).options(joinedload(Classification.comment))
    
    if filter_condition:
        query = query.where(filter_condition)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    if sort_by:
        column = getattr(Classification, sort_by, Classification.created_at)
        if sort_order == "asc":
            query = query.order_by(asc(column))
        else:
            query = query.order_by(desc(column))
    else:
        query = query.order_by(desc(Classification.created_at))
    
    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    classifications = result.scalars().all()
    
    total_pages = (total + page_size - 1) // page_size
    has_next = page < total_pages
    has_previous = page > 1
    
    return PageResponse[
        ClassificationListResponse
    ](
        items=[
            ClassificationListResponse(
                id=c.id,
                comment_id=c.comment_id,
                backend=_enum_value(c.backend),
                flagged=c.is_toxic,
                category=_enum_value(c.category) if c.category else None,
                severity=_enum_value(c.severity) if c.severity else None,
                confidence=c.confidence,
                harmful_score=c.harmful_score,
                created_at=c.created_at,
            )
            for c in classifications
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
    )


async def get_classification_stats(
    db: AsyncSession,
    backend: Optional[str] = None,
    date_range: Optional[str] = None,
) -> ClassificationStatsResponse:
    """
    Get classification statistics.
    
    Args:
        db: Database session
        backend: Filter by backend
        date_range: Filter by date range (1m, 6m, 1y, all)
        
    Returns:
        Classification statistics
    """
    from sqlalchemy import func, and_, true
    from datetime import timedelta
    filters = []
    
    if backend:
        filters.append(Classification.backend == backend)
    
    if date_range:
        now = datetime.utcnow()
        if date_range == "1m":
            filters.append(Classification.created_at >= now - timedelta(days=30))
        elif date_range == "6m":
            filters.append(Classification.created_at >= now - timedelta(days=180))
        elif date_range == "1y":
            filters.append(Classification.created_at >= now - timedelta(days=365))
    
    filter_condition = and_(*filters) if filters else None
    total_result = await db.execute(
        select(func.count())
        .select_from(Classification)
        .where(filter_condition if filter_condition is not None else true())
    )
    total = total_result.scalar()
    
    flagged_result = await db.execute(
        select(func.count())
        .where(
            and_(
                Classification.category != ClassificationCategory.SAFE,
                filter_condition if filter_condition is not None else true(),
            )
        )
    )
    flagged = flagged_result.scalar()
    
    not_flagged = total - flagged
    flagged_percentage = round((flagged / total * 100) if total > 0 else 0, 2)
    
    avg_harmful_result = await db.execute(
        select(func.avg(Classification.harmful_score))
        .where(filter_condition if filter_condition is not None else true())
    )
    avg_harmful = float(avg_harmful_result.scalar() or 0)
    
    avg_confidence_result = await db.execute(
        select(func.avg(Classification.confidence))
        .where(
            and_(
                Classification.confidence.isnot(None),
                filter_condition if filter_condition is not None else true(),
            )
        )
    )
    avg_confidence = float(avg_confidence_result.scalar() or 0)

    category_dist = {}
    for cat in ClassificationCategory:
        count_result = await db.execute(
            select(func.count())
            .where(
                and_(
                    Classification.category == cat,
                    filter_condition if filter_condition is not None else true(),
                )
            )
        )
        category_dist[cat.value] = count_result.scalar()
    severity_dist = {}
    for sev in ClassificationSeverity:
        count_result = await db.execute(
            select(func.count())
            .where(
                and_(
                    Classification.severity == sev,
                    filter_condition if filter_condition is not None else true(),
                )
            )
        )
        severity_dist[sev.value] = count_result.scalar()
    
    return ClassificationStatsResponse(
        backend=backend or "all",
        total=total,
        flagged=flagged,
        not_flagged=not_flagged,
        flagged_percentage=flagged_percentage,
        average_harmful=round(avg_harmful, 4),
        average_confidence=round(avg_confidence, 4) if avg_confidence > 0 else None,
        category_distribution={k: v for k, v in category_dist.items() if v > 0},
        severity_distribution={k: v for k, v in severity_dist.items() if v > 0},
    )


class ClassificationService:
    """
    Class-based wrapper around the classification functions,
    for services that hold a long-lived database session (e.g. AIAssistantService).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def classify_text(
        self,
        text: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Classify raw text using the Mistral Moderation 2 pipeline."""
        return await classify_with_mistral(text, context)
