"""Add persistent account favorites for recipes and places.

Revision ID: 4c7d9e2a1b5f
Revises: 2f3c6a9d8b41
"""
from alembic import op
import sqlalchemy as sa


revision = "4c7d9e2a1b5f"
down_revision = "2f3c6a9d8b41"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recipe_favorite",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe_list.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "recipe_id",
            name="uq_recipe_favorite_account_recipe",
        ),
    )
    op.create_index(
        "ix_recipe_favorite_account_id",
        "recipe_favorite",
        ["account_id"],
    )
    op.create_index(
        "ix_recipe_favorite_recipe_id",
        "recipe_favorite",
        ["recipe_id"],
    )

    op.create_table(
        "place_favorite",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("place_id", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(place_id) >= 1 AND length(place_id) <= 256",
            name="ck_place_favorite_place_id_length",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "place_id",
            name="uq_place_favorite_account_place",
        ),
    )
    op.create_index(
        "ix_place_favorite_account_id",
        "place_favorite",
        ["account_id"],
    )
    op.create_index(
        "ix_place_favorite_place_id",
        "place_favorite",
        ["place_id"],
    )


def downgrade():
    op.drop_index("ix_place_favorite_place_id", table_name="place_favorite")
    op.drop_index("ix_place_favorite_account_id", table_name="place_favorite")
    op.drop_table("place_favorite")
    op.drop_index("ix_recipe_favorite_recipe_id", table_name="recipe_favorite")
    op.drop_index("ix_recipe_favorite_account_id", table_name="recipe_favorite")
    op.drop_table("recipe_favorite")
