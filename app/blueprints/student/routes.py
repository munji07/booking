from datetime import timezone

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_, update
from werkzeug.security import check_password_hash, generate_password_hash

from ...extensions import db
from ...models import ActivityLog, Book, InviteCode, Loan, Reservation, User
from ...time_utils import utc_now
from . import student_bp


def get_effective_available_stock(available_stock, approved_count=0):
    return max(available_stock - approved_count, 0)


def get_availability_state(available_stock, approved_count=0):
    effective_stock = get_effective_available_stock(available_stock, approved_count)
    if effective_stock > 0:
        return "available"
    if available_stock > 0:
        return "reserved"
    return "unavailable"


def validate_reservation_periods(receive_period, return_period):
    if receive_period is None or return_period is None:
        raise ValueError("수령·반납 교시를 올바르게 입력하세요.")
    if min(receive_period, return_period) < 1:
        raise ValueError("수령·반납 교시를 올바르게 입력하세요.")
    if max(receive_period, return_period) > 12:
        raise ValueError("교시는 1교시부터 12교시 사이로 입력하세요.")
    if return_period <= receive_period:
        raise ValueError("반납 교시는 수령 교시 이후로 입력하세요.")
    if return_period - receive_period > 3:
        raise ValueError("대출은 수령 교시부터 최대 3교시까지만 가능합니다.")
    return {"receive_period": receive_period, "return_period": return_period}


@student_bp.get("/")
@login_required
def dashboard():
    approved_holds = (
        db.session.query(db.func.count(Reservation.id))
        .filter(
            Reservation.book_id == Book.id,
            Reservation.status == "approved",
        )
        .correlate(Book)
        .scalar_subquery()
    )
    available_books = Book.query.filter(
        Book.is_active.is_(True),
        Book.available_stock > approved_holds,
    ).count()
    student_id = current_user.student.id if current_user.student else None
    owner_filter = (
        or_(Reservation.user_id == current_user.id, Reservation.student_id == student_id)
        if student_id
        else Reservation.user_id == current_user.id
    )
    reservations = Reservation.query.filter(owner_filter).order_by(Reservation.requested_at.desc()).limit(10).all()
    loan_query = Loan.query.filter_by(status="borrowed")
    loan_count = loan_query.filter_by(student_id=student_id).count() if student_id else loan_query.filter_by(user_id=current_user.id).count()
    return render_template(
        "student/dashboard.html",
        title="학생 대시보드",
        available_books=available_books,
        reservation_count=Reservation.query.filter(owner_filter).count(),
        loan_count=loan_count,
        reservations=reservations,
    )

@student_bp.get("/books")
def books():
    query = request.args.get("q", "", type=str).strip()
    statement = Book.query.filter_by(is_active=True)
    if query:
        term = f"%{query}%"
        statement = statement.filter(
            or_(
                Book.title.ilike(term),
                Book.episode.ilike(term),
            )
        )
    books = statement.order_by(Book.created_at.desc()).all()
    book_ids = [book.id for book in books]
    borrowed_counts = {}
    approved_counts = {}
    if book_ids:
        borrowed_counts = dict(
            db.session.query(Loan.book_id, db.func.count(Loan.id))
            .filter(Loan.book_id.in_(book_ids), Loan.status == "borrowed")
            .group_by(Loan.book_id)
            .all()
        )
        approved_counts = dict(
            db.session.query(Reservation.book_id, db.func.count(Reservation.id))
            .filter(
                Reservation.book_id.in_(book_ids),
                Reservation.status == "approved",
            )
            .group_by(Reservation.book_id)
            .all()
        )
    availability_states = {}
    effective_available = {}
    for book in books:
        approved_count = approved_counts.get(book.id, 0)
        effective_available[book.id] = get_effective_available_stock(book.available_stock, approved_count)
        availability_states[book.id] = get_availability_state(book.available_stock, approved_count)
    return render_template(
        "student/books.html",
        title="만화책 둘러보기",
        books=books,
        query=query,
        borrowed_counts=borrowed_counts,
        approved_counts=approved_counts,
        availability_states=availability_states,
        effective_available=effective_available,
    )

@student_bp.get("/history")
@login_required
def history():
    student_id = current_user.student.id if current_user.student else None
    owner_filter = (
        or_(Reservation.user_id == current_user.id, Reservation.student_id == student_id)
        if student_id
        else Reservation.user_id == current_user.id
    )
    reservations = Reservation.query.filter(owner_filter).order_by(Reservation.requested_at.desc()).all()
    return render_template("student/history.html", title="나의 이용 기록", reservations=reservations)

@student_bp.post("/books/<int:book_id>/reserve")
@login_required
def reserve(book_id):
    book = db.session.get(Book, book_id)
    student = current_user.student
    active_statuses = ("pending", "approved", "issued")
    receive_period = request.form.get("receive_period", type=int)
    return_period = request.form.get("return_period", type=int)
    try:
        validated_periods = validate_reservation_periods(receive_period, return_period)
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("student.books"))

    if current_user.role != "student" or not student or not student.is_active:
        flash("활성 학생 계정으로 로그인한 뒤 신청해 주세요.", "danger")
    elif not book or not book.is_active:
        flash("현재 신청할 수 없는 책입니다.", "warning")
    elif Reservation.query.filter(
        Reservation.student_id == student.id,
        Reservation.book_id == book.id,
        Reservation.status.in_(active_statuses),
    ).first():
        flash("이 책은 이미 신청했거나 대여 중입니다.", "warning")
    else:
        next_number = db.session.execute(
            update(Book)
            .where(Book.id == book.id, Book.is_active.is_(True))
            .values(next_queue_number=Book.next_queue_number + 1)
            .returning(Book.next_queue_number)
        ).scalar_one_or_none()
        if next_number is None:
            db.session.rollback()
            flash("현재 신청할 수 없는 책입니다.", "warning")
            return redirect(url_for("student.books"))
        queue_number = next_number - 1
        reservation = Reservation(
            user_id=current_user.id,
            student_id=student.id,
            book_id=book.id,
            source="online",
            status="pending",
            queue_number=queue_number,
        )
        db.session.add(reservation)
        db.session.flush()
        if book.available_stock <= 0:
            reservation.note = (
                f"수령 교시 {validated_periods['receive_period']}교시, "
                f"반납 교시 {validated_periods['return_period']}교시 예정"
            )
        db.session.commit()
        flash(
            f"신청했습니다. 이 도서의 순번은 {queue_number}번입니다. "
            f"수령은 {validated_periods['receive_period']}교시, 반납은 {validated_periods['return_period']}교시로 예약했습니다.",
            "success",
        )
    return redirect(url_for("student.books"))

@student_bp.post("/reservations/<int:reservation_id>/cancel")
@login_required
def cancel_reservation(reservation_id):
    reservation = db.session.get(Reservation, reservation_id)
    if reservation and reservation.user_id == current_user.id and reservation.status in {"pending", "approved"}:
        previous_status = reservation.status
        now = utc_now()
        cancelled = Reservation.query.filter_by(
            id=reservation.id,
            user_id=current_user.id,
            status=previous_status,
        ).update(
            {
                Reservation.status: "cancelled",
                Reservation.cancelled_at: now,
            },
            synchronize_session=False,
        )
        if cancelled != 1:
            db.session.rollback()
            flash("신청 상태가 이미 변경되었습니다. 화면을 새로고침하세요.", "warning")
            return redirect(url_for("student.dashboard"))
        reservation.status = "cancelled"
        reservation.cancelled_at = now
        db.session.commit()
        flash("신청을 취소했습니다.", "success")
    return redirect(url_for("student.dashboard"))

def _invite_for_code(code):
    for invite in InviteCode.query.filter_by(used_at=None, revoked_at=None).all():
        expires_at = invite.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at > utc_now() and check_password_hash(invite.code_hash, code):
            return invite
    return None

@student_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = User.query.filter_by(username=username, role="student", is_active=True).first()
        if user and check_password_hash(user.password_hash, request.form.get("password", "")):
            login_user(user)
            return redirect(request.args.get("next") or url_for("student.dashboard"))
        flash("아이디 또는 비밀번호를 확인하세요.", "danger")
    return render_template("auth/password_login.html", title="학생 로그인")

@student_bp.route("/invite", methods=["POST"])
def invite():
    code = request.form.get("code", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    invite = _invite_for_code(code)
    if not invite:
        flash("유효하지 않거나 만료된 초대코드입니다.", "danger")
    elif not username and not password:
        if invite.student.user_id:
            flash("이미 사용된 초대코드입니다.", "warning")
        else:
            return render_template("auth/account_setup.html", title="학생 계정 만들기", code=code)
    elif not username or len(password) < 8:
        flash("아이디를 입력하고 비밀번호는 8자 이상 사용하세요.", "danger")
    elif User.query.filter_by(username=username).first():
        flash("이미 사용 중인 아이디입니다.", "danger")
    elif invite.student.user_id:
        flash("이미 사용된 초대코드입니다.", "danger")
    else:
        user = User(username=username, password_hash=generate_password_hash(password), role="student")
        db.session.add(user)
        db.session.flush()
        invite.student.user_id = user.id
        invite.used_at = utc_now()
        db.session.add(ActivityLog(actor_user_id=user.id, action="student_account_created", entity_type="student", entity_id=str(invite.student_id)))
        db.session.commit()
        login_user(user)
        return redirect(url_for("student.dashboard"))
    return render_template("auth/invite.html", title="초대코드로 가입")

@student_bp.get("/account")
@login_required
def account():
    if current_user.role != "student" or not current_user.student or not current_user.student.is_active:
        abort(403)
    return render_template("student/account.html", title="학생 계정", student=current_user.student)


@student_bp.post("/account")
@login_required
def update_account():
    if current_user.role != "student" or not current_user.student or not current_user.student.is_active:
        abort(403)

    action = request.form.get("action")
    if not check_password_hash(current_user.password_hash, request.form.get("current_password", "")):
        flash("현재 비밀번호가 올바르지 않습니다.", "danger")
        return redirect(url_for("student.account"))

    if action == "change_username":
        username = request.form.get("username", "").strip()
        if not 3 <= len(username) <= 80:
            flash("아이디는 3자 이상 80자 이하로 입력하세요.", "danger")
            return redirect(url_for("student.account"))
        existing = User.query.filter_by(username=username).first()
        if existing and existing.id != current_user.id:
            flash("이미 사용 중인 아이디입니다.", "danger")
            return redirect(url_for("student.account"))
        if username == current_user.username:
            flash("현재 아이디와 다른 아이디를 입력하세요.", "warning")
            return redirect(url_for("student.account"))
        current_user.username = username
        log_action = "student_username_changed"
        message = "로그인 아이디를 변경했습니다."
    elif action == "change_password":
        password = request.form.get("new_password", "")
        password_confirm = request.form.get("new_password_confirm", "")
        if len(password) < 8:
            flash("새 비밀번호는 8자 이상 입력하세요.", "danger")
            return redirect(url_for("student.account"))
        if password != password_confirm:
            flash("새 비밀번호 확인이 일치하지 않습니다.", "danger")
            return redirect(url_for("student.account"))
        current_user.set_password(password)
        log_action = "student_password_changed"
        message = "비밀번호를 변경했습니다."
    else:
        flash("요청을 처리할 수 없습니다.", "danger")
        return redirect(url_for("student.account"))

    current_user.auth_version += 1
    db.session.add(ActivityLog(
        actor_user_id=current_user.id,
        action=log_action,
        entity_type="student",
        entity_id=str(current_user.student.id),
    ))
    db.session.commit()
    login_user(current_user, fresh=True)
    flash(f"{message} 다른 기기의 로그인은 종료되었습니다.", "success")
    return redirect(url_for("student.account"))

@student_bp.get("/register")
def register():
    return redirect(url_for("main.student_access"))

@student_bp.post("/logout")
@login_required
def logout():
    if current_user.role != "student":
        abort(403)
    logout_user()
    flash("학생 로그아웃이 완료되었습니다.", "success")
    return redirect(url_for("student.login"))
