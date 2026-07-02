"""
Flask 扩展模块
-------------
所有 Flask 扩展插件在此统一初始化，通过应用工厂延迟绑定到 app 实例。
采用"创建-初始化"模式：先创建未绑定实例，在 create_app() 中调用 init_app()。
"""

from functools import wraps
from flask import redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

# ── 扩展实例（未绑定 app） ──────────────────────────────────────────
db = SQLAlchemy()           # ORM 与数据库连接管理
login_manager = LoginManager()  # 用户会话与认证
migrate = Migrate()         # Alembic 数据库迁移
csrf = CSRFProtect()        # CSRF 跨站请求伪造防护


# ── 前端登录装饰器 ──────────────────────────────────────────────────
# 与 Flask-Login 的 @login_required 不同，此装饰器将未登录用户重定向到
# 前端登录页 /auth/login，而非后台 /admin/login

def frontend_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
