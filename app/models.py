from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    books = db.relationship('Book', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


class Book(db.Model):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    author = db.Column(db.String(100))
    isbn = db.Column(db.String(20), unique=True)
    cover_url = db.Column(db.String(500))
    summary = db.Column(db.Text)
    rating = db.Column(db.Numeric(2, 1), default=0.0)
    status = db.Column(db.String(10), default='reading')
    notes = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    imported = db.Column(db.Boolean, default=False)
    weread_book_id = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    last_viewed_at = db.Column(db.DateTime, nullable=True)
    highlights = db.relationship('Highlight', backref='book', lazy='dynamic',
                                 order_by='Highlight.chapter_uid, Highlight.created_at')

    def __repr__(self):
        return f'<Book {self.title}>'


class Highlight(db.Model):
    __tablename__ = 'highlights'

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    weread_bookmark_id = db.Column(db.String(100), nullable=False)
    chapter_uid = db.Column(db.Integer, default=0)
    chapter_title = db.Column(db.String(200), default='')
    mark_text = db.Column(db.Text, nullable=False)
    range = db.Column(db.String(100))
    color_style = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime)
    imported_at = db.Column(db.DateTime, default=datetime.now)


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f'u_{self.id}'


class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith('u_'):
        return User.query.get(int(user_id[2:]))
    return Admin.query.get(int(user_id))
