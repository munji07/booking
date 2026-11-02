"""record snack price and assign per-book queue numbers

Revision ID: 72ac91e5f340
Revises: 4b8d21e6c735
"""
from alembic import op
import sqlalchemy as sa

revision = "72ac91e5f340"
down_revision = "4b8d21e6c735"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("books") as batch_op:
        batch_op.add_column(sa.Column(
            "next_queue_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ))

    with op.batch_alter_table("reservations") as batch_op:
        batch_op.add_column(sa.Column("queue_number", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_reservations_book_queue_number",
            ["book_id", "queue_number"],
        )

    bind = op.get_bind()
    reservations = sa.table(
        "reservations",
        sa.column("id", sa.Integer),
        sa.column("book_id", sa.Integer),
        sa.column("source", sa.String),
        sa.column("requested_at", sa.DateTime),
        sa.column("queue_number", sa.Integer),
    )
    next_numbers = {}
    rows = bind.execute(
        sa.select(
            reservations.c.id,
            reservations.c.book_id,
            reservations.c.source,
        ).order_by(
            reservations.c.book_id,
            reservations.c.requested_at,
            reservations.c.id,
        )
    )
    for row in rows:
        if row.source == "walk_in":
            continue
        number = next_numbers.get(row.book_id, 1)
        bind.execute(
            reservations.update()
            .where(reservations.c.id == row.id)
            .values(queue_number=number)
        )
        next_numbers[row.book_id] = number + 1

    books = sa.table(
        "books",
        sa.column("id", sa.Integer),
        sa.column("next_queue_number", sa.Integer),
    )
    for book_id, next_number in next_numbers.items():
        bind.execute(
            books.update()
            .where(books.c.id == book_id)
            .values(next_queue_number=next_number)
        )

    with op.batch_alter_table("snack_exchanges") as batch_op:
        batch_op.add_column(sa.Column("unit_price", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("snack_exchanges") as batch_op:
        batch_op.drop_column("unit_price")

    with op.batch_alter_table("reservations") as batch_op:
        batch_op.drop_constraint("uq_reservations_book_queue_number", type_="unique")
        batch_op.drop_column("queue_number")

    with op.batch_alter_table("books") as batch_op:
        batch_op.drop_column("next_queue_number")
