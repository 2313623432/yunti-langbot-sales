"""add AI sales system tables

Revision ID: 0004_sales_system
Revises: 0003_add_rerank_models
Create Date: 2026-05-28
"""

import sqlalchemy as sa
from alembic import op

revision = '0004_sales_system'
down_revision = '0003_add_rerank_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if 'sales_products' not in tables:
        op.create_table(
            'sales_products',
            sa.Column('uuid', sa.String(255), primary_key=True, unique=True),
            sa.Column('name', sa.String(255), nullable=False, index=True),
            sa.Column('category', sa.String(255), nullable=False, server_default=''),
            sa.Column('price', sa.String(255), nullable=False, server_default=''),
            sa.Column('link', sa.String(1024), nullable=False, server_default=''),
            sa.Column('description', sa.Text, nullable=False, server_default=''),
            sa.Column('selling_points', sa.JSON, nullable=False),
            sa.Column('pain_points', sa.JSON, nullable=False),
            sa.Column('objections', sa.JSON, nullable=False),
            sa.Column('audience', sa.JSON, nullable=False),
            sa.Column('enabled', sa.Boolean, nullable=False, server_default=sa.true(), index=True),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

    if 'sales_customer_memories' not in tables:
        op.create_table(
            'sales_customer_memories',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('session_id', sa.String(255), nullable=False, unique=True, index=True),
            sa.Column('platform', sa.String(255), nullable=False, server_default=''),
            sa.Column('user_id', sa.String(255), nullable=False, server_default=''),
            sa.Column('customer_name', sa.String(255), nullable=False, server_default=''),
            sa.Column('summary', sa.Text, nullable=False, server_default=''),
            sa.Column('stage', sa.String(64), nullable=False, server_default='new'),
            sa.Column('last_intent', sa.String(64), nullable=False, server_default='unknown'),
            sa.Column('preferred_product_uuid', sa.String(255), nullable=False, server_default=''),
            sa.Column('profile', sa.JSON, nullable=False),
            sa.Column('intents', sa.JSON, nullable=False),
            sa.Column('last_seen_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

    if 'sales_handoffs' not in tables:
        op.create_table(
            'sales_handoffs',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('session_id', sa.String(255), nullable=False, index=True),
            sa.Column('bot_uuid', sa.String(255), nullable=False, server_default=''),
            sa.Column('target_type', sa.String(32), nullable=False, server_default='person'),
            sa.Column('target_id', sa.String(255), nullable=False, server_default=''),
            sa.Column('platform', sa.String(255), nullable=False, server_default=''),
            sa.Column('user_id', sa.String(255), nullable=False, server_default=''),
            sa.Column('status', sa.String(32), nullable=False, server_default='open', index=True),
            sa.Column('reason', sa.String(512), nullable=False, server_default=''),
            sa.Column('last_message', sa.Text, nullable=False, server_default=''),
            sa.Column('operator_reply', sa.Text, nullable=False, server_default=''),
            sa.Column('assigned_to', sa.String(255), nullable=False, server_default=''),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )

    if 'sales_outreach_plans' not in tables:
        op.create_table(
            'sales_outreach_plans',
            sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('product_uuid', sa.String(255), nullable=False, server_default=''),
            sa.Column('bot_uuid', sa.String(255), nullable=False, server_default=''),
            sa.Column('target_type', sa.String(32), nullable=False, server_default='person'),
            sa.Column('target_id', sa.String(255), nullable=False, server_default=''),
            sa.Column('segment', sa.String(255), nullable=False, server_default=''),
            sa.Column('message_template', sa.Text, nullable=False, server_default=''),
            sa.Column('scheduled_at', sa.DateTime, nullable=True),
            sa.Column('interval_minutes', sa.Integer, nullable=False, server_default='0'),
            sa.Column('enabled', sa.Boolean, nullable=False, server_default=sa.true(), index=True),
            sa.Column('last_sent_at', sa.DateTime, nullable=True),
            sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table('sales_outreach_plans')
    op.drop_table('sales_handoffs')
    op.drop_table('sales_customer_memories')
    op.drop_table('sales_products')
