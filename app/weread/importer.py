"""
微信读书数据导入与同步
---------------------
管理从微信读书 API 到本地数据库的数据流转。

核心流程：
1. 注册/首次登录 → import_shelf_to_db() 全量导入
2. 每次访问书架页 → sync_shelf_for_user() 增量同步（300s 缓存 TTL）
3. 首次查看书籍详情 → import_highlights_for_book() 按需导入划线

关键设计：
- 软删除：书架同步不会物理删除本地数据，而是设置 shelved=False
- 重新上架：如果用户在微信读书重新添加已下架的书，shelved 自动恢复为 True
- 分类匹配：通过 parse_weread_category() 从微信读书的 category 字段提取一级分类名
- 进度同步：同时提取 readUpdateTime 作为最近阅读时间
"""

import time
from datetime import datetime

from app.extensions import db
from app.models import Book, Category, Highlight
from app.weread.api import get_shelf, get_bookmarklist

# 进程内缓存：避免同一进程短时间内重复调用 API
_sync_cache = {}


def parse_weread_category(category_str):
    """
    解析微信读书分类字符串。
    微信读书返回 "文学-经典文学" 格式，提取一级分类 "文学"。
    """
    if not category_str or '-' not in category_str:
        return None
    return category_str.split('-')[0]


def get_or_create_category(name):
    """获取或创建分类，返回 category_id。"""
    cat = Category.query.filter_by(name=name).first()
    if not cat:
        cat = Category(name=name)
        db.session.add(cat)
        db.session.flush()
    return cat.id


def import_shelf_to_db(user_id, api_key=None):
    """
    全量导入：将微信读书书架全部图书写入本地数据库。
    适用于首次注册或手动 CLI 导入场景。
    - weread_book_id 用于去重：已存在的跳过
    - 每 100 本提交一次事务，控制内存
    """
    data = get_shelf(api_key=api_key)
    books_data = data.get('books', [])

    imported = 0
    skipped = 0
    updated = 0
    seen = set()

    for b in books_data:
        weread_id = str(b.get('bookId', ''))
        if not weread_id or weread_id in seen:
            continue
        seen.add(weread_id)

        existing = Book.query.filter_by(weread_book_id=weread_id, user_id=user_id).first()
        if existing:
            # 已存在：补全可能缺失的封面和 imported 标记
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
            progress=b.get('progress', 0),
            last_read_at=datetime.fromtimestamp(b['readUpdateTime']) if b.get('readUpdateTime') else None,
        )
        db.session.add(book)
        imported += 1

        # 批量提交，控制事务大小
        if imported % 100 == 0:
            db.session.commit()

    db.session.commit()
    _sync_cache[user_id] = time.time()

    return {
        'imported': imported,
        'skipped': skipped,
        'updated': updated,
        'total': len(books_data),
    }


def sync_shelf_for_user(user_id, ttl_seconds=300):
    """
    增量同步：对比微信读书书架和本地数据库，执行增/改/软删。
    每次访问书架页时调用，受 300 秒 TTL 缓存保护。

    同步策略：
    - 新增：API 有、本地无 → 创建 Book 记录
    - 更新：API 有、本地有 → 更新状态、进度、封面、shelved 标记
    - 软删：本地有、API 无 → shelved=False（不物理删除）
    """
    now = time.time()
    last = _sync_cache.get(user_id, 0)
    if now - last < ttl_seconds:
        return {'synced': False, 'reason': 'cached'}

    data = get_shelf()
    books_data = data.get('books', [])
    api_ids = set()

    imported = 0
    updated = 0
    deleted = 0

    for b in books_data:
        weread_id = str(b.get('bookId', ''))
        if not weread_id or weread_id in api_ids:
            continue
        api_ids.add(weread_id)

        existing = Book.query.filter_by(weread_book_id=weread_id, user_id=user_id).first()
        if existing:
            # ── 增量更新：只同步非用户编辑的字段 ──
            # status / title / author / category 由用户手动管理，不同步覆盖
            changed = False
            if not existing.shelved:
                existing.shelved = True   # 重新上架
                changed = True
            if not existing.cover_url and b.get('cover'):
                existing.cover_url = b.get('cover')
                changed = True
            progress_new = b.get('progress', 0)
            if existing.progress != progress_new:
                existing.progress = progress_new
                changed = True
            if b.get('readUpdateTime'):
                lr = datetime.fromtimestamp(b['readUpdateTime'])
                if existing.last_read_at != lr:
                    existing.last_read_at = lr
                    changed = True
            if not existing.imported:
                existing.imported = True
                changed = True
            if changed:
                updated += 1
            continue

        # ── 新增图书 ──
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
            progress=b.get('progress', 0),
            last_read_at=datetime.fromtimestamp(b['readUpdateTime']) if b.get('readUpdateTime') else None,
        )
        db.session.add(book)
        imported += 1

    # ── 软删除：微信读书已移除的书 ──
    local_books = Book.query.filter(
        Book.user_id == user_id,
        Book.weread_book_id.isnot(None),
        Book.weread_book_id != ''
    ).all()
    for book in local_books:
        if book.weread_book_id not in api_ids:
            if book.shelved:            # 只处理尚未标记的
                book.shelved = False
                deleted += 1

    db.session.commit()
    _sync_cache[user_id] = now

    return {
        'imported': imported,
        'updated': updated,
        'deleted': deleted,
        'total': len(books_data),
    }


def update_categories_from_api(user_id, api_key=None):
    """从微信读书 API 更新图书分类信息。api_key 为空时使用当前登录用户的 key。"""
    data = get_shelf(api_key=api_key)
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


def categorize_all_books():
    """为所有用户的藏书自动匹配微信读书分类（admin 后台调用）。"""
    from app.models import User
    users = User.query.all()
    total_matched = 0
    total_skipped = 0
    for user in users:
        if not user.weread_api_key:
            continue
        result = update_categories_from_api(user.id, api_key=user.weread_api_key)
        total_matched += result['matched']
        total_skipped += result['skipped']
    return {'categorized': total_matched, 'skipped': total_skipped}


def import_all_highlights_for_user(user_id, api_key=None):
    """
    批量导入：为用户所有未导入划线的书籍批量导入微信读书划线。
    使用 ~Book.highlights.any() 跳过已有划线的书籍，避免重复 API 调用。
    api_key 用于无请求上下文的场景（如注册时），为空则从 current_user 获取。
    返回 {imported: N, books_processed: M}。
    """
    books_to_import = Book.query.filter(
        Book.user_id == user_id,
        Book.weread_book_id.isnot(None),
        Book.weread_book_id != '',
        ~Book.highlights.any()
    ).all()

    imported_total = 0
    for i, book in enumerate(books_to_import):
        try:
            result = import_highlights_for_book(book, user_id, api_key=api_key)
            imported_total += result['imported']
        except Exception:
            db.session.rollback()
            continue

    return {'imported': imported_total, 'books_processed': len(books_to_import)}


def import_highlights_for_book(book, user_id, api_key=None):
    """
    按需导入：为指定书籍导入微信读书划线笔记。
    首次访问书籍详情页时触发，weread_bookmark_id 用于去重。
    api_key 用于无请求上下文的场景（如注册时），为空则从 current_user 获取。
    返回 {imported: N, total: M}。
    """
    if not book.weread_book_id:
        return {'imported': 0, 'total': 0}

    # 获取已存在的 bookmark_id 集合，用于去重
    existing_ids = {h.weread_bookmark_id for h in Highlight.query.with_entities(
        Highlight.weread_bookmark_id).filter_by(book_id=book.id, user_id=user_id).all()}

    data = get_bookmarklist(book.weread_book_id, api_key=api_key)

    # 构建章节映射：chapterUid → 章节标题
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
