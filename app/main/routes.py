from flask import render_template
from app.main import bp
from app.models import Book, Category
from app.weread.api import get_shelf


@bp.route('/')
def index():
    recent_books = Book.query.order_by(Book.created_at.desc()).limit(8).all()
    reading_books = Book.query.filter_by(status='reading').order_by(Book.updated_at.desc()).limit(4).all()

    weread_books = []
    try:
        data = get_shelf()
        if data and 'books' in data:
            for b in data.get('books', [])[:8]:
                weread_books.append({
                    'title': b.get('title', ''),
                    'author': b.get('author', ''),
                    'cover': b.get('cover', ''),
                    'book_id': b.get('bookId', ''),
                    'finished': b.get('finishReading', 0),
                })
    except Exception:
        weread_books = None

    return render_template('index.html', recent_books=recent_books,
                           reading_books=reading_books, weread_books=weread_books)


@bp.route('/books')
def book_list():
    from flask import request
    cid = request.args.get('category', type=int)
    sf = request.args.get('status')
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    query = Book.query
    if cid:
        query = query.filter_by(category_id=cid)
    if sf in ('want', 'reading', 'done'):
        query = query.filter_by(status=sf)
    if q:
        query = query.filter(Book.title.contains(q) | Book.author.contains(q))
    pagination = query.order_by(Book.created_at.desc()).paginate(page=page, per_page=12)
    return render_template('books/list.html', pagination=pagination,
                           categories=Category.query.all(), current_category=cid,
                           current_status=sf, q=q)


@bp.route('/books/<int:id>')
def book_detail(id):
    return render_template('books/detail.html', book=Book.query.get_or_404(id))
