from datetime import datetime, date
from sqlalchemy import UniqueConstraint
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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    author = db.Column(db.String(100))
    isbn = db.Column(db.String(20))
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
    owner = db.relationship('User', backref=db.backref('books', lazy='dynamic'))
    highlights = db.relationship('Highlight', backref='book', lazy='dynamic',
                                 order_by='Highlight.chapter_uid, Highlight.created_at')

    def __repr__(self):
        return f'<Book {self.title}>'


class Highlight(db.Model):
    __tablename__ = 'highlights'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
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
    weread_api_key = db.Column(db.String(200), default='', nullable=True)
    shelf_synced = db.Column(db.Boolean, default=False)

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


class Note(db.Model):
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    author = db.relationship('User', backref=db.backref('notes', lazy='dynamic'))
    book = db.relationship('Book', backref=db.backref('user_notes', lazy='dynamic',
                                                      order_by='Note.updated_at.desc()'))


class NoteImage(db.Model):
    __tablename__ = 'note_images'

    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('notes.id'), nullable=True)
    filename = db.Column(db.String(200), nullable=False)
    stored_path = db.Column(db.String(300), nullable=False)
    display_width = db.Column(db.Integer, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.now)

    note_ref = db.relationship('Note', backref=db.backref('images', lazy='dynamic',
                                order_by='NoteImage.uploaded_at'))


class ReadStat(db.Model):
    __tablename__ = "read_stat"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    total_read_time = db.Column(db.Integer, default=0)
    read_days = db.Column(db.Integer, default=0)
    day_avg_read_time = db.Column(db.Integer, default=0)
    compare = db.Column(db.Float, nullable=True)
    read_longest = db.Column(db.JSON, nullable=True)
    read_stat = db.Column(db.JSON, nullable=True)
    prefer_category = db.Column(db.JSON, nullable=True)
    prefer_time_word = db.Column(db.String(100), nullable=True)
    prefer_author = db.Column(db.JSON, nullable=True)
    prefer_time = db.Column(db.JSON, nullable=True)
    read_rate = db.Column(db.Float, nullable=True)
    wr_read_time = db.Column(db.Integer, nullable=True)
    wr_listen_time = db.Column(db.Integer, nullable=True)
    raw_data = db.Column(db.JSON, nullable=True)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "mode", "period_start"),)
    user = db.relationship("User", backref=db.backref("read_stats", lazy="dynamic"))


class DailyReadStat(db.Model):
    __tablename__ = "daily_read_stat"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    total_read_time = db.Column(db.Integer, default=0)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "date"),)
    user = db.relationship("User", backref=db.backref("daily_read_stats", lazy="dynamic"))


class ReadGoal(db.Model):
    __tablename__ = "read_goal"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=True)
    target_read_time = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "year", "month"),)
    user = db.relationship("User", backref=db.backref("read_goals", lazy="dynamic"))


class Thinker(db.Model):
    __tablename__ = "thinker"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(100))
    avatar_url = db.Column(db.String(500), default='')
    era = db.Column(db.String(50))
    school = db.Column(db.String(100))
    bio = db.Column(db.Text)
    system_prompt = db.Column(db.Text, nullable=False)
    opening_line = db.Column(db.Text, nullable=True)
    theme = db.Column(db.String(50), default='')
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    conversations = db.relationship("Conversation", backref="thinker", lazy="dynamic",
                                    cascade="all, delete-orphan")


class Conversation(db.Model):
    __tablename__ = "conversation"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    thinker_id = db.Column(db.Integer, db.ForeignKey("thinker.id"), nullable=False)
    title = db.Column(db.String(200), default="新对话")
    messages = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("conversations", lazy="dynamic"))


@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith('u_'):
        return User.query.get(int(user_id[2:]))
    return Admin.query.get(int(user_id))


class BookChat(db.Model):
    __tablename__ = 'book_chat'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    title = db.Column(db.String(200), default='关于本书的对话')
    messages = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('book_chats', lazy='dynamic'))
    book = db.relationship('Book', backref=db.backref('book_chats', lazy='dynamic'))


class BookAIContent(db.Model):
    __tablename__ = 'book_ai_content'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    content_type = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    source_info = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('user_id', 'book_id', 'content_type'),)
    user = db.relationship('User', backref=db.backref('ai_contents', lazy='dynamic'))
    book = db.relationship('Book', backref=db.backref('ai_contents', lazy='dynamic'))
