"""
Flask 扩展模块
-------------
所有 Flask 扩展插件在此统一初始化，通过应用工厂延迟绑定到 app 实例。
采用"创建-初始化"模式：先创建未绑定实例，在 create_app() 中调用 init_app()。
"""

import time
import functools
from flask import redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

# ── 扩展实例（未绑定 app） ──────────────────────────────────────────
db = SQLAlchemy()           # ORM 与数据库连接管理
login_manager = LoginManager()  # 用户会话与认证
migrate = Migrate()         # Alembic 数据库迁移
csrf = CSRFProtect()        # CSRF 跨站请求伪造防护


# ── 简易频率限制 ────────────────────────────────────────────────────

_attempts = {}


def _rate_limit_check(key, max_attempts=5, window=300):
    now = time.time()
    history = _attempts.get(key, [])
    history = [t for t in history if now - t < window]
    _attempts[key] = history
    if len(history) >= max_attempts:
        return False
    history.append(now)
    return True


def rate_limit(action, max_attempts=5, window=300):
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            client_ip = request.remote_addr or 'unknown'
            key = f'{action}:{client_ip}'
            if not _rate_limit_check(key, max_attempts, window):
                flash('操作过于频繁，请稍后再试', 'danger')
                if request.method == 'POST':
                    return redirect(request.path)
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── 前端登录装饰器 ──────────────────────────────────────────────────

def frontend_login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
