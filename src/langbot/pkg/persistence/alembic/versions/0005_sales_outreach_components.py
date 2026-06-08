"""add sales outreach message components

Revision ID: 0005_sales_outreach_components
Revises: 0004_sales_system
Create Date: 2026-06-08
"""

import sqlalchemy as sa
from alembic import op

revision = '0005_sales_outreach_components'
down_revision = '0004_sales_system'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column_name in {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column('sales_outreach_plans', 'dedupe_key'):
        op.add_column(
            'sales_outreach_plans',
            sa.Column('dedupe_key', sa.String(255), nullable=False, server_default=''),
        )
        op.create_index(
            'ix_sales_outreach_plans_dedupe_key',
            'sales_outreach_plans',
            ['dedupe_key'],
        )

    if not _has_column('sales_outreach_plans', 'message_components'):
        op.add_column(
            'sales_outreach_plans',
            sa.Column('message_components', sa.JSON(), nullable=False, server_default='[]'),
        )


def downgrade() -> None:
    if _has_column('sales_outreach_plans', 'message_components'):
        op.drop_column('sales_outreach_plans', 'message_components')
    if _has_column('sales_outreach_plans', 'dedupe_key'):
        op.drop_index('ix_sales_outreach_plans_dedupe_key', table_name='sales_outreach_plans')
        op.drop_column('sales_outreach_plans', 'dedupe_key')
