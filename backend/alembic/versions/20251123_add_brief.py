"""add_research_brief_columns

Revision ID: 20251123_add_brief
Revises: 58644be7a57b
Create Date: 2025-11-23 06:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251123_add_brief'
down_revision = 'a18512cd709f'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to threads table
    op.add_column('threads', sa.Column('target_audience', sa.String(), nullable=True))
    op.add_column('threads', sa.Column('research_guidelines', sa.Text(), nullable=True))
    op.add_column('threads', sa.Column('extra_context', sa.Text(), nullable=True))


def downgrade():
    # Remove columns from threads table
    op.drop_column('threads', 'extra_context')
    op.drop_column('threads', 'research_guidelines')
    op.drop_column('threads', 'target_audience')
