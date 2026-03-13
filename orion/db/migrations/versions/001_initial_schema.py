"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import os
import sqlite3
from pathlib import Path

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # First line
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table('orion_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('mode', sa.String(), nullable=False),
        sa.Column('active_provider', sa.String(), nullable=True),
        sa.Column('tab_state', sa.JSON(), nullable=False),
        sa.Column('permissions', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_active_at', sa.DateTime(), nullable=True)
    )

    op.create_table('pipeline_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orion_sessions.id'), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('mode', sa.String(), nullable=False),
        sa.Column('raw_prompt', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('cost_estimate', sa.Float(), nullable=True),
        sa.Column('cost_actual', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.String(), nullable=True),
        sa.UniqueConstraint('run_id')
    )

    op.create_table('checkpoints',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', sa.String(), sa.ForeignKey('pipeline_runs.run_id'), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('files_snapshot', sa.JSON(), nullable=False),
        sa.Column('pipeline_state', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table('iisg_contracts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('contract_hash', sa.String(), nullable=False),
        sa.Column('clauses', sa.JSON(), nullable=False),
        sa.Column('approved_by_user', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table('agent_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('agent_role', sa.String(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('file_changes', sa.JSON(), nullable=False),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table('validation_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('layers', sa.JSON(), nullable=False),
        sa.Column('total_duration_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    op.create_table('memory_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('embedding', sa.String(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        op.execute("ALTER TABLE memory_entries ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector;")

    op.create_table('cost_tracking',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('tokens_in', sa.Integer(), nullable=False),
        sa.Column('tokens_out', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    db_path = Path(os.path.expanduser("~/.orion/memories.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def downgrade() -> None:
    op.drop_table('cost_tracking')
    op.drop_table('memory_entries')
    op.drop_table('validation_results')
    op.drop_table('agent_executions')
    op.drop_table('iisg_contracts')
    op.drop_table('checkpoints')
    op.drop_table('pipeline_runs')
    op.drop_table('orion_sessions')
    op.execute("DROP EXTENSION IF EXISTS vector;")
