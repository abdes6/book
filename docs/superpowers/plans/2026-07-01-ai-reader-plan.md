# AI 读书助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在个人藏书管理系统中增加 AI 读书助手功能，支持按书对话、摘要、书评、划线分析和推荐

**Architecture:** 新建 `ai_reader` 蓝图，独立于现有 Thinker 模块；复用 Thinker 的 DeepSeek API 客户端；`BookChat` 存对话记录，`BookAIContent` 缓存摘要/书评/分析结果

**Tech Stack:** Flask, SQLAlchemy, DeepSeek/OpenAI SDK, Bootstrap 5, Jinja2

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `app/models.py` | 追加 `BookChat`, `BookAIContent` 模型 |
| 新建 | `app/ai_reader/__init__.py` | 蓝图定义 |
| 新建 | `app/ai_reader/service.py` | AI system prompt 模板 + DeepSeek 调用 |
| 新建 | `app/ai_reader/routes.py` | 8 个路由处理器 |
| 新建 | `app/templates/ai_reader/index.html` | 左侧选书 + 右侧 5 Tab |
| 修改 | `app/__init__.py` | 注册 ai_reader 蓝图 |
| 修改 | `app/templates/base.html` | 导航栏添加入口 |

---

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

### Task 2: AI 服务层

**Files:**
- Create: `app/ai_reader/service.py`

**Produces:** `chat_with_book()`, `generate_summary()`, `generate_review()`, `generate_analysis()`, `generate_recommendations()` 函数

- [ ] **Step 1: 创建 `app/ai_reader/service.py`**

```python
from flask import current_app
from openai import OpenAI


def _client():
    return OpenAI(
        api_key=current_app.config['DEEPSEEK_API_KEY'],
        base_url=current_app.config['DEEPSEEK_BASE_URL']
    )


PROMPTS = {
    'chat': '你是一位专业的读书助手。我正在阅读《{title}》(作者: {author})。\n'
            '请根据这本书的内容回答我的问题，给出有深度的见解。\n'
            '如果问题书中没有直接涉及，请基于核心思想合理延伸。\n\n'
            '书籍简介：{summary}\n\n相关划线笔记：\n{highlights}',
    'summary': '请为《{title}》(作者: {author})写一份300-500字的书籍摘要。\n'
               '包括：核心主题、主要观点、适合什么人阅读。\n\n'
               '书籍简介：{summary}\n\n划线笔记参考：\n{highlights}',
    'review': '请为《{title}》(作者: {author})写一篇200-400字的书评。\n'
              '包括：整体评价、亮点分析、不足之处、推荐理由。\n\n'
              '书籍简介：{summary}\n\n划线笔记参考：\n{highlights}',
    'analysis': '以下是《{title}》中的划线笔记，请分析：\n'
                '1. 核心观点提炼（3-5个）\n2. 金句精选\n3. 观点之间的逻辑关系\n\n'
                '划线笔记：\n{highlights}',
    'recommend': '我正在阅读《{title}》(作者: {author})，请推荐5本类似的书籍。\n'
                 '每本推荐包括：书名、作者、推荐理由、与当前书的关联。\n\n'
                 '我读过的其他书：\n{read_history}',
}

TEMPS = {'chat': 0.7, 'summary': 0.3, 'review': 0.5, 'analysis': 0.4, 'recommend': 0.6}
MAX_TOKENS = {'chat': 2048, 'summary': 1024, 'review': 1536, 'analysis': 2048, 'recommend': 1024}


def _call_ai(prompt, temp=0.7, max_tokens=2048):
    resp = _client().chat.completions.create(
        model=current_app.config['DEEPSEEK_MODEL'],
        messages=[{'role': 'user', 'content': prompt}],
        temperature=temp, max_tokens=max_tokens
    )
    return resp.choices[0].message.content


def _build_context(book, highlights_text=''):
    return {
        'title': book.title or '',
        'author': book.author or '未知',
        'summary': book.summary or '暂无简介',
        'highlights': highlights_text,
    }


def chat_with_book(book, highlights_text, message, history):
    ctx = _build_context(book, highlights_text)
    prompt = PROMPTS['chat'].format(**ctx)
    messages = [{'role': 'system', 'content': prompt}]
    for h in history:
        messages.append(h)
    messages.append({'role': 'user', 'content': message})
    resp = _client().chat.completions.create(
        model=current_app.config['DEEPSEEK_MODEL'],
        messages=messages, temperature=TEMPS['chat'], max_tokens=MAX_TOKENS['chat']
    )
    return resp.choices[0].message.content


def generate_summary(book, highlights_text):
    ctx = _build_context(book, highlights_text)
    return _call_ai(PROMPTS['summary'].format(**ctx), TEMPS['summary'], MAX_TOKENS['summary'])


def generate_review(book, highlights_text):
    ctx = _build_context(book, highlights_text)
    return _call_ai(PROMPTS['review'].format(**ctx), TEMPS['review'], MAX_TOKENS['review'])


def generate_analysis(book, highlights_text):
    ctx = _build_context(book, highlights_text)
    return _call_ai(PROMPTS['analysis'].format(**ctx), TEMPS['analysis'], MAX_TOKENS['analysis'])


def generate_recommendations(book, read_history_text):
    ctx = {'title': book.title or '', 'author': book.author or '未知', 'read_history': read_history_text}
    text = _call_ai(PROMPTS['recommend'].format(**ctx), TEMPS['recommend'], MAX_TOKENS['recommend'])
    recommendations = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('**'):
            recommendations.append(line)
    return recommendations
```

---

### Task 3: 路由

**Files:**
- Create: `app/ai_reader/routes.py`

**Produces:** 所有 API 端点

- [ ] **Step 1: 创建 `app/ai_reader/routes.py`**

```python
from flask import render_template, jsonify, request, current_app
from flask_login import current_user
from app.ai_reader import bp
from app.ai_reader.service import chat_with_book, generate_summary, generate_review, generate_analysis, generate_recommendations
from app.extensions import db, frontend_login_required, csrf
from app.models import Book, BookChat, BookAIContent, Highlight


@bp.route('/')
@frontend_login_required
def index():
    return render_template('ai_reader/index.html')


@bp.route('/books')
@frontend_login_required
def book_list():
    user_id = int(current_user.get_id().replace('u_', ''))
    books = Book.query.filter_by(user_id=user_id).order_by(Book.updated_at.desc()).all()
    return jsonify([{
        'id': b.id, 'title': b.title, 'author': b.author or '',
        'cover_url': b.cover_url or '', 'status': b.status or 'reading',
    } for b in books])


@bp.route('/<int:book_id>/chat', methods=['GET'])
@frontend_login_required
def get_chat(book_id):
    user_id = int(current_user.get_id().replace('u_', ''))
    chat = BookChat.query.filter_by(user_id=user_id, book_id=book_id).first()
    return jsonify({'messages': chat.messages if chat else []})


@csrf.exempt
@bp.route('/<int:book_id>/chat', methods=['POST'])
@frontend_login_required
def send_message(book_id):
    user_id = int(current_user.get_id().replace('u_', ''))
    book = Book.query.filter_by(id=book_id, user_id=user_id).first_or_404()
    data = request.get_json()
    message = (data.get('message', '') or '').strip()
    if not message:
        return jsonify({'error': '消息不能为空'}), 400

    chat = BookChat.query.filter_by(user_id=user_id, book_id=book_id).first()
    if not chat:
        chat = BookChat(user_id=user_id, book_id=book_id, messages=[])
        db.session.add(chat)
        db.session.commit()
    history = list(chat.messages) if chat.messages else []
    highlights_text = '\n'.join(
        h.mark_text for h in Highlight.query.filter_by(book_id=book_id, user_id=user_id)
        .order_by(Highlight.created_at.desc()).limit(20).all()
    )
    try:
        reply = chat_with_book(book, highlights_text, message, history)
    except Exception as e:
        current_app.logger.error(f'AI chat error: {e}')
        return jsonify({'error': 'AI 服务暂时不可用'}), 500

    history.append({'role': 'user', 'content': message})
    history.append({'role': 'assistant', 'content': reply})
    if not chat.title or chat.title == '关于本书的对话':
        chat.title = message[:50]
    chat.messages = history
    chat.updated_at = db.func.now()
    db.session.commit()
    return jsonify({'reply': reply, 'messages': history})


@bp.route('/<int:book_id>/summary')
@frontend_login_required
def get_summary(book_id):
    user_id = int(current_user.get_id().replace('u_', ''))
    book = Book.query.filter_by(id=book_id, user_id=user_id).first_or_404()
    cached = BookAIContent.query.filter_by(user_id=user_id, book_id=book_id, content_type='summary').first()
    if cached:
        return jsonify({'content': cached.content, 'cached': True})
    highlights_text = '\n'.join(
        h.mark_text for h in Highlight.query.filter_by(book_id=book_id, user_id=user_id)
        .order_by(Highlight.created_at.desc()).limit(30).all()
    )
    try:
        content = generate_summary(book, highlights_text)
    except Exception as e:
        current_app.logger.error(f'AI summary error: {e}')
        return jsonify({'error': '生成摘要失败'}), 500
    entry = BookAIContent(user_id=user_id, book_id=book_id, content_type='summary', content=content, source_info=f'{len(highlights_text.split(chr(10)))}条笔记')
    db.session.add(entry)
    db.session.commit()
    return jsonify({'content': content, 'cached': False})


@bp.route('/<int:book_id>/review')
@frontend_login_required
def get_review(book_id):
    user_id = int(current_user.get_id().replace('u_', ''))
    book = Book.query.filter_by(id=book_id, user_id=user_id).first_or_404()
    cached = BookAIContent.query.filter_by(user_id=user_id, book_id=book_id, content_type='review').first()
    if cached:
        return jsonify({'content': cached.content, 'cached': True})
    highlights_text = '\n'.join(
        h.mark_text for h in Highlight.query.filter_by(book_id=book_id, user_id=user_id)
        .order_by(Highlight.created_at.desc()).limit(30).all()
    )
    try:
        content = generate_review(book, highlights_text)
    except Exception as e:
        current_app.logger.error(f'AI review error: {e}')
        return jsonify({'error': '生成书评失败'}), 500
    entry = BookAIContent(user_id=user_id, book_id=book_id, content_type='review', content=content)
    db.session.add(entry)
    db.session.commit()
    return jsonify({'content': content, 'cached': False})


@bp.route('/<int:book_id>/analysis')
@frontend_login_required
def get_analysis(book_id):
    user_id = int(current_user.get_id().replace('u_', ''))
    book = Book.query.filter_by(id=book_id, user_id=user_id).first_or_404()
    cached = BookAIContent.query.filter_by(user_id=user_id, book_id=book_id, content_type='analysis').first()
    if cached:
        return jsonify({'content': cached.content, 'cached': True})
    highlights = Highlight.query.filter_by(book_id=book_id, user_id=user_id).order_by(Highlight.created_at).all()
    if not highlights:
        return jsonify({'error': '暂无划线笔记，无法分析'}), 400
    highlights_text = '\n'.join(h.mark_text for h in highlights)
    try:
        content = generate_analysis(book, highlights_text)
    except Exception as e:
        current_app.logger.error(f'AI analysis error: {e}')
        return jsonify({'error': '生成分析失败'}), 500
    entry = BookAIContent(user_id=user_id, book_id=book_id, content_type='analysis', content=content, source_info=f'{len(highlights)}条笔记')
    db.session.add(entry)
    db.session.commit()
    return jsonify({'content': content, 'cached': False})


@bp.route('/<int:book_id>/recommend')
@frontend_login_required
def get_recommendations(book_id):
    user_id = int(current_user.get_id().replace('u_', ''))
    book = Book.query.filter_by(id=book_id, user_id=user_id).first_or_404()
    other_books = Book.query.filter(Book.user_id == user_id, Book.id != book_id).order_by(Book.updated_at.desc()).limit(20).all()
    read_history = '\n'.join(f'《{b.title}》({b.author or "未知"})' for b in other_books)
    try:
        recs = generate_recommendations(book, read_history)
    except Exception as e:
        current_app.logger.error(f'AI recommend error: {e}')
        return jsonify({'error': '生成推荐失败'}), 500
    return jsonify({'recommendations': recs})
```

---

### Task 4: 前端模板

**Files:**
- Create: `app/templates/ai_reader/index.html`

**Produces:** 主页面

- [ ] **Step 1: 创建 `app/templates/ai_reader/index.html`**

```html
{% extends 'base.html' %}
{% block title %}AI 读书助手{% endblock %}
{% block content %}
<div class="row" style="height:calc(100vh - 120px);">
  <div class="col-3 border-end overflow-auto" style="background:var(--cream);">
    <h5 class="my-3">📚 选择书籍</h5>
    <input type="text" id="book-search" class="form-control mb-3" placeholder="搜索书名/作者...">
    <div id="book-list" class="list-group"></div>
  </div>
  <div class="col-9 d-flex flex-column">
    <div id="placeholder" class="text-center text-muted mt-5 flex-grow-1">
      <h4>请从左侧选择一本书</h4>
      <p>选中后即可使用 AI 对话、摘要、书评、分析、推荐功能</p>
    </div>
    <div id="ai-panel" class="d-none flex-grow-1 d-flex flex-column">
      <ul class="nav nav-tabs" id="aiTabs">
        <li class="nav-item"><button class="nav-link active" data-tab="chat">对话</button></li>
        <li class="nav-item"><button class="nav-link" data-tab="summary">摘要</button></li>
        <li class="nav-item"><button class="nav-link" data-tab="review">书评</button></li>
        <li class="nav-item"><button class="nav-link" data-tab="analysis">分析</button></li>
        <li class="nav-item"><button class="nav-link" data-tab="recommend">推荐</button></li>
      </ul>
      <div class="tab-content flex-grow-1 d-flex flex-column overflow-auto p-3" id="aiTabContent">
        <div class="tab-pane active d-flex flex-column flex-grow-1" id="tab-chat">
          <div id="chat-messages" class="flex-grow-1 overflow-auto mb-3"></div>
          <div class="input-group">
            <input type="text" id="chat-input" class="form-control" placeholder="输入你的问题...">
            <button class="btn btn-primary" id="chat-send">发送</button>
          </div>
        </div>
        <div class="tab-pane d-none" id="tab-summary"><div class="ai-content"></div></div>
        <div class="tab-pane d-none" id="tab-review"><div class="ai-content"></div></div>
        <div class="tab-pane d-none" id="tab-analysis"><div class="ai-content"></div></div>
        <div class="tab-pane d-none" id="tab-recommend"><div class="ai-content"></div></div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
{% block scripts %}
<script>
(function(){
  var currentBookId = null;

  fetch('{{ url_for("ai_reader.book_list") }}').then(function(r){ return r.json(); }).then(function(books){
    var el = document.getElementById('book-list');
    books.forEach(function(b){
      var a = document.createElement('a');
      a.className = 'list-group-item list-group-item-action';
      a.href = '#';
      a.dataset.id = b.id;
      a.innerHTML = '<strong>' + escapeHtml(b.title) + '</strong><br><small>' + escapeHtml(b.author) + '</small>';
      a.addEventListener('click', function(e){
        e.preventDefault();
        selectBook(b.id, b.title);
        document.querySelectorAll('#book-list .active').forEach(function(x){ x.classList.remove('active'); });
        a.classList.add('active');
      });
      el.appendChild(a);
    });
  });

  document.getElementById('book-search').addEventListener('input', function(){
    var q = this.value.toLowerCase();
    document.querySelectorAll('#book-list .list-group-item').forEach(function(item){
      item.style.display = item.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });

  document.querySelectorAll('#aiTabs .nav-link').forEach(function(tab){
    tab.addEventListener('click', function(){
      document.querySelectorAll('#aiTabs .nav-link').forEach(function(t){ t.classList.remove('active'); });
      tab.classList.add('active');
      document.querySelectorAll('.tab-pane').forEach(function(p){ p.classList.add('d-none'); });
      var target = document.getElementById('tab-' + tab.dataset.tab);
      target.classList.remove('d-none');
      if(currentBookId) loadTabContent(tab.dataset.tab, currentBookId, target);
    });
  });

  document.getElementById('chat-send').addEventListener('click', sendChat);
  document.getElementById('chat-input').addEventListener('keydown', function(e){
    if(e.key === 'Enter') sendChat();
  });

  function selectBook(id, title){
    currentBookId = id;
    document.getElementById('placeholder').classList.add('d-none');
    var panel = document.getElementById('ai-panel');
    panel.classList.remove('d-none');
    document.getElementById('chat-messages').innerHTML = '';
    document.getElementById('chat-input').value = '';
    document.querySelectorAll('.ai-content').forEach(function(el){ el.innerHTML = ''; });
    document.getElementById('tab-chat').classList.remove('d-none');
    document.querySelectorAll('.tab-pane').forEach(function(p){
      if(p.id !== 'tab-chat') p.classList.add('d-none');
    });
    document.querySelectorAll('#aiTabs .nav-link').forEach(function(t){
      t.classList.toggle('active', t.dataset.tab === 'chat');
    });
    fetch('/ai-reader/' + id + '/chat').then(function(r){ return r.json(); }).then(function(data){
      if(data.messages){
        var el = document.getElementById('chat-messages');
        data.messages.forEach(function(m){
          addChatBubble(m.role, m.content);
        });
      }
    });
  }

  function loadTabContent(tab, bookId, targetEl){
    if(targetEl.dataset.loaded) return;
    targetEl.innerHTML = '<div class="text-center py-5"><div class="spinner-border"></div><p class="mt-2 text-muted">正在生成...</p></div>';
    fetch('/ai-reader/' + bookId + '/' + tab).then(function(r){ return r.json(); }).then(function(data){
      targetEl.dataset.loaded = '1';
      if(data.error){
        targetEl.innerHTML = '<div class="alert alert-warning">' + escapeHtml(data.error) + '</div>';
      } else {
        var html = data.content ? '<div class="p-3 rounded" style="background:var(--cream);white-space:pre-wrap;">' + escapeHtml(data.content) + '</div>' : '';
        if(data.recommendations){
          html = data.recommendations.map(function(r){
            return '<div class="card mb-2"><div class="card-body">' + escapeHtml(r) + '</div></div>';
          }).join('');
        }
        html += '<div class="mt-2"><button class="btn btn-sm btn-outline-secondary" onclick="regenerate(this,\'' + tab + '\',' + bookId + ')">重新生成</button></div>';
        targetEl.innerHTML = html;
      }
    }).catch(function(){
      targetEl.innerHTML = '<div class="alert alert-danger">加载失败</div>';
    });
  }

  function regenerate(btn, tab, bookId){
    var target = btn.closest('.tab-pane');
    target.dataset.loaded = '';
    loadTabContent(tab, bookId, target);
  }

  function sendChat(){
    if(!currentBookId) return;
    var input = document.getElementById('chat-input');
    var msg = input.value.trim();
    if(!msg) return;
    input.value = '';
    addChatBubble('user', msg);
    var el = document.getElementById('chat-messages');
    var loading = document.createElement('div');
    loading.className = 'text-muted py-2';
    loading.textContent = 'AI 正在思考...';
    el.appendChild(loading);
    el.scrollTop = el.scrollHeight;
    fetch('/ai-reader/' + currentBookId + '/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg})
    }).then(function(r){ return r.json(); }).then(function(data){
      loading.remove();
      if(data.error){
        addChatBubble('assistant', '⚠️ ' + data.error);
      } else {
        addChatBubble('assistant', data.reply);
      }
    }).catch(function(){
      loading.remove();
      addChatBubble('assistant', '⚠️ 网络错误，请重试');
    });
  }

  function addChatBubble(role, text){
    var el = document.getElementById('chat-messages');
    var div = document.createElement('div');
    div.className = 'mb-2 p-2 rounded ' + (role === 'user' ? 'text-end' : '');
    div.style.background = role === 'user' ? 'var(--accent)' : 'var(--cream)';
    div.style.whiteSpace = 'pre-wrap';
    div.textContent = text;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
  }

  function escapeHtml(text){
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(text));
    return d.innerHTML;
  }
})();
</script>
{% endblock %}
```

---

### Task 5: 导航栏入口

**Files:**
- Modify: `app/templates/base.html`

- [ ] **Step 1: 在 `base.html` 的 navigation 中追加入口**

在 `<li class="nav-item"><a class="nav-link" href="{{ url_for('thinker.list_thinkers') }}">💬 思想家</a></li>` 后追加：
```html
<li class="nav-item"><a class="nav-link" href="{{ url_for('ai_reader.index') }}">🤖 AI 读书</a></li>
```

---

### Task 6: 数据库迁移

- [ ] **Step 1: 生成迁移脚本并升级**

```bash
cd D:\Course\Web开发技术\实训
C:\Users\admin\my_env\Scripts\python.exe -m flask db migrate -m "add book_chat and book_ai_content"
C:\Users\admin\my_env\Scripts\python.exe -m flask db upgrade
```
