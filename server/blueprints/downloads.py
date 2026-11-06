"""公开下载配置：客户端下载页读取当前网盘链接。"""

from flask import Blueprint, jsonify

from download_store import get_download

bp = Blueprint('downloads', __name__)


@bp.route('/api/download', methods=['GET'])
def download_info():
    return jsonify(get_download())
