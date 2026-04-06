"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("sex", sa.String(10), nullable=True),
        sa.Column("chronic_conditions", sa.Text(), nullable=True),
        sa.Column("allergies", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "test_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("test_date", sa.Date(), nullable=False),
        sa.Column("metric_name", sa.String(200), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("ref_min", sa.Float(), nullable=True),
        sa.Column("ref_max", sa.Float(), nullable=True),
        sa.Column("source_file", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_results_metric_date", "test_results", ["metric_name", "test_date"])

    op.create_table(
        "symptom_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("logged_at", sa.DateTime(), nullable=False),
        sa.Column("complaint_text", sa.Text(), nullable=False),
        sa.Column("ai_assessment", sa.Text(), nullable=True),
        sa.Column("severity", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("fire_at", sa.DateTime(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reminders_fire_at", "reminders", ["fire_at"])


def downgrade() -> None:
    op.drop_table("reminders")
    op.drop_table("symptom_logs")
    op.drop_table("test_results")
    op.drop_table("users")
