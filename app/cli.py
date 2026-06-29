from app.extensions import db
from app.models import Admin, Category

WEREAD_CATEGORIES = [
    '文学', '精品小说', '历史', '哲学宗教', '心理', '社会文化',
    '经济理财', '科学技术', '计算机', '个人成长', '艺术',
    '生活百科', '人物传记', '政治军事', '教育学习', '医学健康',
    '漫画', '男生小说', '童书',
]

OLD_CATEGORIES = ['科幻', '技术', '哲学', '传记', '经济', '社会',
                  '政治', '科学', '生活', '教育', '悬疑推理']


def init_db():
    if not Admin.query.first():
        admin = Admin(username='admin')
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
