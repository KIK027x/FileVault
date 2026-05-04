from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
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
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)

    parent = db.relationship('Folder', remote_side=[id], backref='subfolders')
    files = db.relationship('File', backref='folder', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Folder {self.name}>'

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)  # уникальное имя
    original_name = db.Column(db.String(200), nullable=False)  # оригинальное имя
    size = db.Column(db.BigInteger, nullable=False)  # размер в байтах
    mime_type = db.Column(db.String(100), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)

    def __repr__(self):
        return f'<File {self.original_name}>'