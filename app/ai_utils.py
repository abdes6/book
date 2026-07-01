"""AI 对话共享工具：OpenAI 客户端、回复解析、选项生成。"""

import re
from flask import current_app
from openai import OpenAI

FORMAT_RULE = '\n回复末尾必须写 ===OPTIONS===\n换行后每行一个选项（共3个），简洁不超过10字\n'


def get_client():
    return OpenAI(
        api_key=current_app.config['DEEPSEEK_API_KEY'],
        base_url=current_app.config['DEEPSEEK_BASE_URL']
    )


def parse_reply(raw):
    if '===OPTIONS===' in raw:
        parts = raw.split('===OPTIONS===', 1)
        reply = parts[0].strip()
        options = [re.sub(r'^\d+[\.\)、]\s*', '', o).strip() for o in
                   parts[1].strip().split('\n') if o.strip()]
        return reply, [o for o in options if o][:3]
    return raw, []


def generate_options(reply):
    client = get_client()
    resp = client.chat.completions.create(
        model=current_app.config['DEEPSEEK_MODEL'],
        messages=[
            {'role': 'system', 'content': '为下面的回复生成3个简短的自然对话选项，每行一个，不要序号和前缀。'},
            {'role': 'user', 'content': reply}
        ],
        temperature=0.5, max_tokens=200
    )
    text = resp.choices[0].message.content
    return [re.sub(r'^\d+[\.\)、]\s*', '', o).strip() for o in
            text.split('\n') if o.strip()][:3]
