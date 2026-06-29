from app.extensions import db
from app.models import Book, Category
from app.weread.api import get_shelf


def parse_weread_category(category_str):
    if not category_str or '-' not in category_str:
        return None
    return category_str.split('-')[0]


def get_or_create_category(name):
    cat = Category.query.filter_by(name=name).first()
    if not cat:
        cat = Category(name=name)
        db.session.add(cat)
        db.session.flush()
    return cat.id


def import_shelf_to_db():
    data = get_shelf()
    books_data = data.get('books', [])

    imported = 0
    skipped = 0
    updated = 0

    for b in books_data:
        weread_id = str(b.get('bookId', ''))
        if not weread_id:
            continue

        existing = Book.query.filter_by(weread_book_id=weread_id).first()
        if existing:
            changed = False
            if not existing.cover_url and b.get('cover'):
                existing.cover_url = b.get('cover')
                changed = True
            if not existing.imported:
                existing.imported = True
                changed = True
            if changed:
                updated += 1
            else:
                skipped += 1
            continue

        title = b.get('title', '')
        author = b.get('author', '')
        cat_name = parse_weread_category(b.get('category', ''))
        cat_id = get_or_create_category(cat_name) if cat_name else None

        book = Book(
            title=title,
            author=author,
            cover_url=b.get('cover', ''),
            weread_book_id=weread_id,
            imported=True,
            category_id=cat_id,
            status='done' if b.get('finishReading', 0) else 'want',
        )
        db.session.add(book)
        imported += 1

        if imported % 100 == 0:
            db.session.commit()

    db.session.commit()

    return {
        'imported': imported,
        'skipped': skipped,
        'updated': updated,
        'total': len(books_data),
    }


def update_categories_from_api():
    data = get_shelf()
    books_data = data.get('books', [])

    matched = 0
    skipped = 0

    for b in books_data:
        weread_id = str(b.get('bookId', ''))
        if not weread_id:
            continue

        book = Book.query.filter_by(weread_book_id=weread_id).first()
        if not book:
            continue

        cat_name = parse_weread_category(b.get('category', ''))
        if cat_name:
            cat_id = get_or_create_category(cat_name)
            if book.category_id != cat_id:
                book.category_id = cat_id
                matched += 1
        else:
            skipped += 1

    db.session.commit()
    return {'matched': matched, 'skipped': skipped, 'total': len(books_data)}
