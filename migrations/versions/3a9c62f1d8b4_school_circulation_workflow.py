"""support pickup, walk-in lending, and school-period tickets

Revision ID: 3a9c62f1d8b4
Revises: 1b7f4e2a9d11
"""
from alembic import op
import sqlalchemy as sa

revision = "3a9c62f1d8b4"
down_revision = "1b7f4e2a9d11"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("reservations") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.add_column(sa.Column("student_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column(
            "source",
            sa.String(length=20),
            nullable=False,
            server_default="online",
        ))
        batch_op.create_foreign_key(
            "fk_reservations_student_id_students",
            "students",
            ["student_id"],
            ["id"],
        )
        batch_op.create_index("ix_reservations_student_id", ["student_id"])
        batch_op.create_index("ix_reservations_source", ["source"])

    op.execute(sa.text(
        "UPDATE reservations "
        "SET student_id = (SELECT students.id FROM students "
        "WHERE students.user_id = reservations.user_id) "
        "WHERE student_id IS NULL"
    ))

    with op.batch_alter_table("loans") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.add_column(sa.Column("student_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_loans_student_id_students",
            "students",
            ["student_id"],
            ["id"],
        )
        batch_op.create_index("ix_loans_student_id", ["student_id"])

    op.execute(sa.text(
        "UPDATE loans SET student_id = "
        "(SELECT reservations.student_id FROM reservations "
        "WHERE reservations.id = loans.reservation_id) "
        "WHERE student_id IS NULL"
    ))
    op.execute(sa.text(
        "UPDATE reservations SET status = 'issued' "
        "WHERE status = 'approved' AND EXISTS ("
        "SELECT 1 FROM loans WHERE loans.reservation_id = reservations.id "
        "AND loans.status = 'borrowed')"
    ))

    with op.batch_alter_table("paper_tickets") as batch_op:
        batch_op.add_column(sa.Column("receive_period", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("return_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("return_period", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("paper_tickets") as batch_op:
        batch_op.drop_column("return_period")
        batch_op.drop_column("return_date")
        batch_op.drop_column("receive_period")

    with op.batch_alter_table("loans") as batch_op:
        batch_op.drop_index("ix_loans_student_id")
        batch_op.drop_constraint("fk_loans_student_id_students", type_="foreignkey")
        batch_op.drop_column("student_id")

    with op.batch_alter_table("reservations") as batch_op:
        batch_op.drop_index("ix_reservations_source")
        batch_op.drop_index("ix_reservations_student_id")
        batch_op.drop_constraint("fk_reservations_student_id_students", type_="foreignkey")
        batch_op.drop_column("source")
        batch_op.drop_column("student_id")
