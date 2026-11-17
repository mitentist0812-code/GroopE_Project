"""Add demo restaurant place linking.

Revision ID: 71fd59c0a3e4
Revises: 3d8b7b4a1f2c
Create Date: 2026-11-17 12:25:00
"""
from alembic import op
import sqlalchemy as sa


revision = "71fd59c0a3e4"
down_revision = "3d8b7b4a1f2c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("account") as batch_op:
        batch_op.add_column(sa.Column("place_id", sa.String(length=256)))
        batch_op.create_unique_constraint("uq_account_place_id", ["place_id"])

    op.create_table(
        "restaurant_place_claim",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("place_id", sa.String(length=256), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "attempts >= 0 AND attempts <= 5",
            name="ck_restaurant_place_claim_attempts",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            name="uq_restaurant_place_claim_account",
        ),
    )


def downgrade():
    op.drop_table("restaurant_place_claim")
    with op.batch_alter_table("account") as batch_op:
        batch_op.drop_constraint("uq_account_place_id", type_="unique")
        batch_op.drop_column("place_id")
