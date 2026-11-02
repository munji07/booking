import secrets
from datetime import date, timedelta
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from ...extensions import db
from ...models import ActivityLog, Book, InviteCode, Loan, PaperTicket, Reservation, SnackExchange, Student, User
from ...time_utils import to_kst, utc_now
from . import admin_bp

def admin_only(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        user = User.query.filter_by(username=request.form.get("username", "").strip(), role="admin", is_active=True).first()
        if user and check_password_hash(user.password_hash, request.form.get("password", "")):
            login_user(user)
            return redirect(request.args.get("next") or url_for("admin.dashboard"))
        flash("관리자 아이디 또는 비밀번호를 확인하세요.", "danger")
    return render_template("auth/admin_login.html", title="관리자 로그인")

@admin_bp.post("/logout")
@admin_only
def logout():
    logout_user()
    flash("관리자 로그아웃이 완료되었습니다.", "success")
    return redirect(url_for("admin.login"))

@admin_bp.get("/")
@admin_only
def dashboard():
    stats = {"students": Student.query.count(), "books": Book.query.count(), "pending": Reservation.query.filter_by(status="pending").count(), "approved": Reservation.query.filter_by(status="approved").count(), "borrowed": Loan.query.filter_by(status="borrowed").count(), "returned": Loan.query.filter_by(status="returned").count(), "snacks": SnackExchange.query.filter_by(status="completed").count(), "logs": ActivityLog.query.count()}
    return render_template("admin/dashboard.html", title="관리자 대시보드", stats=stats)


def _student_records(query=""):
    statement = Student.query.outerjoin(User, Student.user_id == User.id)
    if query:
        term = f"%{query}%"
        statement = statement.filter(or_(
            Student.name.ilike(term),
            Student.grade.ilike(term),
            Student.class_name.ilike(term),
            Student.internal_id.ilike(term),
            User.username.ilike(term),
        ))
    return statement.order_by(Student.created_at.desc()).all()


def _students_with_history(students):
    student_ids = [student.id for student in students]
    user_ids = [student.user_id for student in students if student.user_id is not None]
    if not student_ids:
        return set()

    history_ids = set()
    user_to_student = {student.user_id: student.id for student in students if student.user_id is not None}
    reservation_rows = Reservation.query.with_entities(
        Reservation.student_id,
        Reservation.user_id,
    ).filter(or_(
        Reservation.student_id.in_(student_ids),
        Reservation.user_id.in_(user_ids) if user_ids else Reservation.id == -1,
    )).all()
    for student_id, user_id in reservation_rows:
        if student_id in student_ids:
            history_ids.add(student_id)
        elif user_id in user_to_student:
            history_ids.add(user_to_student[user_id])

    loan_rows = Loan.query.with_entities(Loan.student_id, Loan.user_id).filter(or_(
        Loan.student_id.in_(student_ids),
        Loan.user_id.in_(user_ids) if user_ids else Loan.id == -1,
    )).all()
    for student_id, user_id in loan_rows:
        if student_id in student_ids:
            history_ids.add(student_id)
        elif user_id in user_to_student:
            history_ids.add(user_to_student[user_id])
    return history_ids


@admin_bp.route("/students", methods=["GET", "POST"])
@admin_only
def students():
    query = request.args.get("q", "").strip()
    issued_code = None
    if request.method == "POST":
        values = {key: request.form.get(key, "").strip() for key in ("name", "grade", "class_name", "internal_id")}
        if not all(values.values()):
            flash("학생 정보를 모두 입력하세요.", "danger")
        elif Student.query.filter_by(internal_id=values["internal_id"]).first():
            flash("이미 등록된 내부 ID입니다.", "danger")
        else:
            student = Student(**values)
            db.session.add(student)
            db.session.flush()
            issued_code = secrets.token_urlsafe(8)
            db.session.add(InviteCode(student_id=student.id, code_hash=generate_password_hash(issued_code), expires_at=utc_now() + timedelta(days=7)))
            db.session.add(ActivityLog(actor_user_id=current_user.id, action="student_created", entity_type="student", entity_id=str(student.id)))
            db.session.commit()
            flash("학생을 등록했습니다. 가입 코드는 지금만 확인할 수 있습니다.", "success")
    records = _student_records(query)
    return render_template(
        "admin/students.html",
        title="학생 관리",
        students=records,
        students_with_history=_students_with_history(records),
        issued_code=issued_code,
        query=query,
    )

@admin_bp.post("/students/<int:student_id>/invite")
@admin_only
def reissue_invite(student_id):
    student = db.session.get(Student, student_id)
    if not student or student.user_id or not student.is_active:
        abort(404)
    now = utc_now()
    InviteCode.query.filter_by(student_id=student.id, used_at=None, revoked_at=None).update({"revoked_at": now})
    raw_code = secrets.token_urlsafe(8)
    db.session.add(InviteCode(student_id=student.id, code_hash=generate_password_hash(raw_code), expires_at=now + timedelta(days=7)))
    db.session.add(ActivityLog(actor_user_id=current_user.id, action="invite_reissued", entity_type="student", entity_id=str(student.id)))
    db.session.commit()
    flash("가입 코드를 재발급했습니다. 학생에게 새 코드를 전달하세요.", "success")
    query = request.args.get("q", "").strip()
    records = _student_records(query)
    return render_template(
        "admin/students.html",
        title="학생 관리",
        students=records,
        students_with_history=_students_with_history(records),
        issued_code=raw_code,
        query=query,
    )


@admin_bp.post("/students/<int:student_id>/reset-password")
@admin_only
def reset_student_password(student_id):
    student = db.session.get(Student, student_id)
    if not student or not student.is_active or not student.user or student.user.role != "student":
        abort(404)
    temporary_password = secrets.token_urlsafe(12)
    student.user.set_password(temporary_password)
    student.user.auth_version += 1
    db.session.add(ActivityLog(
        actor_user_id=current_user.id,
        action="student_password_reset",
        entity_type="student",
        entity_id=str(student.id),
    ))
    db.session.commit()
    records = _student_records(request.args.get("q", "").strip())
    response = current_app.make_response(render_template(
        "admin/students.html",
        title="학생 관리",
        students=records,
        students_with_history=_students_with_history(records),
        query=request.args.get("q", "").strip(),
        reset_password=temporary_password,
        reset_student=student,
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


@admin_bp.post("/students/<int:student_id>/deactivate")
@admin_only
def deactivate_student(student_id):
    student = db.session.get(Student, student_id)
    if not student or not student.is_active:
        abort(404)

    now = utc_now()
    active_reservations = Reservation.query.filter(
        Reservation.student_id == student.id,
        Reservation.status.in_(("pending", "approved")),
    ).all()
    for reservation in active_reservations:
        reservation.status = "cancelled"
        reservation.cancelled_at = now

    InviteCode.query.filter_by(student_id=student.id, used_at=None, revoked_at=None).update(
        {"revoked_at": now},
        synchronize_session=False,
    )
    student.is_active = False
    if student.user:
        student.user.is_active = False
        student.user.auth_version += 1
    db.session.add(ActivityLog(
        actor_user_id=current_user.id,
        action="student_deactivated",
        entity_type="student",
        entity_id=str(student.id),
    ))
    open_loans = Loan.query.filter_by(student_id=student.id, status="borrowed").count()
    db.session.commit()
    if open_loans:
        flash(f"학생을 비활성화했습니다. 대여 중인 도서 {open_loans}권은 반납 처리해야 합니다. 기록은 보존됩니다.", "warning")
    else:
        flash("학생을 비활성화했습니다. 대출·이용 기록은 보존됩니다.", "success")
    return redirect(url_for("admin.students", q=request.args.get("q", "")))


@admin_bp.post("/students/<int:student_id>/reactivate")
@admin_only
def reactivate_student(student_id):
    student = db.session.get(Student, student_id)
    if not student or student.is_active:
        abort(404)
    student.is_active = True
    if student.user:
        student.user.is_active = True
    db.session.add(ActivityLog(
        actor_user_id=current_user.id,
        action="student_reactivated",
        entity_type="student",
        entity_id=str(student.id),
    ))
    db.session.commit()
    flash("학생을 다시 활성화했습니다.", "success")
    return redirect(url_for("admin.students", q=request.args.get("q", "")))


@admin_bp.post("/students/<int:student_id>/delete")
@admin_only
def delete_student(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        abort(404)

    reservation_query = Reservation.query.filter(
        or_(
            Reservation.student_id == student.id,
            Reservation.user_id == student.user_id if student.user_id is not None else Reservation.id == -1,
        )
    )
    loan_query = Loan.query.filter(
        or_(
            Loan.student_id == student.id,
            Loan.user_id == student.user_id if student.user_id is not None else Loan.id == -1,
        )
    )
    if reservation_query.first() or loan_query.first():
        flash("신청·대출 기록이 있는 학생은 영구 삭제할 수 없습니다. 학생 비활성화를 사용하세요.", "danger")
        return redirect(url_for("admin.students", q=request.args.get("q", "")))

    user = student.user
    if user:
        if user.role != "student":
            abort(409)
        ActivityLog.query.filter_by(actor_user_id=user.id).update(
            {"actor_user_id": None},
            synchronize_session=False,
        )
        PaperTicket.query.filter_by(issued_by=user.id).update(
            {"issued_by": None},
            synchronize_session=False,
        )
    InviteCode.query.filter_by(student_id=student.id).delete(synchronize_session=False)
    db.session.add(ActivityLog(
        actor_user_id=current_user.id,
        action="student_deleted",
        entity_type="student",
        entity_id=str(student.id),
        detail=f"학생 {student.name} ({student.internal_id}) 계정 및 명부 삭제",
    ))
    db.session.flush()
    if user:
        db.session.delete(user)
    db.session.delete(student)
    db.session.commit()
    flash("대출·신청 기록이 없는 학생을 영구 삭제했습니다.", "success")
    return redirect(url_for("admin.students", q=request.args.get("q", "")))


def _book_values():
    values = {
        key: request.form.get(key, "").strip()
        for key in ("title", "episode", "description")
    }
    try:
        values["total_stock"] = int(request.form.get("total_stock", "1"))
        values["available_stock"] = int(request.form.get("available_stock", str(values["total_stock"])))
    except ValueError:
        values["total_stock"] = values["available_stock"] = -1
    return values

def _save_cover():
    upload = request.files.get("cover")
    if not upload or not upload.filename:
        return None
    filename = secure_filename(upload.filename)
    extension = Path(filename).suffix.lower()
    if extension not in current_app.config["UPLOAD_EXTENSIONS"]:
        raise ValueError("jpg, jpeg, png, webp 파일만 업로드할 수 있습니다.")
    stored = f"{uuid4().hex}{extension}"
    folder = Path(current_app.instance_path) / "covers"
    folder.mkdir(parents=True, exist_ok=True)
    upload.save(folder / stored)
    return url_for("main.cover", filename=stored)

@admin_bp.route("/books", methods=["GET", "POST"])
@admin_only
def books():
    if request.method == "POST":
        values = _book_values()
        valid = (
            values["title"]
            and values["episode"]
            and values["total_stock"] >= 0
            and 0 <= values["available_stock"] <= values["total_stock"]
        )
        if not valid:
            flash("책 정보와 재고 수량을 올바르게 입력하세요.", "danger")
        else:
            try:
                cover_url = _save_cover()
            except ValueError as error:
                flash(str(error), "danger")
            else:
                book = Book(**values, author="", category="기타", cover_url=cover_url)
                db.session.add(book)
                db.session.flush()
                db.session.add(ActivityLog(actor_user_id=current_user.id, action="book_created", entity_type="book", entity_id=str(book.id)))
                db.session.commit()
                flash("책을 등록했습니다.", "success")
                return redirect(url_for("admin.books"))
    return render_template("admin/books.html", title="만화책 관리", books=Book.query.order_by(Book.created_at.desc()).all(), edit_book=None)

@admin_bp.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@admin_only
def edit_book(book_id):
    book = db.session.get(Book, book_id)
    if not book:
        abort(404)
    if request.method == "POST":
        values = _book_values()
        outstanding = Loan.query.filter_by(book_id=book.id, status="borrowed").count()
        approved_count = Reservation.query.filter_by(book_id=book.id, status="approved").count()
        valid = (
            values["title"]
            and values["episode"]
            and values["total_stock"] >= outstanding
            and 0 <= values["available_stock"] <= values["total_stock"] - outstanding
            and values["available_stock"] >= approved_count
        )
        if not valid:
            flash("대여 중인 권수와 수령 대기 예약을 고려해 책 정보와 재고를 입력하세요.", "danger")
        else:
            try:
                cover_url = _save_cover()
            except ValueError as error:
                flash(str(error), "danger")
            else:
                for key, value in values.items():
                    setattr(book, key, value)
                if cover_url:
                    book.cover_url = cover_url
                db.session.add(ActivityLog(actor_user_id=current_user.id, action="book_updated", entity_type="book", entity_id=str(book.id)))
                db.session.commit()
                flash("책 정보를 수정했습니다.", "success")
                return redirect(url_for("admin.books"))
    return render_template("admin/books.html", title="만화책 수정", books=Book.query.order_by(Book.created_at.desc()).all(), edit_book=book)

@admin_bp.post("/books/<int:book_id>/toggle")
@admin_only
def toggle_book(book_id):
    book = db.session.get(Book, book_id)
    if not book:
        abort(404)
    book.is_active = not book.is_active
    db.session.add(ActivityLog(actor_user_id=current_user.id, action="book_activated" if book.is_active else "book_deactivated", entity_type="book", entity_id=str(book.id)))
    db.session.commit()
    return redirect(url_for("admin.books"))

@admin_bp.get("/reservations")
@admin_only
def reservations():
    return redirect(url_for("admin.reservation_center"))

@admin_bp.route("/reservations/center", methods=["GET", "POST"])
@admin_only
def reservation_center():
    if request.method == "POST":
        reservation = db.session.get(Reservation, request.form.get("reservation_id", type=int))
        action = request.form.get("action")
        if reservation and reservation.status in {"pending", "approved"}:
            if action == "approve" and reservation.status == "pending":
                if not reservation.student or not reservation.student.is_active:
                    flash("활성 상태의 학생이 아닌 신청은 승인할 수 없습니다.", "warning")
                    return redirect(url_for("admin.reservations"))
                first_waiting = Reservation.query.filter_by(
                    book_id=reservation.book_id,
                    source="online",
                    status="pending",
                ).order_by(Reservation.queue_number, Reservation.id).first()
                if first_waiting and first_waiting.id != reservation.id:
                    flash(
                        f"도서 순번 {first_waiting.queue_number}번 신청을 먼저 처리해야 합니다.",
                        "warning",
                    )
                    return redirect(url_for("admin.reservations"))
                approved_count = Reservation.query.filter_by(
                    book_id=reservation.book_id,
                    status="approved",
                ).count()
                book = db.session.get(Book, reservation.book_id)
                if not book or not book.is_active or book.available_stock <= approved_count:
                    flash("신청을 승인할 수 있는 재고가 없습니다. 기존 수령 대기 예약이나 대출 반납을 확인하세요.", "warning")
                    return redirect(url_for("admin.reservations"))
                now = utc_now()
                claimed = Reservation.query.filter_by(id=reservation.id, status="pending").update(
                    {Reservation.status: "approved", Reservation.reviewed_at: now},
                    synchronize_session=False,
                )
                if claimed != 1:
                    db.session.rollback()
                    flash("신청 상태가 이미 변경되었습니다. 목록을 새로고침하세요.", "warning")
                    return redirect(url_for("admin.reservations"))
                reservation.status = "approved"
                reservation.reviewed_at = now
                flash("신청을 승인했습니다. 학생이 현장에서 수령하면 대여 처리하세요.", "success")
            elif action in {"reject", "cancel"}:
                now = utc_now()
                target_status = "cancelled" if action == "cancel" else "rejected"
                claimed = Reservation.query.filter_by(id=reservation.id, status=reservation.status).update(
                    {
                        Reservation.status: target_status,
                        Reservation.reviewed_at: now,
                        Reservation.cancelled_at: now if target_status == "cancelled" else reservation.cancelled_at,
                    },
                    synchronize_session=False,
                )
                if claimed != 1:
                    db.session.rollback()
                    flash("신청 상태가 이미 변경되었습니다. 목록을 새로고침하세요.", "warning")
                    return redirect(url_for("admin.reservations"))
                reservation.status = target_status
                reservation.reviewed_at = now
                if target_status == "cancelled":
                    reservation.cancelled_at = now
                flash("승인 신청을 취소했습니다." if action == "cancel" else "신청을 거절했습니다.", "success")
            else:
                flash("처리할 수 없는 예약 상태입니다.", "warning")
                return redirect(url_for("admin.reservations"))
            db.session.add(ActivityLog(actor_user_id=current_user.id, action="reservation_" + action, entity_type="reservation", entity_id=str(reservation.id)))
            db.session.commit()
        else:
            flash("이미 처리된 신청이거나 존재하지 않는 신청입니다.", "warning")
        return redirect(url_for("admin.reservations"))
    reservations = Reservation.query.order_by(
        Reservation.book_id,
        Reservation.queue_number,
        Reservation.requested_at.desc(),
    ).all()
    queue_reservations = Reservation.query.filter_by(
        source="online",
    ).filter(
        Reservation.status.in_(("pending", "approved")),
    ).order_by(
        Reservation.book_id,
        Reservation.queue_number,
    ).all()
    return render_template(
        "admin/reservations.html",
        title="예약 관리",
        reservations=reservations,
        queue_reservations=queue_reservations,
    )


def _checkout_details():
    receive_period = request.form.get("receive_period", type=int)
    return_period = request.form.get("return_period", type=int)
    snack_price = request.form.get("snack_price", type=int)
    snack_confirmed = request.form.get("snack_confirmed") == "1"
    return_date_value = request.form.get("return_date", "").strip()
    if not receive_period or not return_period or min(receive_period, return_period) < 1:
        return None, "수령·반납 교시를 올바르게 입력하세요."
    if max(receive_period, return_period) > 12:
        return None, "교시는 1교시부터 12교시 사이로 입력하세요."
    try:
        return_date = date.fromisoformat(return_date_value)
    except ValueError:
        return None, "반납 날짜를 올바르게 입력하세요."
    today = to_kst(utc_now()).date()
    if return_date != today:
        return None, "반납 날짜는 수령 당일로 입력해야 합니다."
    if return_period <= receive_period:
        return None, "반납 교시는 수령 교시 이후로 입력하세요."
    if return_period - receive_period > 3:
        return None, "대출은 수령 교시부터 최대 3교시까지만 가능합니다."
    if not snack_confirmed or snack_price is None or snack_price < 1000:
        return None, "1,000원 이상 간식 1개를 확인하고 가격을 입력해야 대여할 수 있습니다."
    return {
        "receive_period": receive_period,
        "return_period": return_period,
        "return_date": return_date,
        "snack_price": snack_price,
    }, None


def _has_other_active_item(student_id, book_id, exclude_reservation_id=None):
    query = Reservation.query.filter(
        Reservation.student_id == student_id,
        Reservation.book_id == book_id,
        Reservation.status.in_(("pending", "approved", "issued")),
    )
    if exclude_reservation_id is not None:
        query = query.filter(Reservation.id != exclude_reservation_id)
    return query.first() is not None


def _complete_checkout(reservation, details):
    now = utc_now()
    db.session.add(Loan(
        reservation=reservation,
        user_id=reservation.user_id,
        student_id=reservation.student_id,
        book_id=reservation.book_id,
        status="borrowed",
        borrowed_at=now,
    ))
    db.session.add(PaperTicket(
        reservation=reservation,
        ticket_number=uuid4().hex[:12].upper(),
        receive_period=details["receive_period"],
        return_date=details["return_date"],
        return_period=details["return_period"],
        is_issued=True,
        issued_at=now,
        issued_by=current_user.id,
    ))
    db.session.add(SnackExchange(
        reservation=reservation,
        required_quantity=1,
        submitted_quantity=1,
        unit_price=details["snack_price"],
        status="completed",
        checked_at=now,
        completed_at=now,
    ))
    reservation.status = "issued"
    db.session.add(ActivityLog(
        actor_user_id=current_user.id,
        action="loan_issued",
        entity_type="loan",
        entity_id=str(reservation.id),
    ))

@admin_bp.route("/operations", methods=["GET", "POST"])
@admin_only
def operations():
    reservations = Reservation.query.filter_by(status="approved").order_by(
        Reservation.book_id,
        Reservation.queue_number,
        Reservation.requested_at,
    ).all()
    loans = Loan.query.filter_by(status="borrowed").order_by(Loan.borrowed_at).all()
    students = Student.query.filter_by(is_active=True).order_by(Student.grade, Student.class_name, Student.name).all()
    books = Book.query.filter_by(is_active=True).order_by(Book.title).all()
    approved_counts = {}
    if books:
        approved_counts = dict(
            db.session.query(Reservation.book_id, db.func.count(Reservation.id))
            .filter(
                Reservation.book_id.in_([book.id for book in books]),
                Reservation.status == "approved",
            )
            .group_by(Reservation.book_id)
            .all()
        )

    if request.method == "POST":
        action = request.form.get("action")
        if action in {"issue_reserved", "walk_in"}:
            details, error = _checkout_details()
            if error:
                flash(error, "danger")
            elif action == "issue_reserved":
                reservation = db.session.get(Reservation, request.form.get("reservation_id", type=int))
                if not reservation or reservation.status != "approved":
                    flash("현장 수령 대기 중인 신청을 찾을 수 없습니다.", "warning")
                elif not reservation.student or not reservation.student.is_active:
                    flash("활성 상태의 학생만 대여 처리할 수 있습니다.", "danger")
                elif _has_other_active_item(reservation.student_id, reservation.book_id, reservation.id):
                    flash("학생에게 같은 책의 다른 신청이나 대여가 있어 처리할 수 없습니다.", "warning")
                else:
                    claimed = Reservation.query.filter_by(id=reservation.id, status="approved").update(
                        {Reservation.status: "issued"},
                        synchronize_session=False,
                    )
                    if claimed != 1:
                        db.session.rollback()
                        flash("신청 상태가 이미 변경되었습니다. 목록을 새로고침하세요.", "warning")
                        return redirect(url_for("admin.operations"))
                    checked_out = Book.query.filter(
                        Book.id == reservation.book_id,
                        Book.is_active.is_(True),
                        Book.available_stock > 0,
                    ).update(
                        {Book.available_stock: Book.available_stock - 1},
                        synchronize_session=False,
                    )
                    if checked_out != 1:
                        db.session.rollback()
                        flash("대출 가능한 실물 재고가 없습니다. 신청 재고와 대출 상태를 확인하세요.", "danger")
                        return redirect(url_for("admin.operations"))
                    reservation.status = "issued"
                    _complete_checkout(reservation, details)
                    db.session.commit()
                    flash(f"대여증 {reservation.paper_ticket.ticket_number}을 발급했습니다.", "success")
                    return redirect(url_for("admin.operations"))
            else:
                student = db.session.get(Student, request.form.get("student_id", type=int))
                book = db.session.get(Book, request.form.get("book_id", type=int))
                if not student or not student.is_active:
                    flash("활성 학생을 선택하세요.", "danger")
                elif not book or not book.is_active:
                    flash("대여 가능한 책을 선택하세요.", "danger")
                elif _has_other_active_item(student.id, book.id):
                    flash("학생에게 같은 책의 신청이나 대여가 이미 있습니다.", "warning")
                else:
                    approved_count = Reservation.query.filter_by(
                        book_id=book.id,
                        status="approved",
                    ).count()
                    if Reservation.query.filter_by(
                        book_id=book.id,
                        source="online",
                        status="pending",
                    ).first():
                        flash("이 도서는 온라인 대기 신청을 먼저 처리해야 합니다.", "warning")
                        return redirect(url_for("admin.operations"))
                    checked_out = Book.query.filter(
                        Book.id == book.id,
                        Book.is_active.is_(True),
                        Book.available_stock > approved_count,
                    ).update(
                        {Book.available_stock: Book.available_stock - 1},
                        synchronize_session=False,
                    )
                    if checked_out != 1:
                        db.session.rollback()
                        flash("현재 대여 가능한 재고가 없습니다.", "warning")
                    else:
                        now = utc_now()
                        reservation = Reservation(
                            user_id=student.user_id,
                            student_id=student.id,
                            book_id=book.id,
                            source="walk_in",
                            status="issued",
                            requested_at=now,
                            reviewed_at=now,
                            note="현장 즉시 대여",
                        )
                        db.session.add(reservation)
                        db.session.flush()
                        _complete_checkout(reservation, details)
                        db.session.add(ActivityLog(
                            actor_user_id=current_user.id,
                            action="walk_in_loan_issued",
                            entity_type="student",
                            entity_id=str(student.id),
                        ))
                        db.session.commit()
                        flash(f"현장 대여를 처리하고 대출증 {reservation.paper_ticket.ticket_number}을 발급했습니다.", "success")
                        return redirect(url_for("admin.operations"))
        elif action == "return_loan":
            loan = db.session.get(Loan, request.form.get("loan_id", type=int))
            if not loan or loan.status != "borrowed":
                flash("반납 처리할 대여 내역을 찾을 수 없습니다.", "warning")
            else:
                now = utc_now()
                claimed = Loan.query.filter_by(id=loan.id, status="borrowed").update(
                    {Loan.status: "returned", Loan.returned_at: now},
                    synchronize_session=False,
                )
                if claimed != 1:
                    db.session.rollback()
                    flash("이 대여는 이미 반납 처리되었습니다.", "warning")
                    return redirect(url_for("admin.operations"))
                restored = Book.query.filter(
                    Book.id == loan.book_id,
                    Book.available_stock < Book.total_stock,
                ).update(
                    {Book.available_stock: Book.available_stock + 1},
                    synchronize_session=False,
                )
                if restored != 1:
                    db.session.rollback()
                    flash("재고 상태가 변경되어 반납 처리하지 못했습니다. 관리자에게 문의하세요.", "danger")
                else:
                    loan.status = "returned"
                    loan.returned_at = now
                    loan.reservation.status = "returned"
                    db.session.add(ActivityLog(
                        actor_user_id=current_user.id,
                        action="loan_returned",
                        entity_type="loan",
                        entity_id=str(loan.id),
                    ))
                    db.session.commit()
                    flash("반납 처리했습니다. 재고에 반영했습니다.", "success")
                    return redirect(url_for("admin.operations"))
        else:
            flash("요청을 처리할 수 없습니다.", "danger")
        return redirect(url_for("admin.operations"))

    return render_template(
        "admin/operations.html",
        title="대여 운영",
        reservations=reservations,
        loans=loans,
        students=students,
        books=books,
        approved_counts=approved_counts,
        today=to_kst(utc_now()).date().isoformat(),
    )


@admin_bp.get("/loans/<int:loan_id>/ticket")
@admin_only
def print_ticket(loan_id):
    loan = db.session.get(Loan, loan_id)
    if not loan or not loan.reservation.paper_ticket:
        abort(404)
    return render_template("admin/ticket.html", title="대출증 인쇄", loan=loan, ticket=loan.reservation.paper_ticket)
