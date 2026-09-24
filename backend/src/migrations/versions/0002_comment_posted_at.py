"""Add posted_at to comments: the date the comment was written on the
source platform, as provided by the export (CSV 'Date' column). Distinct
from created_at, which records when the row was ingested.

Revision ID: 0002_comment_posted_at
Revises: 0001_baseline
Create Date: 2026-09-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_comment_posted_at'
down_revision: Union[str, None] = '0001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'comments',
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('comments', 'posted_at')
