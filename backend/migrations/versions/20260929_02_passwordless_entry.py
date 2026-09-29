"""Add recruiter approval and passwordless login codes.

Revision ID: 20260929_02
Revises: 20260929_01
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260929_02"
down_revision = "20260929_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), server_default="recruiter", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("approval_status", sa.String(length=20), server_default="approved", nullable=False),
    )
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_approval_status", "users", ["approval_status"])
    op.drop_table("user_credentials")
    op.create_table(
        "recruiter_login_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recruiter_login_codes_user_id", "recruiter_login_codes", ["user_id"])
    op.create_index("ix_recruiter_login_codes_code_hash", "recruiter_login_codes", ["code_hash"])
    op.create_index("ix_recruiter_login_codes_expires_at", "recruiter_login_codes", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_recruiter_login_codes_expires_at", table_name="recruiter_login_codes")
    op.drop_index("ix_recruiter_login_codes_code_hash", table_name="recruiter_login_codes")
    op.drop_index("ix_recruiter_login_codes_user_id", table_name="recruiter_login_codes")
    op.drop_table("recruiter_login_codes")
    op.create_table(
        "user_credentials",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.drop_index("ix_users_approval_status", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "approval_status")
    op.drop_column("users", "role")
