"""Anchor candidate chats to a published job.

Revision ID: 20260929_03
Revises: 20260929_02
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260929_03"
down_revision = "20260929_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.add_column(sa.Column("target_job_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_chats_target_job_id_job_posts",
            "job_posts",
            ["target_job_id"],
            ["id"],
        )
        batch_op.create_index("ix_chats_target_job_id", ["target_job_id"])


def downgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.drop_index("ix_chats_target_job_id")
        batch_op.drop_constraint("fk_chats_target_job_id_job_posts", type_="foreignkey")
        batch_op.drop_column("target_job_id")
