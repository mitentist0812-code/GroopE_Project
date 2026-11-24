"""Add manually specified locations for unlinked restaurants.

Revision ID: af2c9e6d7130
Revises: 91d2e3f4a5b6
"""
from alembic import op
import sqlalchemy as sa


revision = "af2c9e6d7130"
down_revision = "91d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reservation",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE reservation SET is_demo = TRUE")
    op.create_table(
        "restaurant_location",
        sa.Column("restaurant_id", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_restaurant_location_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_restaurant_location_longitude"),
        sa.ForeignKeyConstraint(["restaurant_id"], ["account.id"]),
        sa.PrimaryKeyConstraint("restaurant_id"),
    )


def downgrade():
    op.drop_table("restaurant_location")
    with op.batch_alter_table("reservation") as batch_op:
        batch_op.drop_column("is_demo")
