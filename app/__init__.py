"""
Flask 应用工厂
-------------
采用应用工厂模式（Application Factory Pattern），通过 create_app() 创建 Flask 实例。
所有 Blueprint、CLI 命令、Jinja 过滤器和错误处理器在此注册。

Blueprint 架构（7 个模块）：
  main       /            首页、书架浏览、书籍详情、阅读统计、划线搜索
  auth       /auth        用户登录/注册/API Key 管理
  admin      /admin       后台管理（图书/分类/笔记 CRUD）
  weread     /weread      微信读书 API 集成
  notes      /notes       个人笔记（Markdown 编辑、图片上传、导出）
  thinker    /thinkers    AI 哲学家对话
  ai_reader  /ai-reader   AI 阅读助手（对话/摘要/书评/分析/推荐）

启动方式：
  python run.py       → 直接运行（加载 .env, 校验配置, debug 由 FLASK_DEBUG 控制）
  flask run            → Flask CLI（config.py 顶层自动加载 .env）
  start.ps1            → PowerShell 脚本（禁用代理后调用 python run.py）
"""

import logging
import click
import markdown as md_lib
import bleach
from flask import Flask, render_template
from config import Config
from app.extensions import db, login_manager, migrate, csrf

# ── Markdown 渲染配置 ────────────────────────────────────────────────
# 允许的 HTML 标签和白名单属性，用于 bleach 安全过滤

ALLOWED_TAGS = ['h1','h2','h3','h4','h5','h6','p','br','strong','em',
    'a','ul','ol','li','code','pre','blockquote','img','hr','table',
    'thead','tbody','tr','th','td','span','div']

ALLOWED_ATTRS = {'img':['src','alt','title'], 'a':['href','title','target'],
    '*':['class']}


def render_markdown(text):
    """将 Markdown 文本渲染为安全 HTML（Jinja 过滤器和路由中使用）。"""
    html = md_lib.markdown(text or '', extensions=['extra', 'codehilite'])
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    """
    应用工厂函数。
    1. 校验必需配置（SECRET_KEY / DATABASE_URL）
    2. 初始化 Flask 扩展
    3. 注册 7 个 Blueprint
    4. 注册 Jinja 过滤器、错误处理器、CLI 命令
    """
    # ── 配置校验 ──
    if not config_class.SECRET_KEY or not config_class.SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            '缺少必需的环境变量：SECRET_KEY 和 DATABASE_URL。\n'
            '请在项目根目录创建 .env 文件，参考 .env.example'
        )
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── 扩展初始化 ──
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'  # 未登录用户重定向到前端登录

    # ── Blueprint 注册 ──
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.weread import bp as weread_bp
    app.register_blueprint(weread_bp, url_prefix='/weread')

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.notes import bp as notes_bp
    app.register_blueprint(notes_bp, url_prefix='/notes')

    from app.thinker import bp as thinker_bp
    app.register_blueprint(thinker_bp)

    from app.ai_reader import bp as ai_reader_bp
    app.register_blueprint(ai_reader_bp, url_prefix='/ai-reader')

    # ── Jinja 自定义过滤器 ──

    @app.template_filter('fmt_seconds')
    def fmt_seconds_filter(seconds):
        """格式化秒数为 X小时Y分钟。"""
        if seconds is None:
            return '--'
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        if hours > 0:
            return f'{hours}小时{mins}分钟'
        return f'{mins}分钟'

    @app.template_filter('fmt_compare')
    def fmt_compare_filter(val):
        """格式化环比变化率（小数 → 百分比文本）。"""
        if val is None:
            return ''
        pct = val * 100
        if val > 0:
            return f'较上期增长{pct:.0f}%'
        return f'较上期下降{abs(pct):.0f}%'

    app.jinja_env.filters['markdown'] = render_markdown

    # ── 错误处理 ──

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f'500 error: {e}', exc_info=True)
        return render_template('errors/500.html'), 500

    # ── CLI 命令 ──

    @app.cli.command('init-db')
    def init_db_command():
        """初始化数据库：创建默认管理员账号和 19 个微信读书分类。"""
        from app.cli import init_db
        init_db()

    @app.cli.command('import-weread')
    @click.option('--user-id', type=int, required=True, help='用户 ID')
    def import_weread_command(user_id):
        """CLI 导入微信读书书架。"""
        import click
        from app.weread.importer import import_shelf_to_db
        click.echo(f'正在为用户 {user_id} 从微信读书导入书架...')
        result = import_shelf_to_db(user_id)
        click.echo(f'完成！新增 {result["imported"]} 本，'
                    f'跳过 {result["skipped"]} 本，更新 {result["updated"]} 本')

    @app.cli.command('init-weread-categories')
    def init_weread_categories_command():
        """添加微信读书预设分类。"""
        from app.cli import add_weread_categories
        add_weread_categories()

    @app.cli.command('remove-old-categories')
    def remove_old_categories_command():
        """移除废弃的分类名称。"""
        from app.cli import remove_old_categories
        remove_old_categories()

    @app.cli.command('update-categories')
    @click.option('--user-id', type=int, required=True, help='用户 ID')
    def update_categories_command(user_id):
        """从微信读书 API 更新图书分类。"""
        import click
        from app.weread.importer import update_categories_from_api
        click.echo(f'正在为用户 {user_id} 从微信读书更新分类...')
        result = update_categories_from_api(user_id)
        click.echo(f'完成！{result["matched"]} 本已分类，{result["skipped"]} 本未匹配')

    @app.cli.command('import-highlights')
    @click.option('--user-id', type=int, default=None, help='用户 ID，不填则导入所有用户')
    def import_highlights_command(user_id):
        """CLI 批量导入划线笔记。"""
        import click
        click.echo('正在批量导入划线笔记...')
        from app.cli import import_all_highlights
        import_all_highlights(user_id=user_id)

    @app.cli.command('sync-stats')
    @click.option('--force', is_flag=True, help='强制全量重新同步')
    def sync_stats_command(force):
        """同步所有用户的阅读统计数据。--force 清除缓存重新拉取。"""
        from app.weread.stats_sync import sync_all_stats
        from app.models import ReadStat, DailyReadStat, User
        if force:
            ReadStat.query.delete()
            DailyReadStat.query.delete()
            db.session.commit()
            click.echo('已清除缓存的统计数据')
        users = User.query.all()
        for user in users:
            sync_all_stats(user.id)
            click.echo(f'已同步用户 {user.id}')
        click.echo('同步完成')

    return app
