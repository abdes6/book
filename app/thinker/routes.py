import json
import markdown as md_lib
import bleach
from datetime import datetime
from flask import current_app, jsonify, request, render_template
from flask_login import current_user
from app.ai_utils import get_client, parse_reply, generate_options, FORMAT_RULE
from app.extensions import csrf, db, frontend_login_required
from app.thinker import bp
from app.models import Thinker, Conversation

_MD_TAGS = ['h1','h2','h3','h4','h5','h6','p','br','strong','em',
    'a','ul','ol','li','code','pre','blockquote','img','hr','table',
    'thead','tbody','tr','th','td','span','div']
_MD_ATTRS = {'img':['src','alt','title'], 'a':['href','title','target'], '*':['class']}


def _md_to_html(text):
    if not text:
        return ''
    html = md_lib.markdown(text, extensions=['extra', 'codehilite'])
    return bleach.clean(html, tags=_MD_TAGS, attributes=_MD_ATTRS)


def _chat_with_thinker(system_prompt, messages):
    client = get_client()
    resp = client.chat.completions.create(
        model=current_app.config["DEEPSEEK_MODEL"],
        messages=[
            {"role": "system", "content": system_prompt},
            *messages
        ],
        temperature=0.7,
        max_tokens=2048
    )
    return resp.choices[0].message.content


@bp.route('/thinkers')
@frontend_login_required
def list_thinkers():
    thinkers = Thinker.query.order_by(Thinker.sort_order).all()
    return render_template('thinkers/list.html', thinkers=thinkers)


@bp.route('/thinkers/<slug>')
@frontend_login_required
def chat(slug):
    thinker = Thinker.query.filter_by(slug=slug).first_or_404()
    user_id = current_user.safe_id
    conversations = Conversation.query.filter_by(
        user_id=user_id, thinker_id=thinker.id
    ).order_by(Conversation.updated_at.desc()).all()

    opening_options = []
    if not conversations and thinker.opening_line:
        text, opts = parse_reply(thinker.opening_line)
        conv = Conversation(
            user_id=user_id, thinker_id=thinker.id,
            title="新对话",
            messages=[{"role": "assistant", "content": text, "content_html": _md_to_html(text)}]
        )
        db.session.add(conv)
        db.session.commit()
        conversations = [conv]
        opening_options = opts
    elif conversations and thinker.opening_line:
        latest = conversations[0]
        has_user_reply = any(m.get('role') == 'user' for m in (latest.messages or []))
        if not has_user_reply:
            _, opening_options = parse_reply(thinker.opening_line)

    for conv in conversations:
        for m in (conv.messages or []):
            if m.get('role') == 'assistant' and 'content_html' not in m:
                m['content_html'] = _md_to_html(m.get('content', ''))

    return render_template('thinkers/chat.html', thinker=thinker,
                           conversations=conversations,
                           opening_options=opening_options)


@bp.route('/thinkers/<slug>/new', methods=['POST'])
@csrf.exempt
@frontend_login_required
def new_conversation(slug):
    thinker = Thinker.query.filter_by(slug=slug).first_or_404()
    user_id = current_user.safe_id
    text, opts = parse_reply(thinker.opening_line or "")
    conv = Conversation(user_id=user_id, thinker_id=thinker.id,
                        title="新对话",
                        messages=[{"role": "assistant", "content": text, "content_html": _md_to_html(text)}])
    db.session.add(conv)
    db.session.commit()
    return jsonify({
        'id': conv.id,
        'title': conv.title,
        'messages': conv.messages,
        'options': opts,
        'updated_at': conv.updated_at.isoformat()
    })


@bp.route('/thinkers/<slug>/chat', methods=['POST'])
@csrf.exempt
@frontend_login_required
def send_message(slug):
    thinker = Thinker.query.filter_by(slug=slug).first_or_404()
    user_id = current_user.safe_id
    data = request.get_json()
    conv_id = data.get('conversation_id')
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': '消息不能为空'}), 400

    if conv_id:
        conv = Conversation.query.filter_by(id=conv_id, user_id=user_id).first_or_404()
    else:
        conv = Conversation(user_id=user_id, thinker_id=thinker.id,
                            title=message[:50], messages=[])
        db.session.add(conv)
        db.session.commit()
        conv_id = conv.id

    history = list(conv.messages) if conv.messages else []
    history.append({"role": "user", "content": message})

    try:
        combined_prompt = thinker.system_prompt + "\n\n" + FORMAT_RULE
        raw = _chat_with_thinker(combined_prompt, history)
        reply, options = parse_reply(raw)
        if not options:
            options = generate_options(reply)
    except Exception as e:
        current_app.logger.error(f'DeepSeek API error: {e}')
        return jsonify({'error': '对话服务暂时不可用'}), 500

    reply_html = _md_to_html(reply)
    history.append({"role": "assistant", "content": reply, "content_html": reply_html})
    if not conv.title or conv.title == "新对话":
        conv.title = message[:50]
    conv.messages = history
    conv.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'conversation_id': conv.id,
        'reply': reply,
        'reply_html': reply_html,
        'options': options,
        'history': history
    })


@bp.route('/thinkers/conversation/<int:id>')
@frontend_login_required
def get_conversation(id):
    user_id = current_user.safe_id
    conv = Conversation.query.filter_by(id=id, user_id=user_id).first_or_404()
    msgs = conv.messages or []
    for m in msgs:
        if m.get('role') == 'assistant' and 'content_html' not in m:
            m['content_html'] = _md_to_html(m.get('content', ''))
    return jsonify({
        'id': conv.id,
        'thinker_id': conv.thinker_id,
        'title': conv.title,
        'messages': msgs,
        'updated_at': conv.updated_at.isoformat()
    })


@bp.route('/thinkers/conversation/<int:id>/delete', methods=['POST'])
@csrf.exempt
@frontend_login_required
def delete_conversation(id):
    user_id = current_user.safe_id
    conv = Conversation.query.filter_by(id=id, user_id=user_id).first_or_404()
    db.session.delete(conv)
    db.session.commit()
    return jsonify({'ok': True})


@bp.route('/thinkers/conversation/<int:id>/rename', methods=['POST'])
@csrf.exempt
@frontend_login_required
def rename_conversation(id):
    user_id = current_user.safe_id
    conv = Conversation.query.filter_by(id=id, user_id=user_id).first_or_404()
    data = request.get_json()
    conv.title = data.get('title', conv.title)[:200]
    db.session.commit()
    return jsonify({'ok': True})
