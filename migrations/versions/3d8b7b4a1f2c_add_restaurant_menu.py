"""Add persistent restaurant menus.

Revision ID: 3d8b7b4a1f2c
Revises: b58e2202f3a1
Create Date: 2026-11-17 09:50:00
"""
from alembic import op
import sqlalchemy as sa


revision = "3d8b7b4a1f2c"
down_revision = "b58e2202f3a1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "restaurant_menu",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("restaurant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("calories", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_restaurant_menu_name",
        ),
        sa.CheckConstraint(
            "price >= 0",
            name="ck_restaurant_menu_price",
        ),
        sa.CheckConstraint(
            "calories >= 0",
            name="ck_restaurant_menu_calories",
        ),
        sa.ForeignKeyConstraint(["restaurant_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_restaurant_menu_restaurant_id"),
        "restaurant_menu",
        ["restaurant_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_restaurant_menu_restaurant_id"),
        table_name="restaurant_menu",
    )
    op.drop_table("restaurant_menu")
