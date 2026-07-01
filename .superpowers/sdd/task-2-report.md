# Task 2: AI 服务层 — 报告

## 状态: DONE

## 实现内容
创建 `app/ai_reader/service.py`，实现完整的 AI 阅读助手服务层。

## 文件变更
- **新增**: `app/ai_reader/service.py`

## 实现的函数
| 函数 | 说明 |
|------|------|
| `_client()` | 工厂函数，返回 OpenAI 客户端实例 |
| `_call_ai(prompt, temp, max_tokens)` | 简单文本补全封装 |
| `_build_context(book, highlights_text)` | 构建 prompt 格式化上下文字典 |
| `chat_with_book(book, highlights, message, history)` | 带历史消息的多轮对话 |
| `generate_summary(book, highlights)` | 生成书籍摘要（300-500字） |
| `generate_review(book, highlights)` | 生成书评（200-400字） |
| `generate_analysis(book, highlights)` | 分析划线笔记（核心观点+金句+逻辑关系） |
| `generate_recommendations(book, read_history)` | 生成推荐书目（解析为列表） |

## 自审发现
1. **不存在 `app/ai_reader/__init__.py` 导入** — `__init__.py` 已存在且不含 service 导入。这是正常的，`service.py` 由 `routes.py` 按需导入即可。
2. **依赖项** — 依赖 `openai` 包（已安装 `v2.44.0`）和 Flask 应用配置项 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`（当前项目已有）。
3. **无硬编码** — 所有 API 密钥和模型名均通过 `current_app.config` 获取，符合现有项目模式。
4. **Prompt 模板** — 与任务说明一致，均设为模块级常量（`PROMPTS`、`TEMPS`、`MAX_TOKENS`）。

## 问题/担忧
- 无

## 报告文件路径
`.superpowers\sdd\task-2-report.md`
