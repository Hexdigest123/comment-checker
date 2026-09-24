"""Tests for the ExportComments column mapping during CSV ingestion.

The ExportComments export layout must map onto the right model fields:
the Comment URL is the direct permalink to the comment (not the profile
URL), Date is when the comment was written (posted_at), and columns the
mapping does not know are preserved in extra_metadata instead of being
dropped.
"""

import io
from datetime import datetime

import pytest
from fastapi import UploadFile
from sqlalchemy import select

from src.db.models import Comment
from src.services.csv_processor import process_csv_file

# Raw ExportComments layout (as in assets/data2-clean.csv)
EXPORTCOMMENTS_CSV = (
    "Name,Username,Profile ID,Date,Likes,Comment,User Verified,"
    "Comment ID,Profile URL,Comment URL\n"
    "Test User,testuser,12345,2026-06-01 22:41:57,3,Hello there,no,"
    "18067525943382979,https://www.instagram.com/testuser,"
    "https://www.instagram.com/p/DZDH8YstgWl/c/18067525943382979\n"
)


def _upload_file(content: str) -> UploadFile:
    return UploadFile(filename="test.csv", file=io.BytesIO(content.encode("utf-8")))


class TestExportCommentsMapping:
    """Tests for ExportComments column mapping in process_csv_file."""

    @pytest.mark.asyncio
    async def test_comment_url_lands_in_source_url(self, db_session):
        """source_url must be the comment permalink, not the profile URL."""
        result = await process_csv_file(
            db_session, _upload_file(EXPORTCOMMENTS_CSV), user_id=1
        )
        comment = (
            await db_session.execute(select(Comment))
        ).scalars().one()

        assert comment.source_url == (
            "https://www.instagram.com/p/DZDH8YstgWl/c/18067525943382979"
        )
        assert result["valid_rows"] == 1

    @pytest.mark.asyncio
    async def test_author_fields_are_populated(self, db_session):
        """Author handle, profile ID and profile URL map to the author fields."""
        await process_csv_file(db_session, _upload_file(EXPORTCOMMENTS_CSV), user_id=1)
        comment = (
            await db_session.execute(select(Comment))
        ).scalars().one()

        assert comment.original_author == "testuser"
        assert comment.original_author_id == "12345"
        assert comment.original_author_url == "https://www.instagram.com/testuser"

    @pytest.mark.asyncio
    async def test_date_maps_to_posted_at(self, db_session):
        """The export Date must become posted_at, not be confused with created_at."""
        await process_csv_file(db_session, _upload_file(EXPORTCOMMENTS_CSV), user_id=1)
        comment = (
            await db_session.execute(select(Comment))
        ).scalars().one()

        assert comment.posted_at == datetime(2026, 6, 1, 22, 41, 57)
        assert comment.created_at != comment.posted_at

    @pytest.mark.asyncio
    async def test_likes_and_comment_id_are_stored(self, db_session):
        """Likes land in metadata; Comment ID lands in platform_comment_id."""
        await process_csv_file(db_session, _upload_file(EXPORTCOMMENTS_CSV), user_id=1)
        comment = (
            await db_session.execute(select(Comment))
        ).scalars().one()

        assert comment.platform_comment_id == "18067525943382979"
        assert comment.extra_metadata["likes"] == 3

    @pytest.mark.asyncio
    async def test_unmapped_columns_are_preserved_in_metadata(self, db_session):
        """Columns without a mapping must be kept in metadata, not dropped."""
        await process_csv_file(db_session, _upload_file(EXPORTCOMMENTS_CSV), user_id=1)
        comment = (
            await db_session.execute(select(Comment))
        ).scalars().one()

        source_columns = comment.extra_metadata["source_columns"]
        assert source_columns["User Verified"] == "no"

    @pytest.mark.asyncio
    async def test_link_still_used_as_source_url_without_comment_url(self, db_session):
        """CSVs with only a profile link keep the previous source_url behaviour."""
        content = (
            "text,username,link\n"
            "hello world,john,https://twitter.com/john\n"
        )
        await process_csv_file(db_session, _upload_file(content), user_id=1)
        comment = (
            await db_session.execute(select(Comment))
        ).scalars().one()

        assert comment.source_url == "https://twitter.com/john"
