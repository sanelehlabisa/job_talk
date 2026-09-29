"""Create the initial Job Talk schema.

Revision ID: 20260929_01
Revises:
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260929_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True, if_not_exists=True)

    op.create_table(
        "user_credentials",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
        if_not_exists=True,
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"], if_not_exists=True)
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True, if_not_exists=True)
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], if_not_exists=True)

    op.create_table(
        "chats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("intent", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index("ix_chats_user_id", "chats", ["user_id"], if_not_exists=True)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("sender", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"]),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index("ix_messages_chat_id", "messages", ["chat_id"], if_not_exists=True)

    op.create_table(
        "job_posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_profile", sa.JSON(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id"),
        if_not_exists=True,
    )
    op.create_index("ix_job_posts_published", "job_posts", ["published"], if_not_exists=True)
    op.create_index("ix_job_posts_user_id", "job_posts", ["user_id"], if_not_exists=True)

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_user_id", sa.Integer(), nullable=False),
        sa.Column("candidate_chat_id", sa.Integer(), nullable=False),
        sa.Column("job_post_id", sa.Integer(), nullable=False),
        sa.Column("candidate_profile", sa.JSON(), nullable=False),
        sa.Column("match_result", sa.JSON(), nullable=False),
        sa.Column("submitted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["candidate_chat_id"], ["chats.id"]),
        sa.ForeignKeyConstraint(["candidate_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["job_post_id"], ["job_posts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_chat_id", "job_post_id"),
        if_not_exists=True,
    )
    op.create_index("ix_applications_candidate_chat_id", "applications", ["candidate_chat_id"], if_not_exists=True)
    op.create_index("ix_applications_candidate_user_id", "applications", ["candidate_user_id"], if_not_exists=True)
    op.create_index("ix_applications_job_post_id", "applications", ["job_post_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_applications_job_post_id", table_name="applications", if_exists=True)
    op.drop_index("ix_applications_candidate_user_id", table_name="applications", if_exists=True)
    op.drop_index("ix_applications_candidate_chat_id", table_name="applications", if_exists=True)
    op.drop_table("applications", if_exists=True)
    op.drop_index("ix_job_posts_user_id", table_name="job_posts", if_exists=True)
    op.drop_index("ix_job_posts_published", table_name="job_posts", if_exists=True)
    op.drop_table("job_posts", if_exists=True)
    op.drop_index("ix_messages_chat_id", table_name="messages", if_exists=True)
    op.drop_table("messages", if_exists=True)
    op.drop_index("ix_chats_user_id", table_name="chats", if_exists=True)
    op.drop_table("chats", if_exists=True)
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions", if_exists=True)
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions", if_exists=True)
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions", if_exists=True)
    op.drop_table("auth_sessions", if_exists=True)
    op.drop_table("user_credentials", if_exists=True)
    op.drop_index("ix_users_email", table_name="users", if_exists=True)
    op.drop_table("users", if_exists=True)
