from app.extensions import db
from app.models import Admin, Category


def init_db():
    if not Admin.query.first():
        admin = Admin(username='admin')
        admin.set_password('admin123')
        db.session.add(admin)

    for name in ['文学', '科幻', '历史', '技术', '哲学', '艺术', '传记', '心理']:
        if not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name))

    db.session.commit()
    print('初始化完成：admin / admin123，8个默认分类')
