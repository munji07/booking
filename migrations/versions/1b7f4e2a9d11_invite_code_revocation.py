"""add invite code revocation timestamp

Revision ID: 1b7f4e2a9d11
Revises: e84c7340a8c5
"""
from alembic import op
import sqlalchemy as sa

revision = "1b7f4e2a9d11"
down_revision = "e84c7340a8c5"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("invite_codes") as batch_op:
        batch_op.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))

def downgrade():
    with op.batch_alter_table("invite_codes") as batch_op:
        batch_op.drop_column("revoked_at")
