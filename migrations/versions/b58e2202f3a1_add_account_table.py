"""Add persistent user and restaurant accounts.

Revision ID: b58e2202f3a1
Revises: 6e923ee54cbe
Create Date: 2026-11-16 10:35:00
"""
from alembic import op
import sqlalchemy as sa


revision = "b58e2202f3a1"
down_revision = "6e923ee54cbe"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "account_type IN ('user', 'restaurant')",
            name="ck_account_account_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_account_email"),
    )


def downgrade():
    op.drop_table("account")
