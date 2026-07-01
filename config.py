import os

# 自动加载项目根目录的 .env 文件
# 在所有入口点 (flask run / python run.py / start.ps1) 都会执行
_env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.isfile(_env_path):
    with open(_env_path, 'r', encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith('#') or '=' not in _line:
                continue
            _key, _, _val = _line.partition('=')
            _key = _key.strip()
            _val = _val.strip().strip('"').strip("'")
            if _key not in os.environ:
                os.environ[_key] = _val


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    WEREAD_API_KEY = os.environ.get('WEREAD_API_KEY', '')
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
    DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
