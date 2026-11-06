"""静态页面：总览、作者查询、上传、上传码状态、下载、管理端。"""

from flask import Blueprint, current_app, send_from_directory

bp = Blueprint('pages', __name__)


@bp.route('/')
def index():
    return send_from_directory(current_app.static_folder, 'index.html')


@bp.route('/author')
def author_page():
    return send_from_directory(current_app.static_folder, 'author.html')


@bp.route('/maps')
def maps_page():
    return send_from_directory(current_app.static_folder, 'maps.html')


@bp.route('/map')
def map_detail_page():
    return send_from_directory(current_app.static_folder, 'map_detail.html')


@bp.route('/upload')
def upload_page():
    return send_from_directory(current_app.static_folder, 'upload.html')


@bp.route('/u/<code>')
def upload_status_page(code):
    return send_from_directory(current_app.static_folder, 'upload_status.html')


@bp.route('/download')
def download_page():
    return send_from_directory(current_app.static_folder, 'download.html')


@bp.route('/admin/uploads')
def admin_uploads_page():
    return send_from_directory(current_app.static_folder, 'admin_uploads.html')


@bp.route('/admin/overview')
def admin_overview_page():
    return send_from_directory(current_app.static_folder, 'admin_overview.html')


@bp.route('/admin/cases')
def admin_cases_page():
    return send_from_directory(current_app.static_folder, 'admin_cases.html')


@bp.route('/admin/download')
def admin_download_page():
    return send_from_directory(current_app.static_folder, 'admin_download.html')
