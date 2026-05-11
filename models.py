from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    # Модель пользователя
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    files = db.relationship('File', backref='owner', lazy=True, cascade='all, delete-orphan')
    folders = db.relationship('Folder', backref='owner', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Folder(db.Model):
    # Модель папки
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)

    parent = db.relationship('Folder', remote_side=[id], backref='subfolders')
    files = db.relationship('File', backref='folder', lazy=True, cascade='all, delete-orphan')

    def total_size(self):
        # Подсчет общего размера папки
        total = sum(f.size for f in self.files)
        for subfolder in self.subfolders:
            total += subfolder.total_size()
        return total

    def __repr__(self):
        return f'<Folder {self.name}>'

class File(db.Model):
    # Модель файла
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)  # уникальное имя
    original_name = db.Column(db.String(200), nullable=False)  # оригинальное имя
    size = db.Column(db.BigInteger, nullable=False)  # размер в байтах
    mime_type = db.Column(db.String(100), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)

    # Связь many-to-many с тегами
    tags = db.relationship('Tag', secondary='file_tags', back_populates='files')

    def __repr__(self):
        return f'<File {self.original_name}>'

class Tag(db.Model):
    # Модель тега
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    files = db.relationship('File', secondary='file_tags', back_populates='tags')

    def __repr__(self):
        return f'<Tag {self.name}>'

# Таблица связи файлов и тегов
file_tags = db.Table('file_tags',
    db.Column('file_id', db.Integer, db.ForeignKey('file.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)