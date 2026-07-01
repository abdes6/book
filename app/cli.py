from app.extensions import db
from app.models import User, Category

WEREAD_CATEGORIES = [
    '文学', '精品小说', '历史', '哲学宗教', '心理', '社会文化',
    '经济理财', '科学技术', '计算机', '个人成长', '艺术',
    '生活百科', '人物传记', '政治军事', '教育学习', '医学健康',
    '漫画', '男生小说', '童书',
]

OLD_CATEGORIES = ['科幻', '技术', '哲学', '传记', '经济', '社会',
                  '政治', '科学', '生活', '教育', '悬疑推理']


def init_db():
    if not User.query.filter_by(is_admin=True).first():
        admin = User(username='admin', email='admin@book.com', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)

    _init_categories(WEREAD_CATEGORIES)
    db.session.commit()
    print('初始化完成：admin / admin123，19个微信读书分类')


def _init_categories(names):
    for name in names:
        if not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name))


def add_weread_categories():
    _init_categories(WEREAD_CATEGORIES)
    db.session.commit()
    print(f'微信读书分类已就绪（{len(WEREAD_CATEGORIES)}个）')


def remove_old_categories():
    cleared = Book.query.filter(Book.category_id.isnot(None)).update(
        {Book.category_id: None})
    deleted = Category.query.filter(Category.name.in_(OLD_CATEGORIES)).delete(
        synchronize_session=False)
    db.session.commit()
    print(f'已置空 {cleared} 本书的分类，已删除 {deleted} 个旧分类')


# 避免循环导入，在函数内 import Book
from app.models import Book


def import_all_highlights(user_id=None):
    from app.weread.importer import import_highlights_for_book
    from app.models import User
    if user_id:
        books = Book.query.filter(Book.user_id == user_id,
                                  Book.weread_book_id.isnot(None),
                                  Book.weread_book_id != '').all()
    else:
        books = Book.query.filter(Book.weread_book_id.isnot(None),
                                  Book.weread_book_id != '').all()
    total = len(books)
    imported_total = 0
    errors = 0
    for i, book in enumerate(books, 1):
        uid = book.user_id
        print(f'[{i}/{total}] {book.title}...', end=' ')
        try:
            result = import_highlights_for_book(book, uid)
            imported_total += result['imported']
            print(f"{result['imported']}/{result['total']} 条")
        except Exception as e:
            errors += 1
            print(f'失败: {e}')
    print(f'\n完成：共导入 {imported_total} 条划线，{errors} 本失败')
