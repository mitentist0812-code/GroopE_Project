"""Add persistent reviews for recipes and restaurants.

Revision ID: 2f3c6a9d8b41
Revises: 0e7f2a4b9c10
"""
from alembic import op
import sqlalchemy as sa


revision = "2f3c6a9d8b41"
down_revision = "0e7f2a4b9c10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "content_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=True),
        sa.Column("place_id", sa.String(length=256), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(recipe_id IS NOT NULL AND place_id IS NULL) OR "
            "(recipe_id IS NULL AND place_id IS NOT NULL)",
            name="ck_content_review_single_target",
        ),
        sa.CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_content_review_rating",
        ),
        sa.CheckConstraint(
            "length(trim(comment)) > 0",
            name="ck_content_review_comment",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe_list.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_review_recipe_id",
        "content_review",
        ["recipe_id"],
        unique=False,
    )
    op.create_index(
        "ix_content_review_place_id",
        "content_review",
        ["place_id"],
        unique=False,
    )
    op.create_index(
        "uq_content_review_account_recipe",
        "content_review",
        ["account_id", "recipe_id"],
        unique=True,
        sqlite_where=sa.text("recipe_id IS NOT NULL"),
        postgresql_where=sa.text("recipe_id IS NOT NULL"),
    )
    op.create_index(
        "uq_content_review_account_place",
        "content_review",
        ["account_id", "place_id"],
        unique=True,
        sqlite_where=sa.text("place_id IS NOT NULL"),
        postgresql_where=sa.text("place_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index(
        "uq_content_review_account_place",
        table_name="content_review",
    )
    op.drop_index(
        "uq_content_review_account_recipe",
        table_name="content_review",
    )
    op.drop_index("ix_content_review_place_id", table_name="content_review")
    op.drop_index("ix_content_review_recipe_id", table_name="content_review")
    op.drop_table("content_review")
