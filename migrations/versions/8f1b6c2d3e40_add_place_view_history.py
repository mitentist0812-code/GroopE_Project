"""Add persistent place view history.

Revision ID: 8f1b6c2d3e40
Revises: 4c7d9e2a1b5f
"""
from alembic import op
import sqlalchemy as sa


revision = "8f1b6c2d3e40"
down_revision = "4c7d9e2a1b5f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "place_view_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("place_id", sa.String(length=256), nullable=False),
        sa.Column("viewed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_place_view_history_account_id",
        "place_view_history",
        ["account_id"],
    )


def downgrade():
    op.drop_index("ix_place_view_history_account_id", table_name="place_view_history")
    op.drop_table("place_view_history")
