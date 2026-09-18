"""
ExportComments.com API client for direct comment export integration.

This module provides programmatic access to ExportComments.com's REST API
for exporting comments from 20+ social media platforms.
"""

import os
import requests
import time
from typing import Optional, Dict, Any
from utils import logger


class ExportCommentsClient:
    """Client for interacting with ExportComments.com API."""

    BASE_URL = "https://exportcomments.com/api/v3"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the ExportComments client.
        
        Args:
            api_key: ExportComments API key. If None, reads from EXPORTCOMMENTS_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("EXPORTCOMMENTS_API_KEY")
        if not self.api_key:
            logger.warning(
                "EXPORTCOMMENTS_API_KEY not set. API calls will fail. "
                "Set via environment variable or pass to constructor."
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "CommentChecker/1.0",
        })
        if self.api_key:
            self.session.headers["X-AUTH-TOKEN"] = self.api_key

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an authenticated request to the API."""
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"ExportComments API request failed: {e}")
            raise

    def create_job(
        self,
        url: str,
        format: str = "csv",
        include_replies: bool = False,
        wait: bool = False,
        timeout: int = 300,
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Create an export job for a social media URL.
        
        Args:
            url: The URL of the social media post to export comments from.
            format: Output format - 'csv', 'xlsx', or 'json'. Default: 'csv'.
            include_replies: Whether to include reply threads. Default: False.
            wait: If True, block until job completes. Default: False.
            timeout: Maximum seconds to wait if wait=True. Default: 300 (5 min).
            poll_interval: Seconds between status checks if wait=True. Default: 2.0.
            
        Returns:
            Job information dictionary with id, guid, status, etc.
        """
        payload = {
            "url": url,
            "format": format,
            "include_replies": include_replies,
        }
        
        logger.info(f"Creating ExportComments job for: {url}")
        job = self._request("POST", "/job", json=payload)
        
        if wait:
            job = self._wait_for_completion(job, timeout=timeout, poll_interval=poll_interval)
        
        return job

    def _wait_for_completion(
        self,
        job: Dict[str, Any],
        timeout: int = 300,
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Wait for a job to complete.
        
        Args:
            job: The job dictionary from create_job.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between status checks.
            
        Returns:
            Updated job dictionary with final status.
        """
        job_id = job.get("id")
        guid = job.get("guid")
        
        if not job_id and not guid:
            raise ValueError("Job missing id or guid field")
        
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Job {job_id} timed out after {timeout}s")
            
            # Use guid if available, otherwise id
            job_identifier = guid or str(job_id)
            updated_job = self.get_job(job_identifier)
            status = updated_job.get("status", "").lower()
            
            if status in ("done", "completed", "error", "failed"):
                return updated_job
            
            logger.info(f"Job {job_id} status: {status}. Waiting {poll_interval}s...")
            time.sleep(poll_interval)

    def get_job(self, job_identifier: str) -> Dict[str, Any]:
        """Get the status of an export job.
        
        Args:
            job_identifier: The job ID or GUID.
            
        Returns:
            Job information dictionary.
        """
        return self._request("GET", f"/job/{job_identifier}")

    def download_job(
        self,
        job_identifier: str,
        output_path: Optional[str] = None,
    ) -> bytes:
        """Download the results of a completed export job.
        
        Args:
            job_identifier: The job ID or GUID.
            output_path: Optional path to save the file. If provided, saves to disk.
            
        Returns:
            The raw bytes of the exported file.
        """
        response = self.session.get(
            f"{self.BASE_URL}/job/{job_identifier}/download",
            stream=True,
        )
        response.raise_for_status()
        
        content = response.content
        
        if output_path:
            with open(output_path, "wb") as f:
                f.write(content)
            logger.info(f"Saved export to: {output_path}")
        
        return content

    def export_to_csv(
        self,
        url: str,
        output_path: str,
        include_replies: bool = False,
        wait: bool = True,
        timeout: int = 300,
        poll_interval: float = 2.0,
    ) -> str:
        """Convenience method to export comments directly to a CSV file.
        
        This is the recommended method for most use cases.
        
        Args:
            url: The URL of the social media post.
            output_path: Path to save the CSV file.
            include_replies: Whether to include reply threads.
            wait: Whether to wait for completion. Default: True.
            timeout: Maximum seconds to wait. Default: 300.
            poll_interval: Seconds between status checks. Default: 2.0.
            
        Returns:
            The path to the saved CSV file.
        """
        job = self.create_job(
            url=url,
            format="csv",
            include_replies=include_replies,
            wait=wait,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        
        job_id = job.get("id")
        guid = job.get("guid")
        job_identifier = guid or str(job_id)
        
        # Download the results
        self.download_job(job_identifier, output_path)
        
        return output_path
