# AI 读书助手 — 设计文档

## 1. 概述

在个人藏书管理系统中新增 **AI 读书助手** 功能模块，为用户提供围绕单本书的智能对话、摘要生成、书评撰写、划线笔记分析和阅读推荐能力。

## 2. 架构

### 2.1 新增文件

```
app/ai_reader/
├── __init__.py      蓝图定义 (name='ai_reader', url_prefix='/ai-reader')
├── routes.py        路由：主页面、书列表、对话、摘要、书评、分析、推荐
└── service.py       AI 逻辑层：system prompt 管理、DeepSeek API 调用
```

### 2.2 新数据库模型 (app/models.py)

```python
class BookChat(db.Model):
    __tablename__ = 'book_chat'
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey('users.id'), nullable=False)
    book_id     = Column(Integer, ForeignKey('books.id'), nullable=False)
    title       = Column(String(200), default='关于本书的对话')
    messages    = Column(JSON, nullable=False, default=list)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BookAIContent(db.Model):
    __tablename__ = 'book_ai_content'
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey('users.id'), nullable=False)
    book_id       = Column(Integer, ForeignKey('books.id'), nullable=False)
    content_type  = Column(String(20), nullable=False)   # summary | review | analysis
    content       = Column(Text, nullable=False)
    source_info   = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('user_id', 'book_id', 'content_type'),)
```

### 2.3 蓝图注册 (app/__init__.py)

```python
from app.ai_reader import bp as ai_reader_bp
app.register_blueprint(ai_reader_bp)
```

### 2.4 导航栏入口 (app/templates/base.html)

在「💬 思想家」后新增：`<li class="nav-item"><a class="nav-link" href="{{ url_for('ai_reader.index') }}">🤖 AI 读书</a></li>`

## 3. 路由设计

| 方法 | 路径 | 用途 | 返回值 |
|------|------|------|--------|
| GET | `/ai-reader` | 主页面 | 渲染 `ai_reader/index.html` |
| GET | `/ai-reader/books` | 用户书籍 JSON 列表 | `[{id, title, author, cover_url, status}]` |
| GET | `/ai-reader/<book_id>/chat` | 获取对话历史 | 现存 `BookChat` 的 `messages` |
| POST | `/ai-reader/<book_id>/chat` | 发送消息, 获取 AI 回复 | `{reply, messages}` |
| GET | `/ai-reader/<book_id>/summary` | 生成/获取摘要 | `{content}` |
| GET | `/ai-reader/<book_id>/review` | 生成/获取书评 | `{content}` |
| GET | `/ai-reader/<book_id>/analysis` | 基于划线笔记分析 | `{content}` |
| GET | `/ai-reader/<book_id>/recommend` | 实时推荐 | `{recommendations: [...]}` |

## 4. AI 服务层 (service.py)

### 4.1 system prompt 模板

| 场景 | Temperature | 缓存 | Prompt 核心 |
|------|-------------|------|-------------|
| chat | 0.7 | 否（存 messages） | 读书助手，基于书名/作者/简介/笔记回答问题 |
| summary | 0.3 | 是 | 300-500 字摘要，含核心主题、主要观点、适合人群 |
| review | 0.5 | 是 | 200-400 字书评，含整体评价、亮点、不足、推荐理由 |
| analysis | 0.4 | 是 | 基于划线笔记提炼核心观点(3-5个) + 金句 + 逻辑关系 |
| recommend | 0.6 | 否 | 基于当前书 + 用户已读列表推荐 5 本 |

### 4.2 上下文注入

对话和分析场景自动注入书籍信息：
- `{title}`, `{author}`, `{summary}` — 来自 `Book` 模型
- `{highlights_text}` — 该用户在该书的前 20 条划线笔记

### 4.3 复用逻辑

- OpenAI 客户端：复用 `app/thinker/routes.py` 中的 `_get_openai_client()`
- 直接 import 该函数，不重复创建

## 5. 前端模板

### 5.1 文件

```
app/templates/ai_reader/
└── index.html
```

### 5.2 页面结构

- **左侧面板**（约 30% 宽度）
  - 搜索输入框（按书名/作者过滤）
  - 书籍卡片列表，点击高亮选中
- **右侧面板**（约 70% 宽度）
  - 5 个 Bootstrap Tab：对话、摘要、书评、分析、推荐
  - **对话 Tab**：消息气泡列表 + 底部输入框 + 发送按钮
  - **摘要/书评/分析 Tab**：首次加载显示 spinner，完成后展示内容 +「重新生成」按钮
  - **推荐 Tab**：推荐内容展示

### 5.3 JS 交互

- 选书 → 切换右侧 Tab 为「对话」，fetch 对话历史
- 发送消息 → POST, 加载中显示「正在思考...」, 回复追加到气泡列表
- Tab 切换 → 首次进入各 Tab 自动触发 API 调用
- 全部异步 fetch, 无页面刷新

## 6. 错误处理

| 场景 | 处理 |
|------|------|
| DeepSeek API 不可用 | 返回 `{error: 'AI 服务暂时不可用'}`, 前端显示警告条 |
| 该书无划线笔记 | 分析 Tab 提示「暂无划线笔记，无法分析」 |
| 书籍信息不完整 | 对话/摘要仍可工作 |
| 消息为空 | 前端禁用发送按钮，后端返回 400 |

## 7. Out of Scope

- 不修改现有 Thinker 蓝图的任何代码
- 不实现流式输出（SSE）
- 不实现对话历史管理（删除/重命名）
