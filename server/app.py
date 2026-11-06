"""服务端入口：创建 Flask 应用、注册蓝图并完成一次性初始化。

模块拆分：
- settings.py      配置、环境变量、共享知识库
- common.py        版本/偏移归一化与上报字段校验
- db.py            建表/迁移与聚合重建
- legacy_report.py 旧版 /api/report 的日志解析
- upload_store.py  上传存储、zip 校验、崩溃区/KK 区解析、到期清理
- diagnosis.py     服务端诊断与上传入库
- blueprints/      页面、上传、管理端、上报统计、聚合标注
"""

import os
import sys

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from flask import Flask

from blueprints.admin import bp as admin_bp
from blueprints.aggregates import bp as aggregates_bp
from blueprints.pages import bp as pages_bp
from blueprints.reports import bp as reports_bp
from blueprints.uploads import bp as uploads_bp, upload_too_large
from db import init_db, rebuild_aggregates
from settings import MAX_UPLOAD_BYTES
from upload_store import cleanup_expired_uploads


def create_app():
    application = Flask(__name__, static_folder='static')
    application.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_BYTES + 2 * 1024 * 1024

    application.register_blueprint(pages_bp)
    application.register_blueprint(uploads_bp)
    application.register_blueprint(admin_bp)
    application.register_blueprint(reports_bp)
    application.register_blueprint(aggregates_bp)
    application.register_error_handler(413, upload_too_large)

    init_db()
    rebuild_aggregates()
    cleanup_expired_uploads(force=True)
    return application


app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2234, debug=True)
