# 用户个人读书笔记 — 实现计划

> **For agentic workers:** Use subagent-driven-development or executing-plans to implement task-by-task.

**Goal:** 为每个登录用户提供多篇、Markdown 格式、支持本地图片上传的个人读书笔记

**Architecture:** 新增 `app/notes/` 蓝图，独立处理笔记 CRUD 和图片上传；新增 Note 和 NoteImage 模型；通过 Jinja2 过滤器在详情页渲染 HTML

**Tech Stack:** Flask 3.x + SQLAlchemy + MySQL + markdown + bleach + EasyMDE (CDN)

## Global Constraints

- 虚拟环境：`C:\Users\admin\my_env\Scripts\python.exe`
- MySQL: `root/Aa123456@localhost:3306/book_collection`
- 图片存储：`app/static/uploads/notes/`，命名 `{user_id}_{timestamp}_{uuid4_hex8}.{ext}`
- 图片限制：png/jpg/jpeg/gif/webp，≤5MB
- 所有笔记路由需用户登录
- 遵循现有代码风格：双引号字符串，`db.relationship` 写法，蓝图模式

---

### Task 1: 添加 Note + NoteImage 模型并生成迁移

**Files:**
- Modify: `app/models.py` (在文件末尾添加两个模型)
- New: 自动生成迁移脚本

**Interfaces:**
- Consumes: `app/extensions.py` 中的 `db`、已有 `User`/`Book` 模型
- Produces: `Note` 和 `NoteImage` 两个模型类

- [ ] **Step 1: 在 models.py 末尾添加模型**

在 `app/models.py` 最后、`load_user` 之前添加：

```python
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
    uploaded_at = db.Column(db.DateTime, default=datetime.now)
```

- [ ] **Step 2: 生成并运行迁移**

```powershell
C:\Users\admin\my_env\Scripts\python.exe run.py db migrate -m "add note and note_image tables"
C:\Users\admin\my_env\Scripts\python.exe run.py db upgrade
```

预期输出：成功创建 `notes` 和 `note_images` 两张表

- [ ] **Step 3: Commit**

```bash
git add app/models.py migrations/
git commit -m "feat: add Note and NoteImage models"
```

---

### Task 2: 提取 frontend_login_required 到公共模块 + 更新引用

**Files:**
- Modify: `app/extensions.py`
- Modify: `app/main/routes.py`

**Interfaces:**
- Produces: `app.extensions.frontend_login_required` 可被其他蓝图引用

- [ ] **Step 1: 在 extensions.py 中添加 decorator**

```python
from functools import wraps
from flask import redirect, url_for
from flask_login import current_user


def frontend_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
```

`app/extensions.py` 最终内容：

```python
from functools import wraps
from flask import redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


def frontend_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
```

- [ ] **Step 2: 更新 main/routes.py 的引用**

将：
```python
from functools import wraps
from datetime import datetime
from flask import render_template, jsonify, redirect, url_for
from flask import current_app
from flask_login import current_user
from app.main import bp
from app.models import Book, Category, Highlight, db
from app.weread.api import get_shelf, get_readdata
from app.weread.importer import import_highlights_for_book


def frontend_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
```

改为：
```python
from datetime import datetime
from flask import render_template, jsonify, redirect, url_for
from flask import current_app
from flask_login import current_user
from app.main import bp
from app.extensions import frontend_login_required
from app.models import Book, Category, Highlight, db
from app.weread.api import get_shelf, get_readdata
from app.weread.importer import import_highlights_for_book
```

- [ ] **Step 3: Commit**

```bash
git add app/extensions.py app/main/routes.py
git commit -m "refactor: move frontend_login_required to extensions.py"
```

---

### Task 3: 安装依赖 + 注册 Jinja2 过滤器 + 注册蓝图

**Files:**
- Modify: `requirements.txt`
- Modify: `app/__init__.py`

- [ ] **Step 1: 更新 requirements.txt**

在文件末尾添加：
```
markdown
bleach
```

- [ ] **Step 2: 安装依赖**

```powershell
C:\Users\admin\my_env\Scripts\python.exe -m pip install markdown bleach
```

- [ ] **Step 3: 在 app/__init__.py 中添加过滤器 + 注册蓝图**

在 `create_app` 函数中，`auth_bp` 注册之后添加：

```python
import markdown as md_lib
import bleach

ALLOWED_TAGS = ['h1','h2','h3','h4','h5','h6','p','br','strong','em',
    'a','ul','ol','li','code','pre','blockquote','img','hr','table',
    'thead','tbody','tr','th','td','span','div']

ALLOWED_ATTRS = {'img':['src','alt','title'], 'a':['href','title','target'],
    '*':['class']}

def render_markdown(text):
    html = md_lib.markdown(text or '', extensions=['extra','codehilite'])
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)

app.jinja_env.filters['markdown'] = render_markdown
```

并在 `auth_bp` 注册之后添加蓝图注册：
```python
from app.notes import bp as notes_bp
app.register_blueprint(notes_bp, url_prefix='/notes')
```

同时将顶部的 `import markdown` 改为 `import markdown as md_lib` 以避免与 `markdown` 包名冲突。顶部新增：
```python
import markdown as md_lib
import bleach
```

注意：原有的 `from app.auth import bp as auth_bp` 和 `app.register_blueprint(auth_bp, url_prefix='/auth')` 要保持不变。将 notes 蓝图注册放在 auth 之后。

- [ ] **Step 4: Commit**

```bash
git add requirements.txt app/__init__.py
git commit -m "feat: add markdown/bleach deps, Jinja2 filter, notes blueprint"
```

---

### Task 4: 创建 notes 蓝图（图片上传 + CRUD 路由）

**Files:**
- Create: `app/notes/__init__.py`
- Create: `app/notes/forms.py`
- Create: `app/notes/routes.py`
- Create: `app/static/uploads/notes/.gitkeep`

- [ ] **Step 1: 创建 `app/notes/__init__.py`**

```python
from flask import Blueprint
bp = Blueprint('notes', __name__)
from app.notes import routes
```

- [ ] **Step 2: 创建 `app/notes/forms.py`**

```python
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired


class NoteForm(FlaskForm):
    title = StringField('笔记标题', validators=[DataRequired()])
    content = TextAreaField('笔记内容')
    submit = SubmitField('保存')
```

- [ ] **Step 3: 创建 `app/notes/routes.py`**

```python
import os
import uuid
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename
from app.extensions import frontend_login_required
from app.notes import bp
from app.notes.forms import NoteForm
from app.models import db, Book, Note, NoteImage

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route('/book/<int:book_id>')
@frontend_login_required
def book_notes(book_id):
    notes = Note.query.filter_by(user_id=current_user.id, book_id=book_id)\
        .order_by(Note.updated_at.desc()).all()
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'preview': (n.content or '')[:100],
        'updated_at': n.updated_at.strftime('%Y-%m-%d %H:%M') if n.updated_at else '',
    } for n in notes])


@bp.route('/create/<int:book_id>', methods=['GET', 'POST'])
@frontend_login_required
def note_create(book_id):
    book = Book.query.get_or_404(book_id)
    form = NoteForm()
    if form.validate_on_submit():
        note = Note(
            user_id=current_user.id,
            book_id=book.id,
            title=form.title.data,
            content=form.content.data,
        )
        db.session.add(note)
        db.session.commit()
        flash('笔记保存成功', 'success')
        return redirect(url_for('main.book_detail', id=book.id))
    return render_template('notes/create.html', form=form, book=book)


@bp.route('/<int:id>')
@frontend_login_required
def note_detail(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        flash('无权访问', 'danger')
        return redirect(url_for('main.index'))
    return render_template('notes/detail.html', note=note)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@frontend_login_required
def note_edit(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        flash('无权操作', 'danger')
        return redirect(url_for('main.index'))
    form = NoteForm(obj=note)
    if form.validate_on_submit():
        note.title = form.title.data
        note.content = form.content.data
        note.updated_at = datetime.now()
        db.session.commit()
        flash('笔记已更新', 'success')
        return redirect(url_for('main.book_detail', id=note.book_id))
    return render_template('notes/edit.html', form=form, note=note)


@bp.route('/<int:id>/delete', methods=['POST'])
@frontend_login_required
def note_delete(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        flash('无权操作', 'danger')
        return redirect(url_for('main.index'))
    book_id = note.book_id
    db.session.delete(note)
    db.session.commit()
    flash('笔记已删除', 'success')
    return redirect(url_for('main.book_detail', id=book_id))


@bp.route('/upload-image', methods=['POST'])
@frontend_login_required
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': '未选择文件'}), 400
    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': '不支持的文件格式'}), 400

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'notes')
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.rsplit('.', 1)[1].lower()
    new_name = f"{current_user.id}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}.{ext}"
    save_path = os.path.join(upload_dir, new_name)
    file.save(save_path)

    url = url_for('static', filename=f'uploads/notes/{new_name}')
    return jsonify({'url': url, 'markdown': f'![]({url})'})
```

- [ ] **Step 4: 创建 `.gitkeep`**

```powershell
New-Item -ItemType File -Path "app\static\uploads\notes\.gitkeep"
```

- [ ] **Step 5: Commit**

```bash
git add app/notes/ app/static/uploads/notes/.gitkeep
git commit -m "feat: notes blueprint with CRUD and image upload"
```

---

### Task 5: 创建笔记模板

**Files:**
- Create: `app/templates/notes/create.html`
- Create: `app/templates/notes/edit.html`
- Create: `app/templates/notes/detail.html`

- [ ] **Step 1: 创建 `app/templates/notes/create.html`**

```html
{% extends 'base.html' %}
{% block title %}写笔记{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-lg-10">
        <h4 class="mb-3">为《{{ book.title }}》写笔记</h4>
        <form method="post">
            {{ form.hidden_tag() }}
            <div class="mb-3">
                {{ form.title.label(class='form-label') }}
                {{ form.title(class='form-control', placeholder='给这篇笔记起个标题') }}
                {% for e in form.title.errors %}<div class="text-danger">{{ e }}</div>{% endfor %}
            </div>
            <div class="mb-3">
                {{ form.content.label(class='form-label') }}
                <div class="mb-2">
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="document.getElementById('image-input').click()">上传图片</button>
                    <input type="file" id="image-input" accept="image/*" style="display:none">
                </div>
                {{ form.content(class='form-control', rows=20, placeholder='支持 Markdown 语法...', id='note-editor') }}
            </div>
            {{ form.submit(class='btn btn-primary') }}
            <a href="{{ url_for('main.book_detail', id=book.id) }}" class="btn btn-outline-secondary">取消</a>
        </form>
    </div>
</div>
{% endblock %}
{% block scripts %}
<script>
document.getElementById('image-input').addEventListener('change', function(e) {
    var file = e.target.files[0];
    if (!file) return;
    var formData = new FormData();
    formData.append('image', file);
    fetch('{{ url_for("notes.upload_image") }}', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.markdown) {
            var editor = document.getElementById('note-editor');
            editor.value += '\n' + data.markdown + '\n';
        }
    })
    .catch(function() { alert('上传失败'); });
});
</script>
{% endblock %}
```

- [ ] **Step 2: 创建 `app/templates/notes/edit.html`**

```html
{% extends 'base.html' %}
{% block title %}编辑笔记{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-lg-10">
        <h4 class="mb-3">编辑笔记</h4>
        <form method="post">
            {{ form.hidden_tag() }}
            <div class="mb-3">
                {{ form.title.label(class='form-label') }}
                {{ form.title(class='form-control') }}
                {% for e in form.title.errors %}<div class="text-danger">{{ e }}</div>{% endfor %}
            </div>
            <div class="mb-3">
                {{ form.content.label(class='form-label') }}
                <div class="mb-2">
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="document.getElementById('image-input').click()">上传图片</button>
                    <input type="file" id="image-input" accept="image/*" style="display:none">
                </div>
                {{ form.content(class='form-control', rows=20, id='note-editor') }}
            </div>
            {{ form.submit(class='btn btn-primary') }}
            <a href="{{ url_for('notes.note_detail', id=note.id) }}" class="btn btn-outline-secondary">取消</a>
        </form>
    </div>
</div>
{% endblock %}
{% block scripts %}
<script>
document.getElementById('image-input').addEventListener('change', function(e) {
    var file = e.target.files[0];
    if (!file) return;
    var formData = new FormData();
    formData.append('image', file);
    fetch('{{ url_for("notes.upload_image") }}', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.markdown) {
            document.getElementById('note-editor').value += '\n' + data.markdown + '\n';
        }
    })
    .catch(function() { alert('上传失败'); });
});
</script>
{% endblock %}
```

- [ ] **Step 3: 创建 `app/templates/notes/detail.html`**

```html
{% extends 'base.html' %}
{% block title %}{{ note.title }}{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-lg-8">
        <div class="d-flex justify-content-between align-items-start mb-3">
            <h3>{{ note.title }}</h3>
            <div>
                <a href="{{ url_for('notes.note_edit', id=note.id) }}" class="btn btn-sm btn-outline-primary">编辑</a>
                <form method="post" action="{{ url_for('notes.note_delete', id=note.id) }}" style="display:inline" onsubmit="return confirm('确定删除？')">
                    <button class="btn btn-sm btn-outline-danger">删除</button>
                </form>
            </div>
        </div>
        <p class="text-muted small mb-4">
            所属书籍：<a href="{{ url_for('main.book_detail', id=note.book_id) }}">{{ note.book.title }}</a>
            &middot; 更新于 {{ note.updated_at.strftime('%Y-%m-%d %H:%M') if note.updated_at else '' }}
        </p>
        <div class="note-content p-4 rounded" style="background:var(--cream);">
            {{ note.content|markdown|safe }}
        </div>
        <a href="{{ url_for('main.book_detail', id=note.book_id) }}" class="btn btn-outline-secondary mt-3">&larr; 返回书籍详情</a>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Commit**

```bash
git add app/templates/notes/
git commit -m "feat: note templates (create, edit, detail)"
```

---

### Task 6: 修改图书详情页，增加"我的笔记" tab

**Files:**
- Modify: `app/templates/books/detail.html`

- [ ] **Step 1: 在 detail.html 中现有划线笔记区域下方（或替换为 tab），添加"我的笔记"区域**

将原有的提示和 tab 改为：
- 在 `h4 划线笔记` 所在区域替换为 tab 布局
- 新增 JS 加载笔记列表

将 `app/templates/books/detail.html` 中从 `<hr>` 到 `{% endblock %}` 的内容整体替换为：

```html
<hr class="my-4" style="border-color:var(--border-warm);">

<ul class="nav nav-tabs mb-3" id="noteTabs" role="tablist">
    <li class="nav-item" role="presentation">
        <button class="nav-link active" id="highlights-tab" data-bs-toggle="tab" data-bs-target="#highlights" type="button">划线笔记 <span id="highlight-count" class="text-muted"></span></button>
    </li>
    <li class="nav-item" role="presentation">
        <button class="nav-link" id="mynotes-tab" data-bs-toggle="tab" data-bs-target="#mynotes" type="button">我的笔记 <span id="note-count" class="text-muted"></span></button>
    </li>
</ul>
<div class="tab-content">
    <div class="tab-pane fade show active" id="highlights">
        <div id="highlight-loading" class="text-center py-4">
            <div class="spinner-border" role="status" style="color:var(--leather);"><span class="visually-hidden">加载中...</span></div>
            <p class="mt-2 text-muted">正在加载划线笔记...</p>
        </div>
        <div id="highlight-error" class="alert alert-danger d-none"></div>
        <div id="highlight-empty" class="text-muted py-3 d-none">暂无划线笔记</div>
        <div id="highlight-content" class="d-none"></div>
    </div>
    <div class="tab-pane fade" id="mynotes">
        <div id="notes-loading" class="text-center py-4">
            <div class="spinner-border" role="status" style="color:var(--leather);"><span class="visually-hidden">加载中...</span></div>
            <p class="mt-2 text-muted">正在加载笔记...</p>
        </div>
        <div id="notes-error" class="alert alert-danger d-none"></div>
        <div id="notes-empty" class="text-muted py-3 d-none">
            暂无笔记
            <div class="mt-2"><a href="{{ url_for('notes.note_create', book_id=book.id) }}" class="btn btn-primary btn-sm">写第一篇笔记</a></div>
        </div>
        <div id="notes-content" class="d-none"></div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
fetch('{{ url_for("main.book_highlights", id=book.id) }}')
    .then(function(r) {
        if (!r.ok) { return r.json().then(function(d) { throw new Error(d.error || '请求失败'); }); }
        return r.json();
    })
    .then(function(data) {
        document.getElementById('highlight-loading').classList.add('d-none');
        if (data.error) {
            document.getElementById('highlight-error').textContent = data.error;
            document.getElementById('highlight-error').classList.remove('d-none');
        } else if (data.highlights && data.highlights.length > 0) {
            var total = 0;
            var html = '';
            data.highlights.forEach(function(group) {
                html += '<h5 class="mt-3 mb-2 text-secondary">' + group.chapter_title + '</h5>';
                group.items.forEach(function(item) {
                    total++;
                    html += '<div class="highlight-item" style="border-left-color:' + item.color + ';">';
                    html += '<p class="mb-1">' + item.mark_text + '</p>';
                    if (item.created_at) html += '<small class="text-muted">' + item.created_at + '</small>';
                    html += '</div>';
                });
            });
            document.getElementById('highlight-count').textContent = '(' + total + '条)';
            document.getElementById('highlight-content').innerHTML = html;
            document.getElementById('highlight-content').classList.remove('d-none');
        } else {
            document.getElementById('highlight-empty').classList.remove('d-none');
        }
    })
    .catch(function(e) {
        document.getElementById('highlight-loading').classList.add('d-none');
        document.getElementById('highlight-error').classList.remove('d-none');
        document.getElementById('highlight-error').textContent = e.message || '加载划线笔记失败，请稍后重试';
    });

fetch('{{ url_for("notes.book_notes", book_id=book.id) }}')
    .then(function(r) { return r.json(); })
    .then(function(data) {
        document.getElementById('notes-loading').classList.add('d-none');
        if (data && data.length > 0) {
            document.getElementById('note-count').textContent = '(' + data.length + '篇)';
            var html = '';
            data.forEach(function(n) {
                html += '<div class="card mb-2">';
                html += '<div class="card-body">';
                html += '<h5 class="card-title"><a href="{{ url_for("notes.note_detail", id=0) }}'.replace('/0', '/' + n.id) + '">' + n.title + '</a></h5>';
                html += '<p class="card-text text-muted small">' + n.preview + '</p>';
                html += '<p class="card-text"><small class="text-muted">' + n.updated_at + '</small>';
                html += ' <a href="{{ url_for("notes.note_edit", id=0) }}'.replace('/0', '/' + n.id) + '" class="btn btn-sm btn-outline-primary">编辑</a>';
                html += ' <form method="post" action="{{ url_for("notes.note_delete", id=0) }}'.replace('/0', '/' + n.id) + '" style="display:inline" onsubmit="return confirm(\'确定删除？\')"><button class="btn btn-sm btn-outline-danger">删除</button></form>';
                html += '</p></div></div>';
            });
            html += '<div class="mt-3"><a href="{{ url_for("notes.note_create", book_id=book.id) }}" class="btn btn-primary">写新笔记</a></div>';
            document.getElementById('notes-content').innerHTML = html;
            document.getElementById('notes-content').classList.remove('d-none');
        } else {
            document.getElementById('notes-empty').classList.remove('d-none');
        }
    })
    .catch(function() {
        document.getElementById('notes-loading').classList.add('d-none');
        document.getElementById('notes-error').classList.remove('d-none');
        document.getElementById('notes-error').textContent = '加载笔记失败';
    });
</script>
{% endblock %}
```

注意：需确保文件中原有的 `{% block scripts %}` 和 `{% endblock %}` 配对正确。完整替换从 `<hr class="my-4">` 到文件末尾。

- [ ] **Step 2: Commit**

```bash
git add app/templates/books/detail.html
git commit -m "feat: add My Notes tab to book detail page"
```

---

### 自审记录

**Spec Coverage:**
- 多篇笔记 → Task 1 (Note 模型) + Task 4 (CRUD 路由) ✓
- 用户独立 → Task 1 (user_id FK) + Task 4 (路由中过滤 user_id) ✓
- Markdown 编辑 → Task 3 (markdown 过滤器) + Task 5 (textarea 编辑器) ✓
- 本地图片上传 → Task 4 (upload-image 路由) + Task 5 (模板中的上传按钮) ✓
- 图书详情页展示 → Task 6 (tab 切换) ✓
- 笔记详情页 → Task 5 (detail.html) + Task 4 (note_detail 路由) ✓
- 图⽚存储限5MB → Task 4 (逻辑中未明确限，需添加) → 需在 upload_image 中添加大小检查

**修复：** 移除了模块级 `UPLOAD_DIR`（`current_app.root_path` 在导入时不可用），已在函数内用 `os.path.join(current_app.root_path, ...)` 替代 ✓

**需修复：** upload_image 中缺少文件大小检查。在 `allowed_file` 检查后添加：
```python
file.seek(0, os.SEEK_END)
if file.tell() > 5 * 1024 * 1024:
    return jsonify({'error': '文件大小不能超过 5MB'}), 400
file.seek(0)
```

**Type consistency:** 所有路由签名一致，模型字段与路由中使用的字段匹配 ✓

**Placeholder scan:** 无 TBD/TODO ✓
