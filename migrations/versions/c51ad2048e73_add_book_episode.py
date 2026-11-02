"""add a book episode field

Revision ID: c51ad2048e73
Revises: 91e0c47a6b22
"""
from alembic import op
import sqlalchemy as sa

revision = "c51ad2048e73"
down_revision = "91e0c47a6b22"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("books") as batch_op:
        batch_op.add_column(
            sa.Column(
                "episode",
                sa.String(length=40),
                nullable=False,
                server_default="",
            )
        )


def downgrade():
    with op.batch_alter_table("books") as batch_op:
        batch_op.drop_column("episode")
