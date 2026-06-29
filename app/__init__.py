import logging
from flask import Flask, render_template
from config import Config
from app.extensions import db, login_manager, migrate, csrf

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
    def import_weread_command():
        import click
        from app.weread.importer import import_shelf_to_db
        click.echo('正在从微信读书导入书架...')
        result = import_shelf_to_db()
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
    def update_categories_command():
        import click
        from app.weread.importer import update_categories_from_api
        click.echo('正在从微信读书更新分类...')
        result = update_categories_from_api()
        click.echo(f'完成！{result["matched"]} 本已分类，{result["skipped"]} 本未匹配')

    @app.cli.command('import-highlights')
    def import_highlights_command():
        import click
        click.echo('正在批量导入划线笔记...')
        from app.cli import import_all_highlights
        import_all_highlights()

    return app
