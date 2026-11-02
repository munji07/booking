"""Core domain models for the Bookmaru lending service."""
from flask_login import UserMixin
from werkzeug.security import generate_password_hash

from .extensions import db
from .time_utils import utc_now


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student", index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    student = db.relationship("Student", back_populates="user", uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)


class Student(TimestampMixin, db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    grade = db.Column(db.String(20), nullable=False)
    class_name = db.Column(db.String(20), nullable=False)
    internal_id = db.Column(db.String(80), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    user = db.relationship("User", back_populates="student")


class InviteCode(db.Model):
    __tablename__ = "invite_codes"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    code_hash = db.Column(db.String(255), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    student = db.relationship("Student")


class Book(TimestampMixin, db.Model):
    __tablename__ = "books"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    author = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    cover_url = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(80), nullable=False, default="기타", index=True)
    total_stock = db.Column(db.Integer, nullable=False, default=1)
    available_stock = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    __table_args__ = (
        db.CheckConstraint("total_stock >= 0", name="ck_books_total_stock_nonnegative"),
        db.CheckConstraint("available_stock >= 0", name="ck_books_available_stock_nonnegative"),
    )


class Reservation(TimestampMixin, db.Model):
    __tablename__ = "reservations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    requested_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    note = db.Column(db.Text, nullable=True)
    user = db.relationship("User")
    book = db.relationship("Book")


class Loan(TimestampMixin, db.Model):
    __tablename__ = "loans"
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="borrowed", index=True)
    borrowed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    returned_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reservation = db.relationship("Reservation")
    book = db.relationship("Book")


class Locker(db.Model):
    __tablename__ = "lockers"
    id = db.Column(db.Integer, primary_key=True)
    locker_number = db.Column(db.String(30), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    current_reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), unique=True, nullable=True)
    current_reservation = db.relationship("Reservation")


class PaperTicket(db.Model):
    __tablename__ = "paper_tickets"
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), unique=True, nullable=False)
    ticket_number = db.Column(db.String(40), unique=True, nullable=False)
    locker_id = db.Column(db.Integer, db.ForeignKey("lockers.id"), nullable=True)
    is_issued = db.Column(db.Boolean, nullable=False, default=False)
    issued_at = db.Column(db.DateTime(timezone=True), nullable=True)
    issued_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reservation = db.relationship("Reservation")
    locker = db.relationship("Locker")


class SnackExchange(db.Model):
    __tablename__ = "snack_exchanges"
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), unique=True, nullable=False)
    required_quantity = db.Column(db.Integer, nullable=False, default=1)
    submitted_quantity = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="waiting", index=True)
    checked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reservation = db.relationship("Reservation")


class SystemSetting(db.Model):
    __tablename__ = "system_settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"
    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.String(80), nullable=True)
    detail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    actor = db.relationship("User")
