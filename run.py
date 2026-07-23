"""
应用入口
-------
启动方式：python run.py 或通过 setup.ps1 脚本调用。

执行流程：
1. 从 config.py 导入 Config（触发 .env 加载和 os.environ 填充）
2. 校验必需环境变量存在（SECRET_KEY）
3. 调用 create_app() 创建 Flask 实例
4. 检测并自动初始化数据库（首次运行时建表 + 种子数据）
5. 以 debug 模式启动（由 FLASK_DEBUG 环境变量控制，默认关闭）
"""

import os
import sys

from config import Config  # 触发 config.py 顶层的 .env 加载逻辑

if __name__ == '__main__':
    # ── 启动前校验：必需环境变量不能为空 ──
    missing = []
    if not Config.SECRET_KEY:
        missing.append('SECRET_KEY')
    if not Config.SQLALCHEMY_DATABASE_URI:
        missing.append('DATABASE_URL')
    if missing:
        print(f'[FATAL] 缺少必需的环境变量: {", ".join(missing)}', file=sys.stderr)
        print('请创建 .env 文件并设置以上变量，参考 .env.example', file=sys.stderr)
        sys.exit(1)

    if not Config.DEEPSEEK_API_KEY:
        print('[WARN] DEEPSEEK_API_KEY 未设置，AI 功能（哲学家对话/读书助手）不可用')

    from app import create_app
    app = create_app()

    # ── 首次运行自动初始化数据库 ──
    with app.app_context():
        # SQLite 需要确保存储目录存在
        db_path = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_path.startswith('sqlite'):
            db_dir = os.path.dirname(db_path.replace('sqlite:///', ''))
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
        import sqlalchemy as sa
        from app.extensions import db
        inspector = sa.inspect(db.engine)
        if 'users' not in inspector.get_table_names():
            db.create_all()
            from app.cli import init_db
            init_db()
            print('[INFO] 数据库表与种子数据已自动初始化')

    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug)
