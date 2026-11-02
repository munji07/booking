"""책마루 Flask application package."""
from pathlib import Path
import click

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError

from .config import get_config_class
from .extensions import csrf, db, login_manager, migrate
from .models import User
from werkzeug.security import generate_password_hash
from .time_utils import format_kst


@login_manager.user_loader
def load_user(user_id):
    try:
        raw_id, separator, raw_version = user_id.partition(":")
        user = db.session.get(User, int(raw_id))
        version = int(raw_version) if separator else 1
        if user and user.auth_version == version:
            return user
        return None
    except (TypeError, ValueError):
        return None


def create_app(config_class=None):
    """Create and configure the Flask application."""
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(__name__, instance_relative_config=True, root_path=str(Path(__file__).resolve().parent))
    app.config.from_object(config_class or get_config_class())
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.setdefault("PROJECT_ROOT", str(project_root))

    db.init_app(app)
    login_manager.init_app(app)
    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import redirect, request, url_for
        endpoint = "admin.login" if request.path.startswith("/admin") else "student.login"
        return redirect(url_for(endpoint, next=request.full_path))
    csrf.init_app(app)
    migrate.init_app(app, db)

    from .blueprints.admin import admin_bp
    from .blueprints.main import main_bp
    from .blueprints.student import student_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_helpers():
        return {"format_kst": format_kst}

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return render_template("errors/error.html", title="보안 확인 필요", message="요청을 다시 확인해 주세요."), 400

    @app.errorhandler(404)
    def handle_not_found(error):
        return render_template("errors/error.html", title="페이지를 찾을 수 없습니다", message="요청하신 페이지가 존재하지 않습니다."), 404

    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables for local development."""
        with app.app_context():
            db.create_all()
        print("책마루 데이터베이스 테이블을 준비했습니다.")

    @app.cli.command("create-admin")
    @click.option("--username", prompt="Admin username")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin_command(username, password):
        """Create an administrator account."""
        with app.app_context():
            username = username.strip()
            if User.query.filter_by(username=username).first():
                raise click.ClickException("Username already exists.")
            user = User(username=username, password_hash=generate_password_hash(password), role="admin")
            db.session.add(user)
            db.session.commit()
        click.echo("Administrator created.")

    return app
