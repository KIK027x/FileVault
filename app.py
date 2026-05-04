# app.py — главный файл приложения
from flask import Flask
from flask_login import LoginManager
from config import Config
from models import db, User
import os

def create_app():
    # Создаём приложение Flask
    app = Flask(__name__)
    app.config.from_object(Config)  # Подключаем настройки

    # Подключаем базу данных
    db.init_app(app)

    # 🆕 Создаём папку для загрузок, если её нет
    if not os.path.exists(Config.UPLOAD_FOLDER):
        os.makedirs(Config.UPLOAD_FOLDER)

    # Настройка входа/регистрации
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # Куда идти, если не авторизован

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))  # Загружаем пользователя по ID

    # Регистрируем модули (страницы)
    from routes.auth import auth_bp
    from routes.files import files_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    # Создаём таблицы в БД при первом запуске
    with app.app_context():
        db.create_all()

        # Если нет пользователей — создаём тестового
        if not User.query.first():
            from werkzeug.security import generate_password_hash
            test_user = User(
                username='test',
                email='test@example.com',
                password_hash=generate_password_hash('password')
            )
            db.session.add(test_user)
            db.session.commit()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)