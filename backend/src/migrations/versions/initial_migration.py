"""Initial database migration for Comment Checker application."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None

# These values are used by the trigram index for efficient text search
# They must be installed in the database before this migration can be applied
# Run: CREATE EXTENSION IF NOT EXISTS pg_trgm; in your PostgreSQL database

# Enums
classification_backend_enum = postgresql.ENUM('typesafe', 'mistral', 'combined', name='classificationbackend')
classification_category_enum = postgresql.ENUM(
    'hate', 'harassment', 'violence', 'self_harm', 'sexual', 'spam', 'illegal', 'safe', name='classificationcategory'
)
classification_severity_enum = postgresql.ENUM('low', 'medium', 'high', 'critical', name='classificationseverity')
comment_status_enum = postgresql.ENUM('pending', 'processing', 'completed', 'failed', 'waiting', name='commentstatus')


def upgrade():
    """Create all tables and indexes for the Comment Checker application."""
    classification_backend_enum.create(op.get_bind())
    classification_category_enum.create(op.get_bind())
    classification_severity_enum.create(op.get_bind())
    comment_status_enum.create(op.get_bind())

    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), primary_key=True, index=True),
        sa.Column('username', sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.String(length=36), primary_key=True, index=True),
        sa.Column('token', sa.String(length=512), nullable=False, unique=True, index=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'comments',
        sa.Column('id', sa.String(length=36), primary_key=True, index=True),
        sa.Column('text', postgresql.TEXT(), nullable=False),
        sa.Column('source_url', postgresql.TEXT(), nullable=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('status', comment_status_enum, nullable=False, default='pending', index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        'classifications',
        sa.Column('id', sa.String(length=36), primary_key=True, index=True),
        sa.Column('comment_id', sa.String(length=36), sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('backend', classification_backend_enum, nullable=False, index=True),
        sa.Column('category', classification_category_enum, nullable=False, index=True),
        sa.Column('severity', classification_severity_enum, nullable=False, index=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('harmful_score', sa.Float(), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=False, default={}),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_index(op.f('ix_comments_text_trgm'), 'comments', sa.func.indexable_text('text'), postgresql_using='gin')
    op.create_index(op.f('ix_comments_status'), 'comments', ['status'])
    op.create_index(op.f('ix_comments_user_id'), 'comments', ['user_id'])
    op.create_index(op.f('ix_comments_created_at'), 'comments', ['created_at'])
    
    op.create_index(op.f('ix_classifications_comment_id'), 'classifications', ['comment_id'])
    op.create_index(op.f('ix_classifications_backend'), 'classifications', ['backend'])
    op.create_index(op.f('ix_classifications_category'), 'classifications', ['category'])
    op.create_index(op.f('ix_classifications_severity'), 'classifications', ['severity'])
    op.create_index(op.f('ix_classifications_created_at'), 'classifications', ['created_at'])
    
    op.create_index(op.f('ix_refresh_tokens_token'), 'refresh_tokens', ['token'])
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'])
    op.create_index(op.f('ix_refresh_tokens_expires_at'), 'refresh_tokens', ['expires_at'])


def downgrade():
    """Drop all tables created in the upgrade."""

    # Drop indexes first (optional, as they will be dropped with tables)
    op.drop_index(op.f('ix_refresh_tokens_expires_at'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_token'), table_name='refresh_tokens')
    
    op.drop_index(op.f('ix_classifications_created_at'), table_name='classifications')
    op.drop_index(op.f('ix_classifications_severity'), table_name='classifications')
    op.drop_index(op.f('ix_classifications_category'), table_name='classifications')
    op.drop_index(op.f('ix_classifications_backend'), table_name='classifications')
    op.drop_index(op.f('ix_classifications_comment_id'), table_name='classifications')
    
    op.drop_index(op.f('ix_comments_created_at'), table_name='comments')
    op.drop_index(op.f('ix_comments_user_id'), table_name='comments')
    op.drop_index(op.f('ix_comments_status'), table_name='comments')
    op.drop_index(op.f('ix_comments_text_trgm'), table_name='comments')

    # Drop tables
    op.drop_table('refresh_tokens')
    op.drop_table('classifications')
    op.drop_table('comments')
    op.drop_table('users')

    # Drop enums
    comment_status_enum.drop(op.get_bind())
    classification_severity_enum.drop(op.get_bind())
    classification_category_enum.drop(op.get_bind())
    classification_backend_enum.drop(op.get_bind())
