from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app.forms import UserLoginForm, RegisterForm
from app.extensions import db, frontend_login_required
from app.models import User


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = UserLoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            if not user.weread_api_key:
                return redirect(url_for('auth.update_key'))
            if not user.shelf_synced:
                from app.weread.importer import import_shelf_to_db
                import_shelf_to_db(user.id)
                user.shelf_synced = True
                db.session.commit()
            # 每次登录都后台导入全部未导入的划线
            from app.weread.importer import import_all_highlights_for_user
            import threading
            t = threading.Thread(
                target=import_all_highlights_for_user,
                args=(user.id,), kwargs={'api_key': user.weread_api_key},
                daemon=True
            )
            t.start()
            flash('登录成功', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        flash('邮箱或密码错误', 'danger')
    return render_template('auth/login.html', form=form)


@bp.route('/update-key', methods=['GET', 'POST'])
@frontend_login_required
def update_key():
    if request.method == 'POST':
        key = request.form.get('weread_api_key', '').strip()
        if not key:
            flash('请输入 API Key', 'danger')
            return render_template('auth/update_key.html')
        current_user.weread_api_key = key
        db.session.flush()
        if not current_user.shelf_synced:
            from app.weread.importer import import_shelf_to_db, import_all_highlights_for_user
            import_shelf_to_db(current_user.id)
            import_all_highlights_for_user(current_user.id)
            current_user.shelf_synced = True
        db.session.commit()
        flash('API Key 已保存，书架已同步', 'success')
        return redirect(url_for('main.index'))
    return render_template('auth/update_key.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('该邮箱已被注册', 'danger')
            return render_template('auth/register.html', form=form)
        if User.query.filter_by(username=form.username.data).first():
            flash('该用户名已被使用', 'danger')
            return render_template('auth/register.html', form=form)
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        user.weread_api_key = form.weread_api_key.data
        db.session.add(user)
        db.session.flush()
        from app.weread.importer import import_shelf_to_db, import_all_highlights_for_user
        import_shelf_to_db(user.id, api_key=form.weread_api_key.data)
        user.shelf_synced = True
        db.session.commit()
        login_user(user)
        flash('注册成功，书架同步完成，划线正在后台导入...', 'success')
        # 划线导入在后台线程执行，避免阻塞注册请求
        import threading
        t = threading.Thread(
            target=import_all_highlights_for_user,
            args=(user.id,), kwargs={'api_key': form.weread_api_key.data},
            daemon=True
        )
        t.start()
        return redirect(url_for('main.index'))
    return render_template('auth/register.html', form=form)


@bp.route('/logout')
def logout():
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('main.index'))