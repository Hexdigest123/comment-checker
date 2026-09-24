"""
Classification worker: in-process job queue that processes PENDING comments.

Uploads create comments with status PENDING. This worker polls the database
for PENDING comments, claims a batch (PENDING -> WAITING), and classifies
each comment (WAITING -> PROCESSING -> COMPLETED/FAILED) using the
classification service. It runs as a background asyncio task started in the
application lifespan, so no external broker (Celery/Redis) is required for
single-instance deployments.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update

from ..config import get_settings
from ..db.models import Comment, CommentStatus
from ..db.session import async_session_maker
from .classification import classify_comment, ClassificationError

settings = get_settings()

logger = logging.getLogger(__name__)


class ClassificationWorker:
    """Background worker that drains the comment classification queue."""

    def __init__(
        self,
        poll_interval: Optional[float] = None,
        batch_size: Optional[int] = None,
    ):
        self.poll_interval = poll_interval or settings.worker_poll_interval_seconds
        self.batch_size = batch_size or settings.worker_batch_size
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.processed = 0
        self.failed = 0

    async def _claim_batch(self) -> List[int]:
        """Claim a batch of PENDING comments by moving them to WAITING.

        The status transition acts as the queue claim: only one worker
        instance will pick up a given comment per poll cycle.
        """
        async with async_session_maker() as db:
            result = await db.execute(
                select(Comment.id)
                .where(Comment.status == CommentStatus.PENDING)
                .order_by(Comment.created_at.asc())
                .limit(self.batch_size)
                .with_for_update(skip_locked=True)
            )
            comment_ids = [row[0] for row in result.all()]

            if not comment_ids:
                return []

            await db.execute(
                update(Comment)
                .where(Comment.id.in_(comment_ids))
                .values(status=CommentStatus.WAITING)
            )
            await db.commit()
            return comment_ids

    async def _process_comment(self, comment_id: int) -> bool:
        """Classify a single claimed comment. Returns True on success."""
        async with async_session_maker() as db:
            try:
                await classify_comment(db=db, comment_id=comment_id, backend=None)
                self.processed += 1
                return True
            except ClassificationError:
                # classify_comment already marked the comment FAILED
                self.failed += 1
                logger.warning("Comment %s failed to classify", comment_id)
                return False
            except Exception as e:
                # Unexpected error: make sure the comment does not stay stuck
                logger.error("Unexpected worker error on comment %s: %s", comment_id, e)
                await db.rollback()
                await db.execute(
                    update(Comment)
                    .where(Comment.id == comment_id)
                    .values(
                        status=CommentStatus.FAILED,
                        error_message=f"Worker error: {e}",
                        processed_at=datetime.now(timezone.utc),
                    )
                )
                await db.commit()
                self.failed += 1
                return False

    async def run(self) -> None:
        """Main poll loop: claim batches of PENDING comments and classify them."""
        logger.info(
            "Classification worker started (poll=%.1fs, batch=%d)",
            self.poll_interval,
            self.batch_size,
        )
        while self._running:
            try:
                comment_ids = await self._claim_batch()
                if not comment_ids:
                    await asyncio.sleep(self.poll_interval)
                    continue

                logger.info("Worker claimed %d comments", len(comment_ids))
                for comment_id in comment_ids:
                    if not self._running:
                        break
                    await self._process_comment(comment_id)
                    # Yield to the event loop between comments
                    await asyncio.sleep(0)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Worker loop error: %s", e)
                await asyncio.sleep(self.poll_interval)

        logger.info("Classification worker stopped")

    def start(self) -> None:
        """Start the worker as a background task."""
        if self._task is not None and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self.run(), name="classification-worker")

    async def stop(self) -> None:
        """Stop the worker and wait for the current batch to finish."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    @property
    def is_running(self) -> bool:
        return self._running


# Module-level worker instance started by the application lifespan
worker = ClassificationWorker()
