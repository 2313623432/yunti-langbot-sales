"""add sales resource issue tickets

Revision ID: 0009_sales_resource_issues
Revises: 0008_sales_product_line
Create Date: 2026-06-12
"""

import sqlalchemy as sa
from alembic import op

revision = '0009_sales_resource_issues'
down_revision = '0008_sales_product_line'
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in set(inspector.get_table_names())


def upgrade() -> None:
    if _has_table('sales_resource_issues'):
        return

    op.create_table(
        'sales_resource_issues',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(255), nullable=False, index=True),
        sa.Column('bot_uuid', sa.String(255), nullable=False, server_default='', index=True),
        sa.Column('pipeline_uuid', sa.String(255), nullable=False, server_default='', index=True),
        sa.Column('target_type', sa.String(32), nullable=False, server_default='person'),
        sa.Column('target_id', sa.String(255), nullable=False, server_default='', index=True),
        sa.Column('platform', sa.String(255), nullable=False, server_default=''),
        sa.Column('user_id', sa.String(255), nullable=False, server_default=''),
        sa.Column('user_name', sa.String(255), nullable=False, server_default=''),
        sa.Column('status', sa.String(32), nullable=False, server_default='open', index=True),
        sa.Column('issue_type', sa.String(64), nullable=False, server_default='resource_error', index=True),
        sa.Column('book_id', sa.String(255), nullable=False, server_default='', index=True),
        sa.Column('merchant', sa.String(255), nullable=False, server_default='', index=True),
        sa.Column('question_location', sa.String(512), nullable=False, server_default=''),
        sa.Column('issue_summary', sa.Text, nullable=False, server_default=''),
        sa.Column('user_description', sa.Text, nullable=False, server_default=''),
        sa.Column('evidence_images', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('internal_note', sa.Text, nullable=False, server_default=''),
        sa.Column('operator', sa.String(255), nullable=False, server_default=''),
        sa.Column('resolution_note', sa.Text, nullable=False, server_default=''),
        sa.Column('completion_reply', sa.Text, nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('replied_at', sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    if _has_table('sales_resource_issues'):
        op.drop_table('sales_resource_issues')
