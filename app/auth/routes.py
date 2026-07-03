from urllib.parse import urlparse, urljoin
from flask import render_template, redirect, url_for, flash, request, session, send_file
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app.forms import UserLoginForm, RegisterForm
from app.extensions import db, frontend_login_required, rate_limit
from app.models import User
from app.admin.captcha import generate_captcha


def _is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@bp.route('/login', methods=['GET', 'POST'])
@rate_limit('login', max_attempts=10, window=300)
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = UserLoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            session.permanent = True
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
            if next_page and _is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('main.index'))
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


@bp.route('/captcha')
@rate_limit('captcha', max_attempts=30, window=60)
def captcha():
    code, buf = generate_captcha()
    session['captcha'] = code
    return send_file(buf, mimetype='image/png')


@bp.route('/register', methods=['GET', 'POST'])
@rate_limit('register', max_attempts=5, window=300)
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if form.captcha.data.upper() != session.get('captcha', ''):
            flash('验证码错误', 'danger')
            return render_template('auth/register.html', form=form)
        if User.query.filter_by(email=form.email.data).first() or \
           User.query.filter_by(username=form.username.data).first():
            flash('注册信息无效，请检查后重试', 'danger')
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
        session.pop('captcha', None)
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


@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('auth.login'))