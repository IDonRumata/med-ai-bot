"""Add date_of_birth, height_cm, weight_kg to users

Revision ID: 002
Revises: 001
Create Date: 2026-04-07

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("height_cm", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("weight_kg", sa.Float(), nullable=True))
    # Migrate existing age data: set approximate dob from age (year only)
    op.execute("""
        UPDATE users
        SET date_of_birth = (CURRENT_DATE - (age || ' years')::interval)::date
        WHERE age IS NOT NULL AND date_of_birth IS NULL
    """)
    op.drop_column("users", "age")


def downgrade() -> None:
    op.add_column("users", sa.Column("age", sa.Integer(), nullable=True))
    op.drop_column("users", "weight_kg")
    op.drop_column("users", "height_cm")
    op.drop_column("users", "date_of_birth")
