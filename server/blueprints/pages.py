"""静态页面：总览、作者查询、上传、上传码状态、管理端。"""

from flask import Blueprint, current_app, send_from_directory

bp = Blueprint('pages', __name__)


@bp.route('/')
def index():
    return send_from_directory(current_app.static_folder, 'index.html')


@bp.route('/author')
def author_page():
    return send_from_directory(current_app.static_folder, 'author.html')


@bp.route('/upload')
def upload_page():
    return send_from_directory(current_app.static_folder, 'upload.html')


@bp.route('/u/<code>')
def upload_status_page(code):
    return send_from_directory(current_app.static_folder, 'upload_status.html')


@bp.route('/admin/uploads')
def admin_uploads_page():
    return send_from_directory(current_app.static_folder, 'admin_uploads.html')
