"""redis dropout

Revision ID: 003
Revises: 002
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 3.1 Alter: orion_sessions
    op.add_column('orion_sessions', sa.Column('ws_connected_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('orion_sessions', sa.Column('ws_last_seen', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('orion_sessions', sa.Column('ws_status', sa.String(20), server_default='disconnected'))

    # 3.2 Alter: pipeline_runs
    op.add_column('pipeline_runs', sa.Column('fast_result', sa.Text(), nullable=True))
    op.add_column('pipeline_runs', sa.Column('fast_result_expires_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('pipeline_runs', sa.Column('approval_state', postgresql.JSONB(), nullable=True))
    op.add_column('pipeline_runs', sa.Column('approval_expires_at', sa.TIMESTAMP(timezone=True), nullable=True))

    # 3.3 New Table: ws_event_buffer
    op.create_table('ws_event_buffer',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(36), nullable=False, index=True),
        sa.Column('run_id', sa.String(36), nullable=True),
        sa.Column('event_json', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_ws_event_buffer_session_created', 'ws_event_buffer', ['session_id', 'created_at'])

    # 3.4 New Table: embedding_cache
    op.create_table('embedding_cache',
        sa.Column('content_hash', sa.String(64), primary_key=True),
        sa.Column('model', sa.String(100), primary_key=True),
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column('cached_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )

def downgrade() -> None:
    op.drop_table('embedding_cache')
    op.drop_index('ix_ws_event_buffer_session_created', table_name='ws_event_buffer')
    op.drop_table('ws_event_buffer')
    op.drop_column('pipeline_runs', 'approval_expires_at')
    op.drop_column('pipeline_runs', 'approval_state')
    op.drop_column('pipeline_runs', 'fast_result_expires_at')
    op.drop_column('pipeline_runs', 'fast_result')
    op.drop_column('orion_sessions', 'ws_status')
    op.drop_column('orion_sessions', 'ws_last_seen')
    op.drop_column('orion_sessions', 'ws_connected_at')
