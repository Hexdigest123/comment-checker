"""Tests for duplicate detection during CSV/ExportComments ingestion.

Ingested comments must be checked against existing comments before any
AI tooling (classification, embeddings) runs on them, so re-importing
the same CSV or re-running the same ExportComments export does not
create duplicates.
"""

import io

import pytest
from fastapi import UploadFile

from src.services.csv_processor import process_csv_file

CSV_CONTENT = (
    "text,username,link\n"
    "hello world,john,https://twitter.com/john\n"
    "great post,jane,https://twitter.com/jane\n"
)


def _upload_file(content: str) -> UploadFile:
    return UploadFile(filename="test.csv", file=io.BytesIO(content.encode("utf-8")))


class TestCSVDuplicateDetection:
    """Tests for duplicate skipping in process_csv_file."""

    @pytest.mark.asyncio
    async def test_reingest_same_csv_skips_duplicates(self, db_session):
        """Re-ingesting the same CSV must not create duplicate comments."""
        first = await process_csv_file(db_session, _upload_file(CSV_CONTENT), user_id=1)
        assert first["valid_rows"] == 2
        assert first["invalid_rows"] == 0
        assert first["duplicates_skipped"] == 0
        assert len(first["comments"]) == 2

        second = await process_csv_file(db_session, _upload_file(CSV_CONTENT), user_id=1)
        assert second["total_rows"] == 2
        assert second["valid_rows"] == 0
        assert second["duplicates_skipped"] == 2
        assert second["comments"] == []

    @pytest.mark.asyncio
    async def test_duplicates_within_same_file_are_skipped(self, db_session):
        """Identical rows inside one CSV must only be ingested once."""
        content = (
            "text,username,link\n"
            "hello world,john,https://twitter.com/john\n"
            "HELLO   world,john,https://twitter.com/john\n"
        )

        result = await process_csv_file(db_session, _upload_file(content), user_id=1)
        assert result["valid_rows"] == 1
        assert result["duplicates_skipped"] == 1

    @pytest.mark.asyncio
    async def test_same_text_different_author_is_not_duplicate(self, db_session):
        """The same comment text by a different author is a new comment."""
        content = (
            "text,username,link\n"
            "hello world,john,https://twitter.com/john\n"
            "hello world,alice,https://twitter.com/alice\n"
        )

        result = await process_csv_file(db_session, _upload_file(content), user_id=1)
        assert result["valid_rows"] == 2
        assert result["duplicates_skipped"] == 0

    @pytest.mark.asyncio
    async def test_duplicates_are_scoped_per_user(self, db_session):
        """The same comment ingested by another user is not a duplicate."""
        first = await process_csv_file(db_session, _upload_file(CSV_CONTENT), user_id=1)
        assert first["valid_rows"] == 2

        second = await process_csv_file(db_session, _upload_file(CSV_CONTENT), user_id=2)
        assert second["valid_rows"] == 2
        assert second["duplicates_skipped"] == 0

    @pytest.mark.asyncio
    async def test_duplicate_rows_skip_account_and_cluster_creation(self, db_session):
        """Duplicate rows must not create external accounts or clusters."""
        first = await process_csv_file(db_session, _upload_file(CSV_CONTENT), user_id=1)
        accounts_after_first = first["accounts_created"]

        second = await process_csv_file(db_session, _upload_file(CSV_CONTENT), user_id=1)
        assert second["accounts_created"] == 0
        assert accounts_after_first > 0
