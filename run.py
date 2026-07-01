import os
import sys

from config import Config  # 触发 .env 加载

if __name__ == '__main__':
    missing = []
    if not Config.SECRET_KEY:
        missing.append('SECRET_KEY')
    if not Config.SQLALCHEMY_DATABASE_URI:
        missing.append('DATABASE_URL')
    if not Config.DEEPSEEK_API_KEY:
        missing.append('DEEPSEEK_API_KEY')
    if missing:
        print(f'[FATAL] 缺少必需的环境变量: {", ".join(missing)}', file=sys.stderr)
        print('请创建 .env 文件并设置以上变量，参考 .env.example', file=sys.stderr)
        sys.exit(1)

    from app import create_app
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app = create_app()
    app.run(debug=debug)
