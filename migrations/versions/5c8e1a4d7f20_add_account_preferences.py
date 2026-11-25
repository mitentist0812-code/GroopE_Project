"""Add persistent account preferences.

Revision ID: 5c8e1a4d7f20
Revises: af2c9e6d7130
"""
from alembic import op
import sqlalchemy as sa


revision = "5c8e1a4d7f20"
down_revision = "af2c9e6d7130"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_preference",
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column(
            "favorite_foods",
            sa.String(length=500),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "disliked_foods",
            sa.String(length=500),
            nullable=False,
            server_default="",
        ),
        sa.Column("allergies", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "religion",
            sa.String(length=20),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "use_location",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "health_mode",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("account_id"),
    )


def downgrade():
    op.drop_table("account_preference")
