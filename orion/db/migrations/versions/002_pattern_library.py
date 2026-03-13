"""pattern library

Revision ID: 002
Revises: 001
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('pattern_library',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('run_id', sa.String(64), nullable=False),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('pattern_type', sa.String(32), nullable=False),
        sa.Column('pattern_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('occurrence_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True)
    )
    op.create_index('idx_pattern_library_session_id', 'pattern_library', ['session_id'], unique=False)
    op.create_index('idx_pattern_library_pattern_type', 'pattern_library', ['pattern_type'], unique=False)

def downgrade() -> None:
    op.drop_index('idx_pattern_library_pattern_type', table_name='pattern_library')
    op.drop_index('idx_pattern_library_session_id', table_name='pattern_library')
    op.drop_table('pattern_library')
