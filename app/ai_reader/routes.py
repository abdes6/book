import markdown as md_lib
import bleach
from flask import render_template, jsonify, request, current_app
from flask_login import current_user
from app.ai_reader import bp
from app.ai_reader.service import chat_with_book, generate_summary, generate_review, generate_analysis, generate_recommendations, generate_opening
from app.ai_utils import generate_options
from app.extensions import db, frontend_login_required
from app.models import Book, BookChat, BookAIContent, Highlight
from app.weread.importer import sync_shelf_for_user

_MD_TAGS = ['h1','h2','h3','h4','h5','h6','p','br','strong','em',
    'a','ul','ol','li','code','pre','blockquote','img','hr','table',
    'thead','tbody','tr','th','td','span','div']
_MD_ATTRS = {'img':['src','alt','title'], 'a':['href','title','target'], '*':['class']}


def _md_to_html(text):
    if not text:
        return ''
    html = md_lib.markdown(text, extensions=['extra', 'codehilite'])
    return bleach.clean(html, tags=_MD_TAGS, attributes=_MD_ATTRS)


@bp.route('/')
@frontend_login_required
def index():
    return render_template('ai_reader/index.html')


@bp.route('/books')
@frontend_login_required
def book_list():
    try:
        sync_shelf_for_user(current_user.id)
    except Exception:
        current_app.logger.warning('书架同步失败，显示缓存数据', exc_info=True)
    books = Book.query.filter_by(
        user_id=current_user.id, shelved=True
    ).order_by(Book.created_at.desc()).all()
    return jsonify([{
        'id': b.id, 'title': b.title, 'author': b.author or '',
        'cover_url': b.cover_url or '', 'status': b.status or 'reading',
    } for b in books])


@bp.route('/<int:book_id>/chat', methods=['GET'])
@frontend_login_required
def get_chat(book_id):
    user_id = current_user.safe_id
    chat = BookChat.query.filter_by(user_id=user_id, book_id=book_id).first()
    if not chat:
        book = Book.query.filter_by(id=book_id, user_id=user_id).first_or_404()
        try:
            opening, options = generate_opening(book)
        except Exception:
            opening = f'你好！欢迎来到《{book.title}》的阅读空间，有什么想聊的吗？'
            options = [f'聊聊{book.title}的核心思想', f'作者{book.author}的写作背景', f'这本书适合什么人读']
        chat = BookChat(user_id=user_id, book_id=book_id,
                        messages=[{'role': 'assistant', 'content': opening, 'content_html': _md_to_html(opening)}])
        db.session.add(chat)
        db.session.commit()
        return jsonify({'messages': chat.messages, 'options': options})
    msgs = chat.messages or []
    for m in msgs:
        if m.get('role') == 'assistant' and 'content_html' not in m:
            m['content_html'] = _md_to_html(m.get('content', ''))
    opts = []
    if msgs and msgs[-1].get('role') == 'assistant':
        try:
            opts = generate_options(msgs[-1]['content'])
        except Exception:
            opts = []
    return jsonify({'messages': msgs, 'options': opts})


@bp.route('/<int:book_id>/chat', methods=['POST'])
@frontend_login_required
def send_message(book_id):
    user_id = current_user.safe_id
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
        reply, options = chat_with_book(book, highlights_text, message, history)
    except Exception as e:
        current_app.logger.error(f'AI chat error: {e}')
        return jsonify({'error': 'AI 服务暂时不可用'}), 500

    history.append({'role': 'user', 'content': message})
    history.append({'role': 'assistant', 'content': reply, 'content_html': _md_to_html(reply)})
    if not chat.title or chat.title == '关于本书的对话':
        chat.title = message[:50]
    chat.messages = history
    chat.updated_at = db.func.now()
    db.session.commit()
    return jsonify({'reply': reply, 'reply_html': _md_to_html(reply), 'messages': history, 'options': options})


@bp.route('/<int:book_id>/summary')
@frontend_login_required
def get_summary(book_id):
    user_id = current_user.safe_id
    book = Book.query.filter_by(id=book_id, user_id=user_id).first_or_404()
    cached = BookAIContent.query.filter_by(user_id=user_id, book_id=book_id, content_type='summary').first()
    if cached:
        return jsonify({'content': cached.content, 'content_html': _md_to_html(cached.content), 'cached': True})
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
    return jsonify({'content': content, 'content_html': _md_to_html(content), 'cached': False})


@bp.route('/<int:book_id>/review')
@frontend_login_required
def get_review(book_id):
    user_id = current_user.safe_id
    book = Book.query.filter_by(id=book_id, user_id=user_id).first_or_404()
    cached = BookAIContent.query.filter_by(user_id=user_id, book_id=book_id, content_type='review').first()
    if cached:
        return jsonify({'content': cached.content, 'content_html': _md_to_html(cached.content), 'cached': True})
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
    return jsonify({'content': content, 'content_html': _md_to_html(content), 'cached': False})


@bp.route('/<int:book_id>/analysis')
@frontend_login_required
def get_analysis(book_id):
    user_id = current_user.safe_id
    book = Book.query.filter_by(id=book_id, user_id=user_id).first_or_404()
    cached = BookAIContent.query.filter_by(user_id=user_id, book_id=book_id, content_type='analysis').first()
    if cached:
        return jsonify({'content': cached.content, 'content_html': _md_to_html(cached.content), 'cached': True})
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
    return jsonify({'content': content, 'content_html': _md_to_html(content), 'cached': False})


@bp.route('/<int:book_id>/recommend')
@frontend_login_required
def get_recommendations(book_id):
    user_id = current_user.safe_id
    book = Book.query.filter_by(id=book_id, user_id=user_id).first_or_404()
    other_books = Book.query.filter(Book.user_id == user_id, Book.id != book_id).order_by(Book.updated_at.desc()).limit(20).all()
    read_history = '\n'.join(f'《{b.title}》({b.author or "未知"})' for b in other_books)
    try:
        recs = generate_recommendations(book, read_history)
    except Exception as e:
        current_app.logger.error(f'AI recommend error: {e}')
        return jsonify({'error': '生成推荐失败'}), 500
    return jsonify({'recommendations': recs})
