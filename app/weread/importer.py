from app.extensions import db
from app.models import Book
from app.weread.api import get_shelf


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

        book = Book(
            title=b.get('title', ''),
            author=b.get('author', ''),
            cover_url=b.get('cover', ''),
            weread_book_id=weread_id,
            imported=True,
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
