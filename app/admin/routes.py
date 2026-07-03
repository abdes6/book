from flask import render_template, redirect, url_for, flash, request, session
from flask_login import logout_user, login_required, current_user
from app.admin import bp
from app.forms import BookForm, CategoryForm
from app.models import User, Book, Category, db


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect('/auth/login')


@bp.route('/')
@login_required
def dashboard():
    """后台概览：全站统计 + 最近活跃的书籍。"""
    return render_template('admin/dashboard.html',
        total_books=Book.query.count(),
        reading_count=Book.query.filter_by(status='reading').count(),
        done_count=Book.query.filter_by(status='done').count(),
        category_count=Category.query.count(),
        recent_books=Book.query.filter_by(user_id=current_user.safe_id).order_by(
            Book.last_read_at.is_(None),
            Book.last_read_at.desc(),
            Book.created_at.desc()
        ).limit(5).all())


@bp.route('/books')
@login_required
def books():
    page = request.args.get('page', 1, int)
    q = request.args.get('q', '').strip()
    query = Book.query.filter_by(user_id=current_user.safe_id)
    if q:
        query = query.filter(Book.title.contains(q) | Book.author.contains(q))
    pagination = query.order_by(Book.created_at.desc()).paginate(page=page, per_page=10)
    return render_template('admin/books.html', pagination=pagination, q=q)


@bp.route('/books/create', methods=['GET', 'POST'])
@login_required
def book_create():
    form = BookForm()
    form.category_id.choices = [(0, '无分类')] + [(c.id, c.name) for c in Category.query.all()]
    if form.validate_on_submit():
        book = Book(title=form.title.data, author=form.author.data,
                    user_id=current_user.safe_id,
                    cover_url=form.cover_url.data,
                    status=form.status.data,
                    category_id=form.category_id.data if form.category_id.data else None)
        db.session.add(book)
        db.session.commit()
        flash('添加成功', 'success')
        return redirect(url_for('admin.books'))
    return render_template('admin/book_form.html', form=form, title='新增书籍')


@bp.route('/books/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def book_edit(id):
    book = Book.query.filter_by(id=id, user_id=current_user.safe_id).first_or_404()
    form = BookForm(obj=book)
    form.category_id.choices = [(0, '无分类')] + [(c.id, c.name) for c in Category.query.all()]
    if form.validate_on_submit():
        for attr in ['title', 'author', 'cover_url', 'status']:
            setattr(book, attr, getattr(form, attr).data)
        book.category_id = form.category_id.data if form.category_id.data else None
        db.session.commit()
        flash('更新成功', 'success')
        return redirect(url_for('admin.books'))
    form.category_id.data = book.category_id or 0
    return render_template('admin/book_form.html', form=form, title='编辑书籍')


@bp.route('/books/<int:id>/delete', methods=['POST'])
@login_required
def book_delete(id):
    db.session.delete(Book.query.filter_by(id=id, user_id=current_user.safe_id).first_or_404())
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


@bp.route('/notes')
@login_required
def notes():
    from app.models import Note
    page = request.args.get('page', 1, int)
    cid = request.args.get('category', type=int)
    query = Note.query.join(Book, Note.book_id == Book.id)
    if cid:
        query = query.filter(Book.category_id == cid)
    pagination = query.order_by(Note.updated_at.desc()).paginate(page=page, per_page=10)
    categories = Category.query.all()
    return render_template('admin/notes.html', pagination=pagination,
                           categories=categories, current_category=cid)


@bp.route('/notes/<int:id>/delete', methods=['POST'])
@login_required
def note_delete(id):
    from app.models import Note
    note = Note.query.get_or_404(id)
    db.session.delete(note)
    db.session.commit()
    flash('已删除', 'success')
    return redirect(url_for('admin.notes'))
