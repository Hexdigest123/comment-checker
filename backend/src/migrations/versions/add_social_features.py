"""
Add social media account clustering and AI features.

This migration adds:
- External accounts (social media users)
- Account clusters (grouped identities)
- Cluster connections (manual linkages)
- Comment embeddings (for semantic search)
- AI conversations (chat history)
- PGVector extension for vector search
- Updated comments table with external account references
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Enums for new models
platform_enum = postgresql.ENUM(
    'twitter', 'x', 'facebook', 'instagram', 'youtube', 'tiktok',
    'reddit', 'linkedin', 'twitch', 'discord', 'telegram', 'other',
    name='platform'
)

cluster_type_enum = postgresql.ENUM(
    'person', 'organization', 'bot_network', 'troll_farm',
    'fan_club', 'spam_ring', 'unknown',
    name='clustertype'
)

discovery_method_enum = postgresql.ENUM(
    'manual', 'auto_username', 'auto_profile', 'auto_behavior', 'auto_links',
    name='discoverymethod'
)

connection_type_enum = postgresql.ENUM(
    'same_person', 'related', 'affiliated', 'coordinated',
    'shared_infrastructure', 'financial', 'family', 'employment', 'other',
    name='connectiontype'
)

connection_status_enum = postgresql.ENUM(
    'proposed', 'confirmed', 'rejected', 'disputed',
    name='connectionstatus'
)

message_role_enum = postgresql.ENUM(
    'user', 'assistant', 'system',
    name='messagerole'
)

tool_type_enum = postgresql.ENUM(
    'none', 'search', 'classify', 'export', 'move', 'summarize', 'analyze',
    name='tooltype'
)

comment_status_enum = postgresql.ENUM(
    'pending', 'processing', 'completed', 'failed', 'waiting',
    name='commentstatus'
)

classification_backend_enum = postgresql.ENUM(
    'typesafe', 'mistral', 'combined',
    name='classificationbackend'
)

classification_category_enum = postgresql.ENUM(
    'hate', 'harassment', 'violence', 'self_harm', 'sexual', 'spam', 'illegal', 'safe',
    name='classificationcategory'
)

classification_severity_enum = postgresql.ENUM(
    'low', 'medium', 'high', 'critical',
    name='classificationseverity'
)


def upgrade():
    """Create all new tables and update existing ones."""
    
    # Create enums
    platform_enum.create(op.get_bind())
    cluster_type_enum.create(op.get_bind())
    discovery_method_enum.create(op.get_bind())
    connection_type_enum.create(op.get_bind())
    connection_status_enum.create(op.get_bind())
    message_role_enum.create(op.get_bind())
    tool_type_enum.create(op.get_bind())
    comment_status_enum.create(op.get_bind())
    classification_backend_enum.create(op.get_bind())
    classification_category_enum.create(op.get_bind())
    classification_severity_enum.create(op.get_bind())

    # Enable PGVector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create external_accounts table
    op.create_table(
        'external_accounts',
        sa.Column('id', sa.String(length=36), primary_key=True, index=True),
        sa.Column('platform', platform_enum, nullable=False, index=True),
        sa.Column('platform_user_id', sa.String(length=255), index=True),
        sa.Column('username', sa.String(length=255), index=True),
        sa.Column('display_name', sa.String(length=255)),
        sa.Column('profile_url', postgresql.TEXT),
        sa.Column('avatar_url', postgresql.TEXT),
        sa.Column('bio', postgresql.TEXT),
        sa.Column('follower_count', sa.Integer),
        sa.Column('following_count', sa.Integer),
        sa.Column('post_count', sa.Integer),
        sa.Column('verified', sa.Boolean, default=False),
        sa.Column('cluster_id', sa.String(length=36), sa.ForeignKey('account_clusters.id', ondelete='SET NULL'), index=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('last_seen_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create account_clusters table
    op.create_table(
        'account_clusters',
        sa.Column('id', sa.String(length=36), primary_key=True, index=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', postgresql.TEXT),
        sa.Column('cluster_type', cluster_type_enum, nullable=False),
        sa.Column('color', sa.String(length=7), default='#666666'),
        sa.Column('icon', sa.String(length=50)),
        sa.Column('owner_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), index=True),
        sa.Column('discovery_method', discovery_method_enum, nullable=False),
        sa.Column('is_verified', sa.Boolean, default=False),
        sa.Column('comment_count', sa.Integer, default=0),
        sa.Column('toxicity_score', sa.Float, default=0.0),
        sa.Column('last_activity_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create cluster_connections table
    op.create_table(
        'cluster_connections',
        sa.Column('id', sa.String(length=36), primary_key=True, index=True),
        sa.Column('cluster_a_id', sa.String(length=36), sa.ForeignKey('account_clusters.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('cluster_b_id', sa.String(length=36), sa.ForeignKey('account_clusters.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('connection_type', connection_type_enum, nullable=False),
        sa.Column('confidence', sa.Float, nullable=False, default=0.5),
        sa.Column('status', connection_status_enum, nullable=False),
        sa.Column('evidence', postgresql.TEXT),
        sa.Column('notes', postgresql.TEXT),
        sa.Column('created_by_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), index=True),
        sa.Column('verified_at', sa.DateTime),
        sa.Column('verified_by_id', sa.String(length=36)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create comment_embeddings table
    op.create_table(
        'comment_embeddings',
        sa.Column('id', sa.String(length=36), primary_key=True, index=True),
        sa.Column('comment_id', sa.String(length=36), sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=False, index=True, unique=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=False),
        sa.Column('model', sa.String(length=50), nullable=False, default='mistral-embed'),
        sa.Column('dimension', sa.Integer, default=768),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Create ai_conversations table
    op.create_table(
        'ai_conversations',
        sa.Column('id', sa.String(length=36), primary_key=True, index=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('session_id', sa.String(length=36), index=True),
        sa.Column('role', message_role_enum, nullable=False),
        sa.Column('content', postgresql.TEXT, nullable=False),
        sa.Column('tool_used', tool_type_enum, nullable=False, default='none'),
        sa.Column('tool_input', postgresql.JSONB, default={}),
        sa.Column('tool_output', postgresql.JSONB, default={}),
        sa.Column('response_model', sa.String(length=50)),
        sa.Column('response_tokens', sa.Integer),
        sa.Column('latency_ms', sa.Integer),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Update comments table to add external account references
    with op.batch_alter_table('comments') as batch_op:
        batch_op.add_column(sa.Column('external_account_id', sa.String(length=36), sa.ForeignKey('external_accounts.id', ondelete='SET NULL'), index=True))
        batch_op.add_column(sa.Column('platform', sa.String(length=20), index=True))
        batch_op.add_column(sa.Column('platform_comment_id', sa.String(length=255), index=True))

    # Update users table to add cluster relationship
    with op.batch_alter_table('users') as batch_op:
        pass  # Relationships are handled by SQLAlchemy, not migrations

    # Create indexes for better query performance
    
    # External accounts indexes
    op.create_index(op.f('ix_external_accounts_platform_username'), 'external_accounts', ['platform', 'username'], unique=True)
    op.create_index(op.f('ix_external_accounts_cluster_id'), 'external_accounts', ['cluster_id'])
    op.create_index(op.f('ix_external_accounts_platform'), 'external_accounts', ['platform'])
    op.create_index(op.f('ix_external_accounts_username_trgm'), 'external_accounts', sa.func.indexable_text('username'), postgresql_using='gin')
    op.create_index(op.f('ix_external_accounts_bio_trgm'), 'external_accounts', sa.func.indexable_text('bio'), postgresql_using='gin')
    
    # Account clusters indexes
    op.create_index(op.f('ix_account_clusters_owner_id'), 'account_clusters', ['owner_id'])
    op.create_index(op.f('ix_account_clusters_type'), 'account_clusters', ['cluster_type'])
    op.create_index(op.f('ix_account_clusters_name_trgm'), 'account_clusters', sa.func.indexable_text('name'), postgresql_using='gin')
    
    # Cluster connections indexes
    op.create_index(op.f('ix_cluster_connections_a_b'), 'cluster_connections', ['cluster_a_id', 'cluster_b_id'], unique=True)
    op.create_index(op.f('ix_cluster_connections_status'), 'cluster_connections', ['status'])
    op.create_index(op.f('ix_cluster_connections_created_by'), 'cluster_connections', ['created_by_id'])
    
    # Comment embeddings indexes (PGVector)
    op.create_index(op.f('ix_comment_embeddings_vector'), 'comment_embeddings', sa.func.indexable_text('embedding'), postgresql_using='vector')
    op.create_index(op.f('ix_comment_embeddings_comment_id'), 'comment_embeddings', ['comment_id'])
    
    # AI conversations indexes
    op.create_index(op.f('ix_ai_conversations_user_id'), 'ai_conversations', ['user_id'])
    op.create_index(op.f('ix_ai_conversations_session_id'), 'ai_conversations', ['session_id'])
    op.create_index(op.f('ix_ai_conversations_created_at'), 'ai_conversations', ['created_at'])
    
    # Comments indexes for external account
    op.create_index(op.f('ix_comments_external_account'), 'comments', ['external_account_id'])
    op.create_index(op.f('ix_comments_platform'), 'comments', ['platform'])


def downgrade():
    """Drop all tables and columns created in the upgrade."""
    
    # Drop indexes first
    op.drop_index(op.f('ix_comments_platform'), table_name='comments')
    op.drop_index(op.f('ix_comments_external_account'), table_name='comments')
    
    op.drop_index(op.f('ix_ai_conversations_created_at'), table_name='ai_conversations')
    op.drop_index(op.f('ix_ai_conversations_session_id'), table_name='ai_conversations')
    op.drop_index(op.f('ix_ai_conversations_user_id'), table_name='ai_conversations')
    
    op.drop_index(op.f('ix_comment_embeddings_comment_id'), table_name='comment_embeddings')
    op.drop_index(op.f('ix_comment_embeddings_vector'), table_name='comment_embeddings')
    
    op.drop_index(op.f('ix_cluster_connections_created_by'), table_name='cluster_connections')
    op.drop_index(op.f('ix_cluster_connections_status'), table_name='cluster_connections')
    op.drop_index(op.f('ix_cluster_connections_a_b'), table_name='cluster_connections')
    
    op.drop_index(op.f('ix_account_clusters_name_trgm'), table_name='account_clusters')
    op.drop_index(op.f('ix_account_clusters_type'), table_name='account_clusters')
    op.drop_index(op.f('ix_account_clusters_owner_id'), table_name='account_clusters')
    
    op.drop_index(op.f('ix_external_accounts_bio_trgm'), table_name='external_accounts')
    op.drop_index(op.f('ix_external_accounts_username_trgm'), table_name='external_accounts')
    op.drop_index(op.f('ix_external_accounts_platform'), table_name='external_accounts')
    op.drop_index(op.f('ix_external_accounts_cluster_id'), table_name='external_accounts')
    op.drop_index(op.f('ix_external_accounts_platform_username'), table_name='external_accounts')
    
    # Drop tables
    op.drop_table('ai_conversations')
    op.drop_table('comment_embeddings')
    op.drop_table('cluster_connections')
    op.drop_table('account_clusters')
    op.drop_table('external_accounts')
    
    # Remove columns from comments
    with op.batch_alter_table('comments') as batch_op:
        batch_op.drop_column('platform_comment_id')
        batch_op.drop_column('platform')
        batch_op.drop_column('external_account_id')
    
    # Drop enums
    tool_type_enum.drop(op.get_bind())
    message_role_enum.drop(op.get_bind())
    connection_status_enum.drop(op.get_bind())
    connection_type_enum.drop(op.get_bind())
    discovery_method_enum.drop(op.get_bind())
    cluster_type_enum.drop(op.get_bind())
    platform_enum.drop(op.get_bind())
    classification_severity_enum.drop(op.get_bind())
    classification_category_enum.drop(op.get_bind())
    classification_backend_enum.drop(op.get_bind())
    comment_status_enum.drop(op.get_bind())
