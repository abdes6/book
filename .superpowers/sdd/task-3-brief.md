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

