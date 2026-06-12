"""workflow seed state revision marker

Revision ID: 0007_workflow_seed_state
Revises: 0006_workflow_library
Create Date: 2026-06-09 17:40:00
"""

from collections.abc import Sequence


revision: str = '0007_workflow_seed_state'
down_revision: str | Sequence[str] | None = '0006_workflow_library'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
