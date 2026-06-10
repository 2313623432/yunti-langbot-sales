"""add sales product line fields

Revision ID: 0008_sales_product_line
Revises: 0007_workflow_seed_state
Create Date: 2026-06-10
"""

import sqlalchemy as sa
from alembic import op

revision = '0008_sales_product_line'
down_revision = '0007_workflow_seed_state'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column_name in {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column('sales_products', 'product_line'):
        op.add_column(
            'sales_products',
            sa.Column('product_line', sa.String(255), nullable=False, server_default=''),
        )
    if not _has_column('sales_products', 'profile_key'):
        op.add_column(
            'sales_products',
            sa.Column('profile_key', sa.String(255), nullable=False, server_default=''),
        )
    if not _has_column('sales_products', 'keywords'):
        op.add_column(
            'sales_products',
            sa.Column('keywords', sa.JSON(), nullable=False, server_default='[]'),
        )


def downgrade() -> None:
    if _has_column('sales_products', 'keywords'):
        op.drop_column('sales_products', 'keywords')
    if _has_column('sales_products', 'profile_key'):
        op.drop_column('sales_products', 'profile_key')
    if _has_column('sales_products', 'product_line'):
        op.drop_column('sales_products', 'product_line')
