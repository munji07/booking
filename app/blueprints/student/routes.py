from flask import render_template, request
from sqlalchemy import or_

from ...extensions import db
from ...models import Book, Loan, Reservation
from . import student_bp


@student_bp.get("/")
def dashboard():
    available_books = Book.query.filter_by(is_active=True).filter(Book.available_stock > 0).count()
    reservation_count = Reservation.query.count()
    loan_count = Loan.query.filter_by(status="borrowed").count()
    return render_template("student/dashboard.html", title="학생 대시보드", available_books=available_books, reservation_count=reservation_count, loan_count=loan_count)


@student_bp.get("/books")
def books():
    query = request.args.get("q", "", type=str).strip()
    category = request.args.get("category", "", type=str).strip()
    statement = Book.query.filter_by(is_active=True)
    if query:
        term = f"%{query}%"
        statement = statement.filter(or_(Book.title.ilike(term), Book.author.ilike(term)))
    if category:
        statement = statement.filter_by(category=category)
    books = statement.order_by(Book.created_at.desc()).all()
    categories = [row[0] for row in db.session.query(Book.category).filter(Book.is_active.is_(True)).distinct().order_by(Book.category).all()]
    return render_template("student/books.html", title="만화책 둘러보기", books=books, categories=categories, query=query, selected_category=category)


@student_bp.get("/history")
def history():
    return render_template("student/history.html", title="나의 이용 기록")
