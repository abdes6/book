from flask import render_template, redirect, url_for, flash, request, session, send_file
from flask_login import login_user, logout_user, login_required
from app.admin import bp
from app.admin.captcha import generate_captcha
from app.forms import LoginForm, BookForm, CategoryForm
from app.models import User, Book, Category, db


@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        if form.captcha.data.upper() != session.get('captcha', ''):
            flash('验证码错误', 'danger')
            return render_template('admin/login.html', form=form)
        admin = User.query.filter_by(username=form.username.data).first()
        if admin and admin.check_password(form.password.data):
            login_user(admin)
            session.pop('captcha', None)
            return redirect(url_for('admin.dashboard'))
        flash('用户名或密码错误', 'danger')
    return render_template('admin/login.html', form=form)


@bp.route('/captcha')
def captcha():
    code, buf = generate_captcha()
    session['captcha'] = code
    return send_file(buf, mimetype='image/png')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('admin.login'))


@bp.route('/')
@login_required
def dashboard():
    return render_template('admin/dashboard.html',
        total_books=Book.query.count(),
        reading_count=Book.query.filter_by(status='reading').count(),
        done_count=Book.query.filter_by(status='done').count(),
        category_count=Category.query.count(),
        recent_books=Book.query.order_by(Book.created_at.desc()).limit(5).all())


@bp.route('/books')
@login_required
def books():
    page = request.args.get('page', 1, int)
    pagination = Book.query.order_by(Book.created_at.desc()).paginate(page=page, per_page=10)
    return render_template('admin/books.html', pagination=pagination)


@bp.route('/books/create', methods=['GET', 'POST'])
@login_required
def book_create():
    form = BookForm()
    form.category_id.choices = [(0, '无分类')] + [(c.id, c.name) for c in Category.query.all()]
    if form.validate_on_submit():
        book = Book(title=form.title.data, author=form.author.data,
                    isbn=form.isbn.data, cover_url=form.cover_url.data,
                    summary=form.summary.data, rating=form.rating.data or 0,
                    status=form.status.data, notes=form.notes.data,
                    category_id=form.category_id.data if form.category_id.data else None)
        db.session.add(book)
        db.session.commit()
        flash('添加成功', 'success')
        return redirect(url_for('admin.books'))
    return render_template('admin/book_form.html', form=form, title='新增书籍')


@bp.route('/books/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def book_edit(id):
    book = Book.query.get_or_404(id)
    form = BookForm(obj=book)
    form.category_id.choices = [(0, '无分类')] + [(c.id, c.name) for c in Category.query.all()]
    if form.validate_on_submit():
        for attr in ['title', 'author', 'isbn', 'cover_url', 'summary', 'status', 'notes']:
            setattr(book, attr, getattr(form, attr).data)
        book.rating = form.rating.data or 0
        book.category_id = form.category_id.data if form.category_id.data else None
        db.session.commit()
        flash('更新成功', 'success')
        return redirect(url_for('admin.books'))
    form.category_id.data = book.category_id or 0
    return render_template('admin/book_form.html', form=form, title='编辑书籍')


@bp.route('/books/<int:id>/delete', methods=['POST'])
@login_required
def book_delete(id):
    db.session.delete(Book.query.get_or_404(id))
    db.session.commit()
    flash('已删除', 'success')
    return redirect(url_for('admin.books'))


@bp.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    form = CategoryForm()
    if form.validate_on_submit():
        if Category.query.filter_by(name=form.name.data).first():
            flash('分类已存在', 'danger')
        else:
            db.session.add(Category(name=form.name.data))
            db.session.commit()
            flash('添加成功', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/categories.html', form=form, categories=Category.query.all())


@bp.route('/categories/<int:id>/delete', methods=['POST'])
@login_required
def category_delete(id):
    cat = Category.query.get_or_404(id)
    Book.query.filter_by(category_id=id).update({Book.category_id: None})
    db.session.delete(cat)
    db.session.commit()
    flash('已删除', 'success')
    return redirect(url_for('admin.categories'))


@bp.route('/import-weread', methods=['POST'])
@login_required
def import_weread():
    from app.weread.importer import import_shelf_to_db
    try:
        result = import_shelf_to_db(user_id=1)
        flash(f'导入成功！新增 {result["imported"]} 本，跳过 {result["skipped"]} 本，更新 {result["updated"]} 本', 'success')
    except Exception as e:
        flash(f'导入失败：{e}', 'danger')
    return redirect(url_for('admin.dashboard'))


@bp.route('/categorize-weread', methods=['POST'])
@login_required
def categorize_weread():
    from app.weread.importer import categorize_all_books
    try:
        result = categorize_all_books()
        flash(f'自动分类完成：{result["categorized"]} 本已分类，{result["skipped"]} 本未匹配', 'success')
    except Exception as e:
        flash(f'分类失败：{e}', 'danger')
    return redirect(url_for('admin.dashboard'))


@bp.route('/notes')
@login_required
def notes():
    page = request.args.get('page', 1, int)
    pagination = Book.query.filter(Book.notes.isnot(None), Book.notes != '')\
        .order_by(Book.updated_at.desc()).paginate(page=page, per_page=10)
    return render_template('admin/notes.html', pagination=pagination)


@bp.route('/notes/<int:id>/delete', methods=['POST'])
@login_required
def note_delete(id):
    book = Book.query.get_or_404(id)
    book.notes = None
    db.session.commit()
    flash('已删除', 'success')
    return redirect(url_for('admin.notes'))
