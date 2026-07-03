# 个人藏书管理系统 — 项目文档

> Flask + MySQL + 微信读书 API + DeepSeek AI  
> Web 开发技术课程实训项目

---

## 一、项目概述

基于 Flask 的 Web 应用，集成微信读书 API 实现书架同步、划线笔记导入、阅读统计，并接入 DeepSeek AI 提供智能读书助手和哲学家对话功能。支持多用户注册，数据按 user_id 完全隔离。

**技术栈**: Python 3.10 / Flask 3.0 / SQLAlchemy / MySQL / Bootstrap 5 / Chart.js / DeepSeek API

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────────┐
│                    浏览器前端                              │
│  Bootstrap 5 + Chart.js + Vanilla JS (Fetch API)          │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼───────────────────────────────────┐
│                  Flask 应用工厂                             │
│  ┌─────────┐ ┌─────────┐ ┌────────┐ ┌────────┐ ┌──────┐ │
│  │  main   │ │  auth   │ │ admin  │ │ notes  │ │weread│ │
│  │  首页    │ │ 登录注册 │ │ 后台管理│ │ 笔记系统│ │ API  │ │
│  │  书架    │ │ 验证码  │ │  CRUD  │ │ 图片上传│ │ 集成 │ │
│  │  统计    │ │ CSRF   │ │        │ │ 导出   │ │      │ │
│  └─────────┘ └─────────┘ └────────┘ └────────┘ └──────┘ │
│  ┌─────────┐ ┌──────────────┐                             │
│  │ thinker │ │  ai_reader   │                             │
│  │AI哲学家 │ │  AI 读书助手  │                             │
│  └─────────┘ └──────────────┘                             │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│                    外部服务                                 │
│  ┌──────────────┐  ┌──────────────┐                      │
│  │ 微信读书 API  │  │ DeepSeek AI  │                      │
│  │ 书架/划线/统计│  │ 对话/摘要/书评│                      │
│  └──────────────┘  └──────────────┘                      │
└──────────────────────────────────────────────────────────┘
```

### Blueprint 路由表 (7 个模块)

| Blueprint | URL 前缀 | 功能 |
|-----------|---------|------|
| `main` | `/` | 首页、书架浏览、书籍详情、划线搜索、阅读统计 |
| `auth` | `/auth` | 登录、注册（含验证码）、API Key 管理 |
| `admin` | `/admin` | 后台管理（图书/分类/笔记/用户 CRUD） |
| `notes` | `/notes` | Markdown 笔记创建/编辑/导出、图片上传 |
| `thinker` | `/thinkers` | 18 位 AI 哲学家对话 |
| `ai_reader` | `/ai-reader` | AI 摘要、书评、划线分析、书籍推荐 |
| `weread` | `/weread` | 微信读书 API 代理 |

---

## 三、数据库设计 (11 张表)

```
users ──────┬── books ──────┬── highlights      (划线笔记)
            │               ├── notes ─── note_images  (笔记+图片)
            │               ├── book_chat       (AI 对话记录)
            │               └── book_ai_content (AI 生成内容缓存)
            │
            ├── read_stat        (阅读聚合统计)
            ├── daily_read_stat  (每日阅读明细)
            ├── read_goal        (阅读目标)
            │
            ├── thinker ── conversation  (AI 哲学家对话)
            │
            └── categories       (19个预设分类)
```

### 核心表说明

| 表名 | 关键字段 | 说明 |
|------|---------|------|
| `users` | weread_api_key, shelf_synced | 每个用户独立的微信读书 API Key |
| `books` | weread_book_id, shelved | 微信读书导入去重；shelved=False 软删除 |
| `highlights` | weread_bookmark_id, mark_text | 按书籍+用户导入，bookmark_id 去重 |
| `notes` | content(Markdown), highlight_id | 长文笔记，可引用划线 |
| `note_images` | stored_path, display_width | 笔记附图，支持拖拽缩放 |
| `read_stat` | mode, period_start, prefer_category | 4 种时间维度聚合统计 |
| `daily_read_stat` | date, total_read_time | 每日阅读秒数，用于热力图/趋势图 |
| `conversation` | messages(JSON), thinker_id | AI 对话记录，消息数组 |
| `book_chat` | messages(JSON), book_id | 书籍 AI 对话记录 |
| `book_ai_content` | content_type, content | AI 生成内容缓存 (summary/review/analysis) |

---

## 四、核心功能详解

### 4.1 微信读书书架同步

**数据流**: 用户注册 → `import_shelf_to_db()` → 微信读书 API `/shelf/sync` → 逐本写入 books 表

```python
# 全量导入（首次注册）
def import_shelf_to_db(user_id, api_key=None):
    data = get_shelf(api_key=api_key)        # 调用微信读书 API
    for b in data['books']:
        weread_id = b['bookId']
        existing = Book.query.filter_by(weread_book_id=weread_id, user_id=user_id).first()
        if existing: continue                  # 去重跳过
        book = Book(user_id=user_id, title=..., weread_book_id=weread_id)
        db.session.add(book)
    db.session.commit()

# 增量同步（每次访问书架页，300s 缓存）
def sync_shelf_for_user(user_id):
    # 对比 API 书架和本地数据库 → 增/改/软删
```

### 4.2 划线批量导入

**数据流**: 登录 → 后台线程 → `import_all_highlights_for_user()` → 逐本调用微信读书 API `/book/bookmarklist` → 写入 highlights 表

```python
def import_all_highlights_for_user(user_id, api_key=None):
    # 只处理没有划线的书（~Book.highlights.any() 跳过已导入）
    books = Book.query.filter(~Book.highlights.any(), ...)
    for book in books:
        import_highlights_for_book(book, user_id, api_key=api_key)

def import_highlights_for_book(book, user_id, api_key=None):
    data = get_bookmarklist(book.weread_book_id, api_key=api_key)
    for item in data['updated']:
        if item['bookmarkId'] in existing_ids: continue  # 去重
        Highlight(user_id=user_id, book_id=book.id, mark_text=...)
    db.session.commit()
```

**关键技术点**:
- **后台线程 + app context**: 避免注册/登录请求阻塞 5+ 分钟
- **api_key 参数贯穿**: 注册时 login_user 尚未调用，需显式传递 api_key
- **weread_bookmark_id 去重**: 同一划线不会重复导入

### 4.3 多用户数据隔离

所有数据表通过 `user_id` 外键隔离，查询时始终过滤：

```python
# 全局划线搜索 — 只查询当前用户的划线
query = Highlight.query.filter(
    Highlight.user_id == current_user.safe_id,
    Highlight.mark_text.contains(q)
).join(Book, Highlight.book_id == Book.id)
```

### 4.4 AI 读书助手

- **对话模式**: 用户与指定书籍的 AI 对话，对话历史作为上下文发送
- **摘要/书评/分析/推荐**: 调用 DeepSeek API，结果缓存到 `book_ai_content` 表
- **划线分析**: 将用户对该书的全部划线作为输入，生成主题分析

### 4.5 AI 哲学家对话

18 位哲学家（老子、苏格拉底、尼采、萨特等），每位有定制的 system_prompt 定义性格和语气。对话历史存储在 `messages` (JSON) 字段中。

### 4.6 安全机制

| 机制 | 实现 |
|------|------|
| 密码哈希 | Werkzeug `generate_password_hash()` / scrypt |
| CSRF 防护 | Flask-WTF + 自定义 AJAX 拦截器（自动注入 X-CSRFToken） |
| 频率限制 | 滑动窗口算法：注册 5次/5min，验证码 30次/1min |
| 图形验证码 | PIL 生成（旋转+扭曲+噪点+弧线干扰） |
| 路径遍历防护 | `_safe_stored_path()` 验证上传路径 |
| Open Redirect 防护 | `_is_safe_url()` 验证重定向目标 |

---

## 五、项目结构

```
实训/
├── run.py                  # 入口：加载 .env → 校验配置 → create_app() → app.run()
├── config.py               # 配置类：从 .env 加载 SECRET_KEY/DATABASE_URL/API Keys
├── requirements.txt        # 依赖清单
├── .env                    # 环境变量（不入版本控制）
├── PROJECT.md              # 本文档
├── app/
│   ├── __init__.py         # 应用工厂 create_app()
│   ├── models.py           # 11 张数据表定义
│   ├── extensions.py       # Flask 扩展 + 频率限制 + 登录装饰器
│   ├── forms.py            # WTForms 表单类
│   ├── cli.py              # CLI 命令（init-db, import-all-highlights）
│   ├── ai_utils.py         # AI 公共函数（DeepSeek 客户端、回复解析）
│   ├── main/               # 首页/书架/统计/划线搜索
│   ├── auth/               # 登录/注册/验证码/API Key 管理
│   ├── admin/               # 后台管理 CRUD
│   │   └── captcha.py      # 图形验证码生成器
│   ├── notes/              # 笔记系统（Markdown 编辑、图片上传、导出）
│   ├── weread/             # 微信读书 API 集成
│   │   ├── api.py          # HTTP 请求封装
│   │   ├── importer.py     # 书架导入、划线导入
│   │   └── stats_sync.py   # 阅读统计同步
│   ├── thinker/            # AI 哲学家对话
│   ├── ai_reader/          # AI 读书助手
│   ├── static/             # CSS/JS 静态资源
│   │   └── css/custom.css  # 全局样式（含暗色模式）
│   ├── templates/          # Jinja2 模板
│   │   ├── base.html       # 全局布局
│   │   ├── notes/          # 笔记模板 (create/edit/detail)
│   │   ├── thinkers/       # 哲学家对话模板
│   │   └── ai_reader/      # AI 读书模板
│   └── uploads/            # 用户上传的笔记图片（不入版本控制）
```

---

## 六、数据流示意

### 用户注册完整流程

```
1. 填写表单 (username, email, password, API Key, 验证码)
2. POST /auth/register
3. 验证码校验 (session['captcha'] == form.captcha.upper())
4. User 写入数据库
5. import_shelf_to_db(user_id, api_key) → 微信读书 API /shelf/sync → books 表
6. login_user(user)    ← 登录
7. 后台线程启动:
   ├─ app.app_context()  ← Flask 应用上下文
   └─ import_all_highlights_for_user(user_id, api_key)
      └─ 逐本调用 API /book/bookmarklist → highlights 表
8. 返回首页 (302 redirect)
```

### 图片上传流程

```
1. 用户点击 +上传 → type="button" 不提交表单
2. File input change 事件 → FormData → fetch POST /notes/upload-image
3. @csrf.exempt 豁免 CSRF (FormData 不上传 CSRF 避免干扰 Content-Type)
4. @frontend_login_required 验证登录
5. 文件保存到 app/uploads/notes/ (static 外，避免 IDE 文件监听刷新)
6. 返回 JSON {url, stored_path, original_name}
7. JS 增量追加图片卡片 (renderOneImage)，不重绘现有 DOM
```

---

## 七、关键技术决策

| 决策 | 理由 |
|------|------|
| 应用工厂模式 `create_app()` | 便于测试、多环境配置 |
| Blueprint 模块化 | 7 个独立功能模块，松散耦合 |
| 软删除 `shelved=False` | 保留用户数据，支持重新上架恢复 |
| 后台线程导入划线 | 786 本书 × 0.5秒/本 ≈ 6分钟，不能在请求中同步等待 |
| 上传目录移出 `static/` | IDE 文件监听不会检测到新图片，避免页面刷新 |
| 用户独立 API Key | 多用户场景，每人用自己的微信读书 token |
| Markdown + bleach 过滤 | 支持富文本编辑，同时防御 XSS 攻击 |
| AI 内容缓存表 | 避免重复调用 DeepSeek API，节省成本和时间 |
