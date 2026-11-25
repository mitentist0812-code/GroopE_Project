"""Add opt-in login email autofill preference.

Revision ID: 2a4d6e8f1b3c
Revises: 5c8e1a4d7f20
"""
from alembic import op
import sqlalchemy as sa


revision = "2a4d6e8f1b3c"
down_revision = "5c8e1a4d7f20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("account_preference") as batch_op:
        batch_op.add_column(
            sa.Column(
                "autofill_email",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade():
    with op.batch_alter_table("account_preference") as batch_op:
        batch_op.drop_column("autofill_email")
