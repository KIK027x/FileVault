from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, abort, send_file
from flask_login import login_required, current_user
from models import File, Folder, Tag
from forms import UploadForm
from app import db
import os
from werkzeug.utils import secure_filename
from config import Config
import zipfile
import io

files_bp = Blueprint('files', __name__)

# Список разрешённых расширений
ALLOWED_EXTENSIONS = {
    # Текстовые
    'txt', 'rtf', 'doc', 'docx', 'odt', 'pdf', 'md',
    # Изображения
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp',
    # Аудио
    'mp3', 'wav', 'aac', 'ogg', 'flac',
    # Видео
    'mp4', 'avi', 'mov', 'wmv', 'mkv', 'webm',
    # Архивы
    'zip', 'rar', '7z', 'tar', 'gz', 'bz2',
    # Данные
    'json', 'csv', 'xml', 'yaml', 'yml',
    # Презентации
    'ppt', 'pptx', 'odp',
    # Таблицы
    'xls', 'xlsx', 'ods',
    # Базы данных
    'db', 'sqlite', 'sqlite3', 'mdb', 'accdb',
    # Программы (опционально, если хочешь разрешить)
    'py', 'js', 'html', 'css'
}


def allowed_file(filename):
    # Проверка типа файла
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def make_unique_filename(original_name, user_id, folder_id=None):
    # Генерация уникального имени файла
    name, ext = os.path.splitext(original_name)
    counter = 1
    new_name = original_name

    while True:
        unique_filename = f"{user_id}_{new_name}"
        filepath = os.path.join(Config.UPLOAD_FOLDER, unique_filename)

        if not os.path.exists(filepath):
            return unique_filename, new_name

        if counter == 1:
            new_name = f"{name}_1{ext}"
        else:
            new_name = f"{name}_{counter}{ext}"
        counter += 1


@files_bp.route('/')
def index():
    # Главная страница
    if current_user.is_authenticated:
        return redirect(url_for('files.dashboard'))
    return redirect(url_for('auth.login'))


@files_bp.route('/dashboard')
@login_required
def dashboard():
    # Страница файлового менеджера
    folder_id = request.args.get('folder', type=int)
    current_folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first() if folder_id else None

    files = File.query.filter_by(folder_id=folder_id, user_id=current_user.id).all()
    folders = Folder.query.filter_by(parent_id=folder_id, user_id=current_user.id).all()

    upload_form = UploadForm()
    upload_form.set_folder_choices(current_user.id)

    # Хлебные крошки
    breadcrumbs = []
    if current_folder:
        f = current_folder
        while f:
            breadcrumbs.insert(0, (f.id, f.name))
            f = f.parent

    # Недавние файлы
    recent_files = File.query.filter_by(user_id=current_user.id).order_by(File.upload_date.desc()).limit(5).all()

    return render_template('dashboard.html',
                           files=files,
                           folders=folders,
                           current_folder=current_folder,
                           breadcrumbs=breadcrumbs,
                           upload_form=upload_form,
                           recent_files=recent_files)


@files_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    # Загрузка файла
    form = UploadForm()
    form.set_folder_choices(current_user.id)

    folder_id = request.form.get('folder_id', type=int, default=0)
    tags_str = request.form.get('tags', '').strip()

    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Выберите файл для загрузки.', 'danger')
        return redirect(url_for('files.dashboard'))

    if not allowed_file(file.filename):
        flash('Тип файла не поддерживается.', 'danger')
        return redirect(url_for('files.dashboard'))

    unique_filename, original_name = make_unique_filename(file.filename, current_user.id, folder_id)

    filepath = os.path.join(Config.UPLOAD_FOLDER, unique_filename)
    file.save(filepath)

    new_file = File(
        filename=unique_filename,
        original_name=original_name,
        size=os.path.getsize(filepath),
        mime_type=file.content_type or 'application/octet-stream',
        user_id=current_user.id,
        folder_id=folder_id if folder_id != 0 else None
    )
    db.session.add(new_file)
    db.session.flush()

    # Добавление тегов
    if tags_str:
        tag_names = [t.strip().lower() for t in tags_str.split(',') if t.strip()]
        for tag_name in tag_names:
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.session.add(tag)
            if tag not in new_file.tags:
                new_file.tags.append(tag)

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


@files_bp.route('/download-zip/<int:folder_id>')
@login_required
def download_zip(folder_id):
    # Архивация папки в ZIP
    folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        def add_folder_to_zip(zipf, folder, base_path=''):
            for file in folder.files:
                filepath = os.path.join(Config.UPLOAD_FOLDER, file.filename)
                if os.path.exists(filepath):
                    arcname = os.path.join(base_path, file.original_name)
                    zipf.write(filepath, arcname)
            for subfolder in folder.subfolders:
                add_folder_to_zip(zipf, subfolder, os.path.join(base_path, subfolder.name))

        add_folder_to_zip(zipf, folder)

    memory_file.seek(0)
    return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name=f'{folder.name}.zip')


@files_bp.route('/view/<int:file_id>')
@login_required
def view_file(file_id):
    # Просмотр содержимого файла
    file = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    filepath = os.path.join(Config.UPLOAD_FOLDER, file.filename)
    if not os.path.exists(filepath):
        abort(404)

    text_types = {'txt', 'json', 'csv', 'xml', 'yaml', 'yml', 'md', 'py', 'js', 'html', 'css'}
    ext = file.original_name.rsplit('.', 1)[-1].lower()
    if ext not in text_types:
        flash('Файл не является текстовым.', 'danger')
        return redirect(url_for('files.dashboard', folder=file.folder_id))

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        flash('Не удалось прочитать файл (ошибка кодировки).', 'danger')
        return redirect(url_for('files.dashboard', folder=file.folder_id))

    return render_template('view_file.html', file=file, content=content)


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

    # Удаление файлов в папке
    files_in_folder = File.query.filter_by(folder_id=folder.id).all()
    for f in files_in_folder:
        filepath = os.path.join(Config.UPLOAD_FOLDER, f.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        db.session.delete(f)

    # Удаление подпапок рекурсивно
    def delete_subfolders(parent_folder):
        subfolders = Folder.query.filter_by(parent_id=parent_folder.id).all()
        for sub in subfolders:
            delete_subfolders(sub)
            db.session.delete(sub)

    delete_subfolders(folder)

    db.session.delete(folder)
    db.session.commit()
    flash('🗑 Папка удалена.', 'info')
    return redirect(url_for('files.dashboard', folder=folder.parent_id))


@files_bp.route('/search')
@login_required
def search():
    # Поиск по файлам и тегам
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('files.dashboard'))

    # Ищем по имени файла
    files_by_name = File.query.filter(
        File.original_name.contains(query),
        File.user_id == current_user.id
    ).all()

    # Ищем по тегам
    files_by_tag = File.query.join(File.tags).filter(
        Tag.name.contains(query),
        File.user_id == current_user.id
    ).all()

    # Объединяем результаты и убираем дубликаты
    all_files = list(set(files_by_name + files_by_tag))

    return render_template('search_results.html', files=all_files, query=query)


@files_bp.route('/gallery')
@login_required
def gallery():
    # Галерея изображений
    image_files = File.query.filter(
        File.mime_type.like('image/%'),
        File.user_id == current_user.id
    ).all()

    return render_template('gallery.html', files=image_files)


@files_bp.route('/export/<fmt>')
@login_required
def export(fmt):
    # Экспорт файлов в CSV или JSON
    files = File.query.filter_by(user_id=current_user.id).all()

    if fmt == 'csv':
        import csv
        memory_file = io.StringIO()
        writer = csv.writer(memory_file)
        writer.writerow(['ID', 'Original Name', 'Size', 'Upload Date', 'Folder'])
        for f in files:
            folder_name = f.folder.name if f.folder else 'Корень'
            writer.writerow([f.id, f.original_name, f.size, f.upload_date, folder_name])

        memory_file.seek(0)
        from flask import Response
        return Response(
            memory_file.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=files.csv'}
        )

    elif fmt == 'json':
        import json
        data = []
        for f in files:
            folder_name = f.folder.name if f.folder else 'Корень'
            data.append({
                'id': f.id,
                'original_name': f.original_name,
                'size': f.size,
                'upload_date': f.upload_date.isoformat(),
                'folder': folder_name
            })

        return Response(
            json.dumps(data, ensure_ascii=False, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=files.json'}
        )

    else:
        abort(404)