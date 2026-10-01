"""Add privacy-safe experiment events.

Revision ID: 20261001_04
Revises: 20260929_03
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_04"
down_revision = "20260929_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiment_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("visitor_hash", sa.String(length=64), nullable=False),
        sa.Column("event_date", sa.String(length=10), nullable=False),
        sa.Column("subject_type", sa.String(length=20), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("useful", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_type",
            "visitor_hash",
            "event_date",
            "subject_type",
            "subject_id",
            name="uq_experiment_event_daily_subject",
        ),
    )
    op.create_index("ix_experiment_events_event_type", "experiment_events", ["event_type"])
    op.create_index("ix_experiment_events_visitor_hash", "experiment_events", ["visitor_hash"])
    op.create_index("ix_experiment_events_event_date", "experiment_events", ["event_date"])


def downgrade() -> None:
    op.drop_index("ix_experiment_events_event_date", table_name="experiment_events")
    op.drop_index("ix_experiment_events_visitor_hash", table_name="experiment_events")
    op.drop_index("ix_experiment_events_event_type", table_name="experiment_events")
    op.drop_table("experiment_events")
