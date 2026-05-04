# routes/files.py — работа с файлами и папками

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, abort
from flask_login import login_required, current_user
from models import File, Folder
from forms import UploadForm
from app import db
import os
from werkzeug.utils import secure_filename
from config import Config

files_bp = Blueprint('files', __name__)

# Разрешённые типы файлов
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'xlsx', 'pptx'}

def allowed_file(filename):
    # Проверяем, разрешён ли тип файла
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def make_unique_filename(original_name, user_id, folder_id=None):

    #Генерирует уникальное имя файла.
    name, ext = os.path.splitext(original_name)
    counter = 1
    new_name = original_name

    while True:
        # Формируем имя для сохранения на диске
        unique_filename = f"{user_id}_{new_name}"
        filepath = os.path.join(Config.UPLOAD_FOLDER, unique_filename)

        # Если такого файла нет — используем это имя
        if not os.path.exists(filepath):
            return unique_filename, new_name

        # Иначе увеличиваем счётчик и пробуем снова
        if counter == 1:
            new_name = f"{name}_1{ext}"
        else:
            new_name = f"{name}_{counter}{ext}"
        counter += 1

@files_bp.route('/')
def index():
    # Главная — перенаправляем на дашборд или вход
    if current_user.is_authenticated:
        return redirect(url_for('files.dashboard'))
    return redirect(url_for('auth.login'))

@files_bp.route('/dashboard')
@login_required
def dashboard():
    # Получаем текущую папку из URL
    folder_id = request.args.get('folder', type=int)
    current_folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first() if folder_id else None

    # Загружаем файлы и папки в этой директории
    files = File.query.filter_by(folder_id=folder_id, user_id=current_user.id).all()
    folders = Folder.query.filter_by(parent_id=folder_id, user_id=current_user.id).all()

    # Подготовка формы загрузки
    upload_form = UploadForm()
    upload_form.set_folder_choices(current_user.id)

    # Хлебные крошки (путь к папке)
    breadcrumbs = []
    if current_folder:
        f = current_folder
        while f:
            breadcrumbs.insert(0, (f.id, f.name))
            f = f.parent

    return render_template('dashboard.html',
                           files=files,
                           folders=folders,
                           current_folder=current_folder,
                           breadcrumbs=breadcrumbs,
                           upload_form=upload_form)

@files_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    # Получаем форму
    form = UploadForm()
    form.set_folder_choices(current_user.id)

    # ❌ Убираем проверку валидации формы
    # if not form.validate_on_submit():

    # Берём folder_id напрямую из POST
    folder_id = request.form.get('folder_id', type=int, default=0)

    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Выберите файл для загрузки.', 'danger')
        return redirect(url_for('files.dashboard'))

    if not allowed_file(file.filename):
        flash('Тип файла не поддерживается.', 'danger')
        return redirect(url_for('files.dashboard'))

    # Генерируем уникальное имя (чтобы не перезаписывать)
    unique_filename, original_name = make_unique_filename(file.filename, current_user.id, folder_id)

    # Сохраняем файл на диск
    filepath = os.path.join(Config.UPLOAD_FOLDER, unique_filename)
    file.save(filepath)

    # Добавляем запись в базу
    new_file = File(
        filename=unique_filename,
        original_name=original_name,
        size=os.path.getsize(filepath),
        mime_type=file.content_type or 'application/octet-stream',
        user_id=current_user.id,
        folder_id=folder_id if folder_id != 0 else None
    )
    db.session.add(new_file)
    db.session.commit()

    flash(f'✅ "{original_name}" загружен!', 'success')
    return redirect(url_for('files.dashboard', folder=folder_id))

@files_bp.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    # Скачивание файла
    file = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    filepath = os.path.join(Config.UPLOAD_FOLDER, file.filename)
    if not os.path.exists(filepath):
        abort(404)
    return send_from_directory(Config.UPLOAD_FOLDER, file.filename, as_attachment=True)

@files_bp.route('/delete/file/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    # Удаление файла
    file = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    filepath = os.path.join(Config.UPLOAD_FOLDER, file.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(file)
    db.session.commit()
    flash('🗑 Файл удалён.', 'info')
    return redirect(url_for('files.dashboard', folder=file.folder_id))

@files_bp.route('/create_folder', methods=['POST'])
@login_required
def create_folder():
    # Создание папки
    name = request.form.get('folder_name', '').strip()
    parent_id = request.form.get('parent_id', type=int, default=None)

    if not name:
        flash('Введите имя папки.', 'danger')
        return redirect(url_for('files.dashboard', folder=parent_id))

    # Проверяем, нет ли такой папки уже
    if Folder.query.filter_by(name=name, parent_id=parent_id, user_id=current_user.id).first():
        flash(f'Папка "{name}" уже существует.', 'warning')
        return redirect(url_for('files.dashboard', folder=parent_id))

    folder = Folder(name=name, user_id=current_user.id, parent_id=parent_id)
    db.session.add(folder)
    db.session.commit()
    flash(f'📁 Папка "{name}" создана.', 'success')
    return redirect(url_for('files.dashboard', folder=parent_id))

@files_bp.route('/delete/folder/<int:folder_id>', methods=['POST'])
@login_required
def delete_folder(folder_id):
    # Удаление папки
    folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()

    # Удаляем все файлы в папке
    files_in_folder = File.query.filter_by(folder_id=folder.id).all()
    for f in files_in_folder:
        filepath = os.path.join(Config.UPLOAD_FOLDER, f.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        db.session.delete(f)

    # Удаляем подпапки рекурсивно
    def delete_subfolders(parent_folder):
        subfolders = Folder.query.filter_by(parent_id=parent_folder.id).all()
        for sub in subfolders:
            delete_subfolders(sub)  # рекурсивный вызов
            db.session.delete(sub)

    delete_subfolders(folder)

    # Удаляем саму папку
    db.session.delete(folder)
    db.session.commit()
    flash('🗑 Папка удалена.', 'info')
    return redirect(url_for('files.dashboard', folder=folder.parent_id))