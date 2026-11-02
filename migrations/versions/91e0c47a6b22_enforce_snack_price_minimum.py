"""enforce the minimum price for recorded snack exchanges

Revision ID: 91e0c47a6b22
Revises: 72ac91e5f340
"""
from alembic import op

revision = "91e0c47a6b22"
down_revision = "72ac91e5f340"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("snack_exchanges") as batch_op:
        batch_op.create_check_constraint(
            "ck_snack_exchanges_unit_price_minimum",
            "unit_price IS NULL OR unit_price >= 1000",
        )


def downgrade():
    with op.batch_alter_table("snack_exchanges") as batch_op:
        batch_op.drop_constraint("ck_snack_exchanges_unit_price_minimum", type_="check")
