import logging
import click
import markdown as md_lib
import bleach
from flask import Flask, render_template
from config import Config
from app.extensions import db, login_manager, migrate, csrf

ALLOWED_TAGS = ['h1','h2','h3','h4','h5','h6','p','br','strong','em',
    'a','ul','ol','li','code','pre','blockquote','img','hr','table',
    'thead','tbody','tr','th','td','span','div']

ALLOWED_ATTRS = {'img':['src','alt','title'], 'a':['href','title','target'],
    '*':['class']}


def render_markdown(text):
    html = md_lib.markdown(text or '', extensions=['extra', 'codehilite'])
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.login_view = 'admin.login'

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

    @app.template_filter('fmt_seconds')
    def fmt_seconds_filter(seconds):
        if seconds is None:
            return '--'
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        if hours > 0:
            return f'{hours}小时{mins}分钟'
        return f'{mins}分钟'

    @app.template_filter('fmt_compare')
    def fmt_compare_filter(val):
        if val is None:
            return ''
        pct = val * 100
        if val > 0:
            return f'较上期增长{pct:.0f}%'
        return f'较上期下降{abs(pct):.0f}%'

    app.jinja_env.filters['markdown'] = render_markdown

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f'500 error: {e}', exc_info=True)
        return render_template('errors/500.html'), 500

    @app.cli.command('init-db')
    def init_db_command():
        from app.cli import init_db
        init_db()

    @app.cli.command('import-weread')
    @click.option('--user-id', type=int, required=True, help='用户 ID')
    def import_weread_command(user_id):
        import click
        from app.weread.importer import import_shelf_to_db
        click.echo(f'正在为用户 {user_id} 从微信读书导入书架...')
        result = import_shelf_to_db(user_id)
        click.echo(f'完成！新增 {result["imported"]} 本，'
                    f'跳过 {result["skipped"]} 本，更新 {result["updated"]} 本')

    @app.cli.command('init-weread-categories')
    def init_weread_categories_command():
        from app.cli import add_weread_categories
        add_weread_categories()

    @app.cli.command('remove-old-categories')
    def remove_old_categories_command():
        from app.cli import remove_old_categories
        remove_old_categories()

    @app.cli.command('update-categories')
    @click.option('--user-id', type=int, required=True, help='用户 ID')
    def update_categories_command(user_id):
        import click
        from app.weread.importer import update_categories_from_api
        click.echo(f'正在为用户 {user_id} 从微信读书更新分类...')
        result = update_categories_from_api(user_id)
        click.echo(f'完成！{result["matched"]} 本已分类，{result["skipped"]} 本未匹配')

    @app.cli.command('import-highlights')
    @click.option('--user-id', type=int, default=None, help='用户 ID，不填则导入所有用户')
    def import_highlights_command(user_id):
        import click
        click.echo('正在批量导入划线笔记...')
        from app.cli import import_all_highlights
        import_all_highlights(user_id=user_id)

    @app.cli.command('sync-stats')
    @click.option('--force', is_flag=True, help='强制全量重新同步')
    def sync_stats_command(force):
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
