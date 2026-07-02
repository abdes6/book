"""
应用配置模块
-----------
所有敏感信息（密钥、数据库密码）通过环境变量注入，不在代码中硬编码。
.env 文件在模块导入时自动加载，确保 flask run / python run.py / start.ps1 三个入口统一生效。
"""

import os

# ── 自动加载 .env 文件 ──────────────────────────────────────────────
# 放在 Config 类定义之前，确保 os.environ 在类属性求值前已填充
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
    """Flask 配置类，通过 `app.config.from_object(Config)` 注入。"""

    # Flask 会话签名密钥，生产环境必须使用随机值
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # MySQL 数据库连接（通过 PyMySQL 驱动）
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # CSRF 保护（Flask-WTF）
    WTF_CSRF_ENABLED = True

    # 微信读书 API Key — 每个用户有自己的 key，此处仅为默认值
    WEREAD_API_KEY = os.environ.get('WEREAD_API_KEY', '')

    # DeepSeek AI API（兼容 OpenAI SDK）
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
    DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
