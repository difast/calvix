"""add analytics_events table and fix bookings

Revision ID: 003
Revises: 002
Create Date: 2025-01-15

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS analytics_events ("
        "id SERIAL PRIMARY KEY, "
        "business_id INTEGER, "
        "lead_id INTEGER, "
        "event_type VARCHAR(100) NOT NULL, "
        "metadata TEXT, "
        "created_at TIMESTAMP DEFAULT now()"
        ")"
    ))

    # lead_id в bookings сделаем nullable (если запись без лида)
    op.execute(sa.text(
        "ALTER TABLE bookings ALTER COLUMN lead_id DROP NOT NULL"
    ))


def downgrade() -> None:
    op.drop_table("analytics_events")
