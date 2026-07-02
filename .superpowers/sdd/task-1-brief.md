### Task 1: 数据模型 + 蓝图注册

**Files:**
- Modify: `app/models.py` — 末尾追加两个模型
- Create: `app/ai_reader/__init__.py`
- Modify: `app/__init__.py` — 注册蓝图

**Produces:** `BookChat`, `BookAIContent` 模型，`ai_reader` 蓝图

- [ ] **Step 1: 在 `app/models.py` 末尾追加模型**

在文件末尾 `load_user` 函数之后追加 `BookChat` 和 `BookAIContent` 模型。

```python
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
```

- [ ] **Step 2: 创建 `app/ai_reader/__init__.py`**

```python
from flask import Blueprint
bp = Blueprint('ai_reader', __name__)
from app.ai_reader import routes
```

- [ ] **Step 3: 在 `app/__init__.py` 注册蓝图**

在 `thinker_bp` 注册之后追加：
```python
from app.ai_reader import bp as ai_reader_bp
app.register_blueprint(ai_reader_bp)
```

---

