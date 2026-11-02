"""support student account administration and session revocation

Revision ID: 4b8d21e6c735
Revises: 3a9c62f1d8b4
"""
from alembic import op
import sqlalchemy as sa

revision = "4b8d21e6c735"
down_revision = "3a9c62f1d8b4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column(
            "auth_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ))


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("auth_version")
