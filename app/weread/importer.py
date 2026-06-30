from datetime import datetime

from app.extensions import db
from app.models import Book, Category, Highlight
from app.weread.api import get_shelf, get_bookmarklist


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


def import_shelf_to_db(user_id):
    data = get_shelf()
    books_data = data.get('books', [])

    imported = 0
    skipped = 0
    updated = 0

    for b in books_data:
        weread_id = str(b.get('bookId', ''))
        if not weread_id:
            continue

        existing = Book.query.filter_by(weread_book_id=weread_id, user_id=user_id).first()
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
            user_id=user_id,
            title=title,
            author=author,
            cover_url=b.get('cover', ''),
            weread_book_id=weread_id,
            imported=True,
            category_id=cat_id,
            status='done' if b.get('finishReading', 0) else 'reading',
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


def update_categories_from_api(user_id):
    data = get_shelf()
    books_data = data.get('books', [])

    matched = 0
    skipped = 0

    for b in books_data:
        weread_id = str(b.get('bookId', ''))
        if not weread_id:
            continue

        book = Book.query.filter_by(weread_book_id=weread_id, user_id=user_id).first()
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


def import_highlights_for_book(book, user_id):
    if not book.weread_book_id:
        return {'imported': 0, 'total': 0}

    existing_ids = {h.weread_bookmark_id for h in Highlight.query.with_entities(
        Highlight.weread_bookmark_id).filter_by(book_id=book.id).all()}

    data = get_bookmarklist(book.weread_book_id)
    chapters_map = {}
    for ch in data.get('chapters', []):
        chapters_map[ch.get('chapterUid', 0)] = ch.get('title', '')

    imported = 0
    for item in data.get('updated', []):
        bmid = str(item.get('bookmarkId', ''))
        if not bmid or bmid in existing_ids:
            continue
        ch_uid = item.get('chapterUid', 0)
        hl = Highlight(
            user_id=user_id,
            book_id=book.id,
            weread_bookmark_id=bmid,
            chapter_uid=ch_uid,
            chapter_title=chapters_map.get(ch_uid, ''),
            mark_text=item.get('markText', ''),
            range=item.get('range', ''),
            color_style=item.get('colorStyle', 0),
            created_at=datetime.fromtimestamp(item.get('createTime', 0)) if item.get('createTime') else None,
        )
        db.session.add(hl)
        imported += 1

    db.session.commit()
    return {'imported': imported, 'total': len(data.get('updated', []))}
