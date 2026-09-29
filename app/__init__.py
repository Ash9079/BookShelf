from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from config import config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
cache = Cache()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


def create_app(env='default'):
    app = Flask(__name__)
    app.config.from_object(config[env])

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    cache.init_app(app)

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.books import books_bp
    from app.routes.recommendations import recs_bp
    from app.routes.user import user_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp,  url_prefix='/auth')
    app.register_blueprint(books_bp)
    app.register_blueprint(recs_bp,  url_prefix='/recommendations')
    app.register_blueprint(user_bp,  url_prefix='/user')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Template filters
    @app.template_filter('cover_url')
    def cover_url_filter(path):
        if not path:
            return '/static/img/no-cover.svg'
        if path.startswith('http'):
            return path
        if path.startswith('/'):
            return 'https://covers.openlibrary.org' + path
        return '/static/img/no-cover.svg'

    @app.template_filter('pages_fmt')
    def pages_fmt_filter(n):
        if n and int(n) > 0:
            return f'{int(n):,} pages'
        return 'N/A'

    # Context processor — inject admin counts
    @app.context_processor
    def inject_admin_counts():
        try:
            from app.models import Book, User
            return dict(
                admin_book_count=Book.query.count(),
                admin_user_count=User.query.count(),
            )
        except Exception:
            return dict(admin_book_count=0, admin_user_count=0)

    return app
