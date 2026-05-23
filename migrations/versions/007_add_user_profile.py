"""Add profile fields to users

Revision ID: 007
Revises: 006
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('company', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('socials', sa.Text(), nullable=True))  # JSON string
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('users', 'bio')
    op.drop_column('users', 'socials')
    op.drop_column('users', 'company')
