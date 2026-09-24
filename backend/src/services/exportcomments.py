"""
ExportComments.com integration service for the backend.

Creates an export job for a social media URL via the ExportComments REST API,
waits for completion, downloads the CSV result, and feeds it into the regular
CSV processing pipeline (external accounts, clustering, embeddings, and the
classification worker queue).
"""

import asyncio
import logging
from io import BytesIO
from typing import Any, Dict, Optional

import httpx
from fastapi import UploadFile

from ..config import get_settings
from ..db.session import async_session_maker
from .csv_processor import process_csv_file

settings = get_settings()

logger = logging.getLogger(__name__)


class ExportCommentsError(Exception):
    """Raised when the ExportComments API call fails or is misconfigured."""


class ExportCommentsClient:
    """Async client for the ExportComments.com API (v3)."""

    BASE_URL = "https://exportcomments.com/api/v3"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.exportcomments_api_key
        if not self.api_key:
            raise ExportCommentsError(
                "ExportComments API key is not configured. "
                "Set EXPORTCOMMENTS_API_KEY in the environment."
            )
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CommentChecker/1.0",
                "X-AUTH-TOKEN": self.api_key,
            },
        )

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "ExportComments API error: %s - %s",
                e.response.status_code,
                e.response.text,
            )
            raise ExportCommentsError(
                f"ExportComments API error: {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            logger.error("ExportComments API request failed: %s", e)
            raise ExportCommentsError(f"ExportComments API unreachable: {e}") from e

    async def create_job(
        self,
        url: str,
        output_format: str = "csv",
        include_replies: bool = False,
    ) -> Dict[str, Any]:
        """Create an export job for a social media URL."""
        payload = {
            "url": url,
            "format": output_format,
            "include_replies": include_replies,
        }
        logger.info("Creating ExportComments job for: %s", url)
        return await self._request("POST", "/job", json=payload)

    async def get_job(self, job_identifier: str) -> Dict[str, Any]:
        """Get the status of an export job."""
        return await self._request("GET", f"/job/{job_identifier}")

    async def wait_for_completion(
        self,
        job: Dict[str, Any],
        timeout: int = 300,
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Poll a job until it completes or the timeout is reached."""
        job_id = job.get("id")
        guid = job.get("guid")
        if not job_id and not guid:
            raise ExportCommentsError("Job missing id or guid field")

        job_identifier = guid or str(job_id)
        elapsed = 0.0
        while elapsed < timeout:
            updated = await self.get_job(job_identifier)
            status = str(updated.get("status", "")).lower()
            if status in ("done", "completed"):
                return updated
            if status in ("error", "failed"):
                raise ExportCommentsError(
                    f"ExportComments job failed: {updated.get('message', status)}"
                )
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise ExportCommentsError(f"ExportComments job timed out after {timeout}s")

    async def download_job(self, job_identifier: str) -> bytes:
        """Download the CSV result of a completed job."""
        response = await self.client.get(
            f"{self.BASE_URL}/job/{job_identifier}/download"
        )
        response.raise_for_status()
        return response.content

    async def close(self) -> None:
        await self.client.aclose()


async def import_from_url(
    url: str,
    user_id: int,
    context: Optional[str] = None,
    include_replies: bool = False,
    timeout: int = 300,
    max_comments: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run the full import flow: create job, wait, download, ingest comments.

    This is executed as a background task by the import API endpoint.
    Comments are created with status PENDING and are picked up by the
    classification worker.
    """
    import uuid

    client = ExportCommentsClient()
    batch_id = str(uuid.uuid4())
    try:
        job = await client.create_job(url=url, include_replies=include_replies)
        job = await client.wait_for_completion(job, timeout=timeout)
        job_identifier = job.get("guid") or str(job.get("id"))
        content = await client.download_job(job_identifier)
    finally:
        await client.close()

    import csv as csv_module
    import io

    # Ensure the context is attached to every comment if provided
    text_content = content.decode("utf-8", errors="replace")
    if context:
        reader = csv_module.DictReader(io.StringIO(text_content))
        fieldnames = reader.fieldnames or []
        if "context" not in [f.strip().lower() for f in fieldnames]:
            fieldnames = list(fieldnames) + ["context"]
        rows = []
        for row in reader:
            row["context"] = context
            rows.append(row)
        out = io.StringIO()
        writer = csv_module.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        text_content = out.getvalue()

    if max_comments:
        reader = csv_module.DictReader(io.StringIO(text_content))
        rows = list(reader)[:max_comments]
        out = io.StringIO()
        writer = csv_module.DictWriter(out, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        text_content = out.getvalue()

    upload_file = UploadFile(filename="exportcomments.csv", file=BytesIO(text_content.encode("utf-8")))

    async with async_session_maker() as db:
        result = await process_csv_file(
            db=db,
            file=upload_file,
            user_id=user_id,
            batch_id=batch_id,
        )

    logger.info(
        "ExportComments import finished: %d comments from %s",
        result["valid_rows"],
        url,
    )
    return {
        "batch_id": batch_id,
        "export_job_id": job_identifier,
        "url": url,
        **result,
    }
