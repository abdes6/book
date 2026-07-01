import json
from datetime import datetime
from flask import current_app, jsonify, request, render_template
from flask_login import current_user
from openai import OpenAI
from app.extensions import db, frontend_login_required, csrf
from app.thinker import bp
from app.models import Thinker, Conversation


def _get_openai_client():
    return OpenAI(
        api_key=current_app.config["DEEPSEEK_API_KEY"],
        base_url=current_app.config["DEEPSEEK_BASE_URL"]
    )


def _chat_with_thinker(system_prompt, messages):
    client = _get_openai_client()
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


FORMAT_RULE = """【强制格式 - 每次都必须遵守】
1. 你的回复末尾必须写 ===OPTIONS===
2. 换行后每行一个选项（共3个），不要加序号
3. 选项必须基于你刚才回复的内容，简洁（不超过10字）、有启发性、让对话能自然继续"""


def _parse_reply(raw):
    if "===OPTIONS===" in raw:
        parts = raw.split("===OPTIONS===", 1)
        reply = parts[0].strip()
        options = [o.strip().strip("-").strip() for o in parts[1].strip().split("\n") if o.strip()]
        return reply, [o for o in options if o][:3]
    return raw, []


def _generate_options(reply):
    client = _get_openai_client()
    resp = client.chat.completions.create(
        model=current_app.config["DEEPSEEK_MODEL"],
        messages=[
            {"role": "system", "content": "为下面的回复生成3个简短的自然对话选项，每行一个，不要序号和前缀。"},
            {"role": "user", "content": reply}
        ],
        temperature=0.5,
        max_tokens=200
    )
    text = resp.choices[0].message.content
    return [o.strip().strip("-").strip() for o in text.split("\n") if o.strip()][:3]


@bp.route('/thinkers')
@frontend_login_required
def list_thinkers():
    thinkers = Thinker.query.order_by(Thinker.sort_order).all()
    return render_template('thinkers/list.html', thinkers=thinkers)


@bp.route('/thinkers/<slug>')
@frontend_login_required
def chat(slug):
    thinker = Thinker.query.filter_by(slug=slug).first_or_404()
    user_id = int(current_user.get_id().replace('u_', ''))
    conversations = Conversation.query.filter_by(
        user_id=user_id, thinker_id=thinker.id
    ).order_by(Conversation.updated_at.desc()).all()

    opening_options = []
    if not conversations and thinker.opening_line:
        text, opts = _parse_reply(thinker.opening_line)
        conv = Conversation(
            user_id=user_id, thinker_id=thinker.id,
            title="新对话",
            messages=[{"role": "assistant", "content": text}]
        )
        db.session.add(conv)
        db.session.commit()
        conversations = [conv]
        opening_options = opts
    elif conversations and thinker.opening_line:
        latest = conversations[0]
        has_user_reply = any(m.get('role') == 'user' for m in (latest.messages or []))
        if not has_user_reply:
            _, opening_options = _parse_reply(thinker.opening_line)

    return render_template('thinkers/chat.html', thinker=thinker,
                           conversations=conversations,
                           opening_options=opening_options)


@bp.route('/thinkers/<slug>/new', methods=['POST'])
@csrf.exempt
@frontend_login_required
def new_conversation(slug):
    thinker = Thinker.query.filter_by(slug=slug).first_or_404()
    user_id = int(current_user.get_id().replace('u_', ''))
    text, opts = _parse_reply(thinker.opening_line or "")
    conv = Conversation(user_id=user_id, thinker_id=thinker.id,
                        title="新对话",
                        messages=[{"role": "assistant", "content": text}])
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
    user_id = int(current_user.get_id().replace('u_', ''))
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
        reply, options = _parse_reply(raw)
        if not options:
            options = _generate_options(reply)
    except Exception as e:
        current_app.logger.error(f'DeepSeek API error: {e}')
        return jsonify({'error': '对话服务暂时不可用'}), 500

    history.append({"role": "assistant", "content": reply})
    if not conv.title or conv.title == "新对话":
        conv.title = message[:50]
    conv.messages = history
    conv.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'conversation_id': conv.id,
        'reply': reply,
        'options': options,
        'history': history
    })


@bp.route('/thinkers/conversation/<int:id>')
@frontend_login_required
def get_conversation(id):
    user_id = int(current_user.get_id().replace('u_', ''))
    conv = Conversation.query.filter_by(id=id, user_id=user_id).first_or_404()
    return jsonify({
        'id': conv.id,
        'thinker_id': conv.thinker_id,
        'title': conv.title,
        'messages': conv.messages,
        'updated_at': conv.updated_at.isoformat()
    })


@bp.route('/thinkers/conversation/<int:id>/delete', methods=['POST'])
@frontend_login_required
def delete_conversation(id):
    user_id = int(current_user.get_id().replace('u_', ''))
    conv = Conversation.query.filter_by(id=id, user_id=user_id).first_or_404()
    db.session.delete(conv)
    db.session.commit()
    return jsonify({'ok': True})


@bp.route('/thinkers/conversation/<int:id>/rename', methods=['POST'])
@frontend_login_required
def rename_conversation(id):
    user_id = int(current_user.get_id().replace('u_', ''))
    conv = Conversation.query.filter_by(id=id, user_id=user_id).first_or_404()
    data = request.get_json()
    conv.title = data.get('title', conv.title)[:200]
    db.session.commit()
    return jsonify({'ok': True})
