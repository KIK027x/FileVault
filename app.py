from flask import Flask
from flask_login import LoginManager
from config import Config
from models import db, User
import os

def create_app():
    # Создание Flask приложения
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # Создание папки для загрузок
    if not os.path.exists(Config.UPLOAD_FOLDER):
        os.makedirs(Config.UPLOAD_FOLDER)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from routes.auth import auth_bp
    from routes.files import files_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    with app.app_context():
        db.create_all()

        # Создание тестового пользователя
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)