"""Add calorie calculation history.

Revision ID: 7d3a9c2e6f10
Revises: 2a4d6e8f1b3c
"""
from alembic import op
import sqlalchemy as sa


revision = "7d3a9c2e6f10"
down_revision = "2a4d6e8f1b3c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "calorie_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("save_key", sa.String(64), nullable=False),
        sa.Column("dish", sa.String(100), nullable=False),
        sa.Column("ingredients", sa.JSON(), nullable=False),
        sa.Column("total_calories", sa.Integer()),
        sa.Column("unmatched_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "save_key", name="uq_calorie_history_account_save_key"),
    )
    op.create_index("ix_calorie_history_account_id", "calorie_history", ["account_id"])


def downgrade():
    op.drop_index("ix_calorie_history_account_id", table_name="calorie_history")
    op.drop_table("calorie_history")
