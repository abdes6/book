"""
AI 对话共享工具模块
------------------
提供 Open AI 客户端创建、回复解析和选项生成三个核心能力。
Thinker 对话和 AI Reader 两个子系统共享此模块，避免代码重复。

关键设计：
- ===OPTIONS=== 是一种结构化输出协议：AI 在回复末尾附加 3 个建议追问选项
- parse_reply() 从 AI 原始回复中分离正文和选项
- generate_options() 是回退方案：当 AI 未按协议输出时，二次调用生成选项
"""

import re
from flask import current_app
from openai import OpenAI

# ── 结构化输出协议 ──────────────────────────────────────────────────
# AI 回复末尾必须包含此格式标记，后方跟随 3 行选项（每行一个，不超过 10 字）
FORMAT_RULE = '\n回复末尾必须写 ===OPTIONS===\n换行后每行一个选项（共3个），简洁不超过10字\n'


def get_client():
    """创建 DeepSeek API 客户端（兼容 OpenAI SDK 接口）。"""
    return OpenAI(
        api_key=current_app.config['DEEPSEEK_API_KEY'],
        base_url=current_app.config['DEEPSEEK_BASE_URL']
    )


def parse_reply(raw):
    """
    从 AI 原始回复中分离正文和选项。
    返回 (reply_text, [option1, option2, ...])
    如果 AI 未按协议输出 ===OPTIONS===，则返回原始文本和空列表。
    """
    if '===OPTIONS===' in raw:
        parts = raw.split('===OPTIONS===', 1)
        reply = parts[0].strip()
        options = [re.sub(r'^\d+[\.\)、]\s*', '', o).strip() for o in
                   parts[1].strip().split('\n') if o.strip()]
        return reply, [o for o in options if o][:3]
    return raw, []


def generate_options(reply):
    """
    回退方案：当 AI 在原始回复中未包含选项时，
    单独调用 API 为已有回复生成 3 个自然对话选项。
    """
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
