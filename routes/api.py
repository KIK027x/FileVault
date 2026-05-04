from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models import File, Folder
from app import db
import os
from config import Config

api_bp = Blueprint('api', __name__)

@api_bp.route('/files', methods=['GET'])
@login_required
def api_get_files():
    files = File.query.filter_by(user_id=current_user.id).all()
    result = []
    for f in files:
        result.append({
            'id': f.id,
            'original_name': f.original_name,
            'size': f.size,
            'mime_type': f.mime_type,
            'upload_date': f.upload_date.isoformat(),
            'folder_id': f.folder_id
        })
    return jsonify(result)

@api_bp.route('/folders', methods=['GET'])
@login_required
def api_get_folders():
    folders = Folder.query.filter_by(user_id=current_user.id).all()
    result = []
    for f in folders:
        result.append({
            'id': f.id,
            'name': f.name,
            'parent_id': f.parent_id,
            'created_at': f.created_at.isoformat()
        })
    return jsonify(result)

@api_bp.route('/upload', methods=['POST'])
@login_required
def api_upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    from routes.files import allowed_file
    if file and allowed_file(file.filename):
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        unique_filename = f"{current_user.id}_{filename}"
        filepath = os.path.join(Config.UPLOAD_FOLDER, unique_filename)

        file.save(filepath)

        new_file = File(
            filename=unique_filename,
            original_name=filename,
            size=os.path.getsize(filepath),
            mime_type=file.content_type or 'application/octet-stream',
            user_id=current_user.id
        )
        db.session.add(new_file)
        db.session.commit()

        return jsonify({'success': True, 'file_id': new_file.id})
    else:
        return jsonify({'error': 'Invalid file type'}), 400

@api_bp.route('/files/<int:file_id>', methods=['DELETE'])
@login_required
def api_delete_file(file_id):
    file = File.query.filter_by(id=file_id, user_id=current_user.id).first()
    if not file:
        return jsonify({'error': 'File not found'}), 404

    filepath = os.path.join(Config.UPLOAD_FOLDER, file.filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    db.session.delete(file)
    db.session.commit()
    return jsonify({'success': True})