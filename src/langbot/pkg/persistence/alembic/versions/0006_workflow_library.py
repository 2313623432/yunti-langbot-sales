"""add workflow library tables

Revision ID: 0006_workflow_library
Revises: 0005_sales_outreach_components
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from alembic import op

revision = '0006_workflow_library'
down_revision = '0005_sales_outreach_components'
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table('workflow_folders'):
        op.create_table(
            'workflow_folders',
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('name'),
            sa.UniqueConstraint('name'),
        )

    if not _has_table('workflow_projects'):
        op.create_table(
            'workflow_projects',
            sa.Column('uuid', sa.String(length=255), nullable=False),
            sa.Column('folder', sa.String(length=255), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('workflow', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('uuid'),
            sa.UniqueConstraint('uuid'),
        )
        op.create_index('ix_workflow_projects_folder', 'workflow_projects', ['folder'])
        op.create_index('ix_workflow_projects_name', 'workflow_projects', ['name'])


def downgrade() -> None:
    if _has_table('workflow_projects'):
        op.drop_index('ix_workflow_projects_name', table_name='workflow_projects')
        op.drop_index('ix_workflow_projects_folder', table_name='workflow_projects')
        op.drop_table('workflow_projects')
    if _has_table('workflow_folders'):
        op.drop_table('workflow_folders')
