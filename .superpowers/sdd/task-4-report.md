# Task 4 Report: 前端模板 (AI 读书助手)

## 实现内容
- 创建 `app/templates/ai_reader/index.html` — AI 读书助手主页面

## 文件变更
- **新增:** `app/templates/ai_reader/index.html`

## 页面结构
- 左侧书籍选择面板 (col-3): 搜索框 + 书籍列表 (从 `ai_reader.book_list` API 加载)
- 右侧主面板 (col-9): 含占位提示和 5 个标签页（对话/摘要/书评/分析/推荐）
- JavaScript:
  - 书籍列表加载与搜索过滤
  - 标签页切换（摘要/书评/分析/推荐仅在首次加载时获取）
  - 对话功能（GET 加载历史 + POST 发送消息）
  - 工具函数: `escapeHtml`, `addChatBubble`, `regenerate`

## API 端点
| 方法 | 端点 | 用途 |
|------|------|------|
| GET | `{{ url_for("ai_reader.book_list") }}` | 获取书籍列表 |
| GET | `/ai-reader/<id>/chat` | 获取聊天历史 |
| POST | `/ai-reader/<id>/chat` | 发送聊天消息 |
| GET | `/ai-reader/<id>/summary` | 获取摘要 |
| GET | `/ai-reader/<id>/review` | 获取书评 |
| GET | `/ai-reader/<id>/analysis` | 获取分析 |
| GET | `/ai-reader/<id>/recommend` | 获取推荐 |

## 自审
- 模板扩展 `base.html`，使用 `{% block title %}`, `{% block content %}`, `{% block scripts %}`
- 使用 Bootstrap 5 类 + 自定义 CSS 变量 (`var(--cream)`, `var(--accent)`)
- JS 使用 `url_for` 加载书籍列表，动态路径 `/ai-reader/<id>/...` 匹配蓝图前缀
- 无提交

## 问题
- 确保 `ai_reader` 蓝图中存在 `book_list` 路由（返回 JSON 数组，含 `id`, `title`, `author`）
- 若标签页 API 返回大量数据，建议后续添加防抖或缓存过期策略
