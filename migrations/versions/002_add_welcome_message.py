"""add welcome_message to businesses

Revision ID: 002
Revises: 001
Create Date: 2025-01-15

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS welcome_message TEXT"
    ))


def downgrade() -> None:
    op.drop_column("businesses", "welcome_message")
