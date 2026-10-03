"""Keep template suggestions separate from confirmed job criteria."""

from alembic import op
import sqlalchemy as sa


revision = "20261003_05"
down_revision = "20261001_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job_posts", sa.Column("draft", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_posts", "draft")
