"""count approved reservations as holds until checkout

Revision ID: 0e48b71c29af
Revises: c51ad2048e73
"""
from alembic import op
import sqlalchemy as sa

revision = "0e48b71c29af"
down_revision = "c51ad2048e73"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    books = sa.table(
        "books",
        sa.column("id", sa.Integer),
        sa.column("available_stock", sa.Integer),
    )
    reservations = sa.table(
        "reservations",
        sa.column("book_id", sa.Integer),
        sa.column("status", sa.String),
    )
    approved_counts = bind.execute(
        sa.select(
            reservations.c.book_id,
            sa.func.count(),
        )
        .where(reservations.c.status == "approved")
        .group_by(reservations.c.book_id)
    )
    for book_id, count in approved_counts:
        bind.execute(
            books.update()
            .where(books.c.id == book_id)
            .values(available_stock=books.c.available_stock + count)
        )


def downgrade():
    bind = op.get_bind()
    books = sa.table(
        "books",
        sa.column("id", sa.Integer),
        sa.column("available_stock", sa.Integer),
    )
    reservations = sa.table(
        "reservations",
        sa.column("book_id", sa.Integer),
        sa.column("status", sa.String),
    )
    approved_counts = bind.execute(
        sa.select(
            reservations.c.book_id,
            sa.func.count(),
        )
        .where(reservations.c.status == "approved")
        .group_by(reservations.c.book_id)
    )
    for book_id, count in approved_counts:
        bind.execute(
            books.update()
            .where(books.c.id == book_id)
            .values(available_stock=books.c.available_stock - count)
        )
