"""add auto test runs

Revision ID: 0010_auto_test_runs
Revises: 0009_sales_resource_issues, 0009_auto_test_runs
Create Date: 2026-06-12
"""

import sqlalchemy as sa
from alembic import op

revision = '0010_auto_test_runs'
down_revision = ('0009_sales_resource_issues', '0009_auto_test_runs')
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _has_table('auto_test_runs'):
        return

    op.create_table(
        'auto_test_runs',
        sa.Column('uuid', sa.String(255), primary_key=True, unique=True),
        sa.Column('target_type', sa.String(32), nullable=False),
        sa.Column('target_uuid', sa.String(255), nullable=False),
        sa.Column('target_name', sa.String(255), nullable=False, server_default=''),
        sa.Column('status', sa.String(32), nullable=False, server_default='completed'),
        sa.Column('scenario', sa.Text(), nullable=False, server_default=''),
        sa.Column('messages', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('evaluation', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('user_feedback', sa.String(32), nullable=False, server_default=''),
        sa.Column('feedback_reason', sa.Text(), nullable=False, server_default=''),
        sa.Column('optimization_summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('optimization_patch', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_auto_test_runs_target_type', 'auto_test_runs', ['target_type'])
    op.create_index('ix_auto_test_runs_target_uuid', 'auto_test_runs', ['target_uuid'])
    op.create_index('ix_auto_test_runs_status', 'auto_test_runs', ['status'])


def downgrade() -> None:
    if not _has_table('auto_test_runs'):
        return

    op.drop_index('ix_auto_test_runs_status', table_name='auto_test_runs')
    op.drop_index('ix_auto_test_runs_target_uuid', table_name='auto_test_runs')
    op.drop_index('ix_auto_test_runs_target_type', table_name='auto_test_runs')
    op.drop_table('auto_test_runs')
