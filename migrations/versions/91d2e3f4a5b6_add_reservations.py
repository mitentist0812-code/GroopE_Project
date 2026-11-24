"""Add persistent reservations.

Revision ID: 91d2e3f4a5b6
Revises: 8f1b6c2d3e40
"""
from alembic import op
import sqlalchemy as sa


revision = "91d2e3f4a5b6"
down_revision = "8f1b6c2d3e40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reservation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("restaurant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("guests", sa.Integer(), nullable=False),
        sa.Column("reserved_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("submission_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("guests >= 1 AND guests <= 20", name="ck_reservation_guests"),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled')",
            name="ck_reservation_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["restaurant_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_key", name="uq_reservation_submission_key"),
    )
    op.create_index("ix_reservation_user_id", "reservation", ["user_id"])
    op.create_index("ix_reservation_restaurant_id", "reservation", ["restaurant_id"])


def downgrade():
    op.drop_index("ix_reservation_restaurant_id", table_name="reservation")
    op.drop_index("ix_reservation_user_id", table_name="reservation")
    op.drop_table("reservation")
