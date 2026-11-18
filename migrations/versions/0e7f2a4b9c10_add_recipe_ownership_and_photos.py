"""Add recipe ownership and photos.

Revision ID: 0e7f2a4b9c10
Revises: 71fd59c0a3e4
"""
from alembic import op
import sqlalchemy as sa


revision = "0e7f2a4b9c10"
down_revision = "71fd59c0a3e4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("recipe_list") as batch_op:
        batch_op.add_column(sa.Column("account_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("steps", sa.JSON(), nullable=True))
        batch_op.create_foreign_key("fk_recipe_list_account_id", "account", ["account_id"], ["id"])
        batch_op.create_index("ix_recipe_list_account_id", ["account_id"])

    op.create_table(
        "recipe_photo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipe_list.id"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=20), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
    )
    op.create_index("ix_recipe_photo_recipe_id", "recipe_photo", ["recipe_id"])


def downgrade():
    op.drop_index("ix_recipe_photo_recipe_id", table_name="recipe_photo")
    op.drop_table("recipe_photo")
    with op.batch_alter_table("recipe_list") as batch_op:
        batch_op.drop_index("ix_recipe_list_account_id")
        batch_op.drop_constraint("fk_recipe_list_account_id", type_="foreignkey")
        batch_op.drop_column("steps")
        batch_op.drop_column("account_id")
