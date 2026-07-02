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

