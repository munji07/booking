from flask import render_template

from ...models import ActivityLog, Book, Loan, Reservation, SnackExchange, Student, User
from . import admin_bp


@admin_bp.get("/")
def dashboard():
    stats = {
        "students": Student.query.count(),
        "books": Book.query.count(),
        "pending": Reservation.query.filter_by(status="pending").count(),
        "approved": Reservation.query.filter_by(status="approved").count(),
        "borrowed": Loan.query.filter_by(status="borrowed").count(),
        "returned": Loan.query.filter_by(status="returned").count(),
        "snacks": SnackExchange.query.filter_by(status="completed").count(),
        "logs": ActivityLog.query.count(),
    }
    return render_template("admin/dashboard.html", title="관리자 대시보드", stats=stats)


@admin_bp.get("/students")
def students():
    return render_template("admin/section.html", title="학생 관리", section="학생", description="학생 등록과 가입 코드 발급을 이 화면에서 연결합니다.")


@admin_bp.get("/books")
def books():
    return render_template("admin/section.html", title="만화책 관리", section="만화책", description="도서 등록, 표지 업로드, 재고 관리를 이 화면에서 연결합니다.")


@admin_bp.get("/reservations")
def reservations():
    return render_template("admin/section.html", title="예약 관리", section="예약", description="예약 승인·거절과 상태 변경을 이 화면에서 연결합니다.")


@admin_bp.get("/operations")
def operations():
    return render_template("admin/section.html", title="대여 운영", section="대여 운영", description="사물함, 종이 대여증, 간식 교환 흐름을 이 화면에서 연결합니다.")
