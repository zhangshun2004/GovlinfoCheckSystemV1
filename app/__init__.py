from flask import Flask
import os
from .extensions import db, migrate, login_manager
from .main.routes import bp as main_bp
from .auth.routes import bp as auth_bp
from .admin.routes import bp as admin_bp
from .crawler.routes import bp as crawler_bp

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, 'static'),
        template_folder=os.path.join(BASE_DIR, 'templates')
    )
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'devkey')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///govlinfo.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(BASE_DIR, 'migrations'))
    login_manager.init_app(app)
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(crawler_bp, url_prefix='/crawler')
    
    return app

