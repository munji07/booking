"""Flask extension singletons."""
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "main.index"
login_manager.login_message = "로그인 후 이용할 수 있습니다."
csrf = CSRFProtect()
migrate = Migrate()
