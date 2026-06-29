from functools import wraps
from datetime import datetime
from flask import render_template, jsonify, redirect, url_for
from flask import current_app
from flask_login import current_user
from app.main import bp
from app.models import Book, Category, Highlight, db
from app.weread.api import get_shelf, get_readdata
from app.weread.importer import import_highlights_for_book


def frontend_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@bp.route('/')
@frontend_login_required
def index():
    weread_books = []
    try:
        data = get_shelf()
        if data and 'books' in data:
            sorted_books = sorted(data.get('books', []), key=lambda b: b.get('readUpdateTime', 0) or 0, reverse=True)
            for b in sorted_books[:10]:
                local = Book.query.filter_by(weread_book_id=str(b.get('bookId', ''))).first()
                weread_books.append({
                    'title': b.get('title', ''),
                    'author': b.get('author', ''),
                    'cover': b.get('cover', ''),
                    'book_id': b.get('bookId', ''),
                    'finished': b.get('finishReading', 0),
                    'local_id': local.id if local else None,
                })
    except Exception:
        weread_books = None
    return render_template('index.html', weread_books=weread_books)


@bp.route('/stats')
@frontend_login_required
def stats():
    try:
        weekly = get_readdata('weekly')
    except Exception:
        weekly = None
    try:
        monthly = get_readdata('monthly')
    except Exception:
        monthly = None
    try:
        annually = get_readdata('annually')
    except Exception:
        annually = None
    try:
        overall = get_readdata('overall')
    except Exception:
        overall = None
    return render_template('stats.html', weekly=weekly, monthly=monthly,
                           annually=annually, overall=overall)


@bp.route('/books')
@frontend_login_required
def book_list():
    from flask import request
    cid = request.args.get('category', type=int)
    sf = request.args.get('status')
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    query = Book.query
    if cid:
        query = query.filter_by(category_id=cid)
    if sf in ('reading', 'done'):
        query = query.filter_by(status=sf)
    if q:
        query = query.filter(Book.title.contains(q) | Book.author.contains(q))
    pagination = query.order_by(Book.created_at.desc()).paginate(page=page, per_page=12)
    return render_template('books/list.html', pagination=pagination,
                           categories=Category.query.all(), current_category=cid,
                           current_status=sf, q=q)


@bp.route('/books/<int:id>')
@frontend_login_required
def book_detail(id):
    book = Book.query.get_or_404(id)
    book.last_viewed_at = datetime.now()
    db.session.commit()
    return render_template('books/detail.html', book=book)


@bp.route('/books/<int:id>/highlights')
@frontend_login_required
def book_highlights(id):
    book = Book.query.get_or_404(id)
    exists = Highlight.query.filter_by(book_id=book.id).first()
    if not exists and book.weread_book_id:
        try:
            import_highlights_for_book(book)
        except Exception as e:
            current_app.logger.warning('导入划线失败: %s', e)
            return jsonify({'highlights': [], 'error': '导入划线失败: ' + str(e)}), 500

    highlights = Highlight.query.filter_by(book_id=book.id).order_by(
        Highlight.chapter_uid, Highlight.created_at).all()

    color_map = {0: '#F9F3A7', 1: '#B5D8B5', 2: '#A7C7E7', 3: '#F0C0C0', 4: '#F5C792', 5: '#E8D5B7'}

    groups = {}
    for hl in highlights:
        key = hl.chapter_uid or 0
        if key not in groups:
            groups[key] = {'chapter_title': hl.chapter_title or '其他', 'items': []}
        groups[key]['items'].append({
            'id': hl.id,
            'mark_text': hl.mark_text,
            'color': color_map.get(hl.color_style, color_map[0]),
            'created_at': hl.created_at.strftime('%Y-%m-%d') if hl.created_at else '',
        })

    return jsonify({'highlights': list(groups.values())})
