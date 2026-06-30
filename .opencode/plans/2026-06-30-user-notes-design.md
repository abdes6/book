# 用户个人读书笔记 — 设计文档

## 概述
为前端用户增加多篇、Markdown 格式、支持本地图片上传的个人读书笔记功能。每个用户可对同一本书写多篇笔记，图文混排，互相独立。

---

## 数据模型

### `Note` 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| user_id | FK → users.id, nullable=False | 笔记所属用户 |
| book_id | FK → books.id, nullable=False | 关联书籍 |
| title | String(200), nullable=False | 笔记标题 |
| content | Text | Markdown 正文 |
| created_at | DateTime, default=now | |
| updated_at | DateTime, default=now, onupdate=now | |

关系：
- `User.notes = db.relationship('Note', backref='author', lazy='dynamic')`
- `Book.user_notes = db.relationship('Note', backref='book', lazy='dynamic', order_by=Note.updated_at.desc())`

### `NoteImage` 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| note_id | FK → note.id, nullable=True | 所属笔记（可为空，上传但未保存的图片） |
| filename | String(200) | 原始文件名 |
| stored_path | String(300) | 存储相对路径 |
| uploaded_at | DateTime, default=now | |

---

## 存储

- 图片目录：`app/static/uploads/notes/`
- 命名规则：`{user_id}_{timestamp}_{uuid_hex8}.{ext}`
- 限制：png/jpg/jpeg/gif/webp, ≤5MB
- 使用 `werkzeug.utils.secure_filename` + 重命名防路径穿越和重名

---

## 蓝图与路由

新增 `app/notes/` 蓝图，注册前缀 `/notes`：

| 方法 | 路由 | 视图 | 说明 |
|------|------|------|------|
| GET | `/notes/book/<int:book_id>` | `book_notes` | 返回某本书的笔记列表 (JSON) |
| GET | `/notes/create/<int:book_id>` | `note_create_page` | 新建笔记页面 |
| POST | `/notes/create/<int:book_id>` | `note_create` | 提交笔记 |
| GET | `/notes/<int:id>` | `note_detail` | 笔记详情页（渲染后 HTML） |
| GET | `/notes/<int:id>/edit` | `note_edit_page` | 编辑笔记页面 |
| POST | `/notes/<int:id>/edit` | `note_edit` | 提交编辑 |
| POST | `/notes/<int:id>/delete` | `note_delete` | 删除笔记（连带图片） |
| POST | `/notes/upload-image` | `upload_image` | 上传图片，返回 `![](...)` |

所有路由需 `@frontend_login_required`，该装饰器从 `app/main/routes.py` 提取到 `app/extensions.py` 中定义，各蓝图统一引用。

---

## Markdown 渲染

服务端渲染，保存时存原始 Markdown，展示时渲染为 HTML：

```python
import markdown
import bleach

ALLOWED_TAGS = ['h1','h2','h3','h4','h5','h6','p','br','strong','em',
    'a','ul','ol','li','code','pre','blockquote','img','hr','table',
    'thead','tbody','tr','th','td','span','div']

ALLOWED_ATTRS = {'img':['src','alt','title'], 'a':['href','title','target'],
    '*':['class']}

def render_markdown(text):
    html = markdown.markdown(text or '', extensions=['extra','codehilite'])
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)
```

---

## 前端 UI

### 图书详情页新增"我的笔记" tab
- 在划线笔记下方增加 tab 切换（划线笔记 / 我的笔记）
- 加载时 AJAX 请求 `/notes/book/<book_id>` 获取笔记列表
- 每篇显示：标题、摘要（前100字）、更新日期、编辑/删除按钮
- 底部"写新笔记"按钮跳转到 `/notes/create/<book_id>`

### 新建/编辑页面
- Markdown 编辑器：使用 EasyMDE (SimpleMDE 维护版) CDN
- 标题输入框 + 编辑器 + 图片上传按钮 + 保存/取消
- 图片上传按钮 → 调 POST `/notes/upload-image` → 插入 `![](url)` 到光标位置
- 保存后跳回图书详情页

### 笔记详情
- 点击笔记标题 → 跳转到 `/notes/<id>` 独立页面
- 使用渲染后的 HTML 展示

---

## 依赖添加

在 `requirements.txt` 中新增：
```
markdown
bleach
```

---

## 文件变更清单

| 操作 | 文件 |
|------|------|
| 新增 | `app/notes/__init__.py` |
| 新增 | `app/notes/routes.py` |
| 新增 | `app/notes/forms.py` |
| 修改 | `app/models.py` — 新增 Note, NoteImage 模型 |
| 修改 | `app/__init__.py` — 注册 notes 蓝图 + markdown Jinja2 过滤器 |
| 修改 | `app/extensions.py` — 添加 `frontend_login_required` 装饰器（从 main/routes.py 提取） |
修改 | `app/main/routes.py` — 改为引用 `app.extensions.frontend_login_required` |
| 新增 | `app/templates/notes/create.html` |
| 新增 | `app/templates/notes/edit.html` |
| 新增 | `app/templates/notes/detail.html` |
| 修改 | `app/templates/books/detail.html` — 增加"我的笔记" tab |
| 修改 | `requirements.txt` — 添加 markdown, bleach |
| 迁移 | 自动生成迁移脚本新增 note / note_image 表 |
| 新增 | `app/static/uploads/notes/.gitkeep` |
