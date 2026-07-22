# 个人藏书管理系统

> Flask + MySQL + 微信读书 API + DeepSeek AI
>
> Web 开发技术课程实训项目

---

## 功能特性

- **微信读书集成** — 书架自动同步（增量 + 全量）、划线笔记批量导入、阅读统计
- **AI 读书助手** — DeepSeek 驱动的书籍摘要、书评、划线分析、书籍推荐、书籍对话
- **AI 哲学家对话** — 与 18 位哲学家（老子、苏格拉底、尼采等）深度对话
- **阅读统计仪表盘** — 30 日趋势图、年度热力图、连续阅读记录、阅读目标管理
- **Markdown 笔记系统** — 创建/编辑/导出笔记，支持图片上传与拖拽缩放
- **全局划线搜索** — 跨书籍快速搜索微信读书划线笔记
- **多用户系统** — 注册登录、独立微信读书 API Key、数据完全隔离
- **安全管理** — 图形验证码、CSRF 防护、频率限制、密码哈希

## 技术栈

| 层 | 技术 |
|------|------|
| 后端 | Python 3.10 / Flask 3.0 / SQLAlchemy |
| 数据库 | MySQL 8.0 (PyMySQL) |
| 前端 | Bootstrap 5 / Chart.js / Jinja2 |
| AI | DeepSeek API (OpenAI 兼容 SDK) |
| 外部 API | 微信读书 Agent Gateway |
| 迁移 | Flask-Migrate (Alembic) |

## 项目结构

```
实训/
├── run.py                  # 应用入口
├── config.py               # 配置（从 .env 加载）
├── requirements.txt        # 依赖清单
├── app/
│   ├── __init__.py         # 应用工厂（7 个 Blueprint 注册）
│   ├── models.py           # 11 张数据表
│   ├── extensions.py       # Flask 扩展 + 频率限制 + 登录装饰器
│   ├── forms.py            # WTForms 表单
│   ├── cli.py              # CLI 命令（init-db, import-highlights 等）
│   ├── ai_utils.py         # AI 公共函数（DeepSeek 客户端、回复解析）
│   ├── main/               # 首页、书架、书籍详情、统计、划线搜索
│   ├── auth/               # 登录、注册、验证码、API Key 管理
│   ├── admin/              # 后台管理 CRUD
│   ├── notes/              # Markdown 笔记（编辑、图片上传、导出）
│   ├── weread/             # 微信读书 API 集成（书架/划线/统计同步）
│   ├── thinker/            # AI 哲学家对话
│   ├── ai_reader/          # AI 阅读助手（摘要/书评/分析/推荐/对话）
│   ├── static/             # CSS/JS 静态资源
│   ├── templates/          # Jinja2 模板
│   └── uploads/            # 笔记图片上传
└── migrations/             # 数据库迁移文件
```

## 快速开始

### 前置要求

- Python 3.10+
- MySQL 8.0
- 微信读书 API Key
- DeepSeek API Key（[平台注册](https://platform.deepseek.com)）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/abdes6/book.git
cd book

# 2. 创建虚拟环境
python -m venv venv
# Windows: venv\Scripts\activate
# Linux:   source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 创建 .env 配置文件
# 参考 .env.example 填写以下变量：
#   SECRET_KEY=<随机字符串>
#   DATABASE_URL=mysql+pymysql://root:密码@localhost:3306/book_collection
#   DEEPSEEK_API_KEY=<你的 DeepSeek API Key>
#   WEREAD_API_KEY=<你的微信读书 API Key>

# 5. 创建数据库
mysql -u root -p -e "CREATE DATABASE book_collection DEFAULT CHARACTER SET utf8mb4"

# 6. 初始化数据库
flask init-db

# 7. 运行
python run.py

# 8. 访问 http://localhost:5000
#    默认管理员：admin / admin123（首次启动后请修改密码）
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `flask init-db` | 初始化数据库（管理员账号 + 19 个微信读书分类） |
| `flask import-weread --user-id 1` | 从微信读书导入书架 |
| `flask import-highlights` | 批量导入全部用户的划线笔记 |
| `flask sync-stats` | 同步所有用户的阅读统计数据 |
| `flask sync-stats --force` | 强制全量重新同步 |
| `flask init-weread-categories` | 添加微信读书预设分类 |
| `flask update-categories --user-id 1` | 从 API 更新图书分类 |

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `SECRET_KEY` | ✅ | Flask 会话签名密钥 |
| `DATABASE_URL` | ✅ | MySQL 连接字符串 |
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek AI API 密钥 |
| `WEREAD_API_KEY` | 可选 | 微信读书 API 密钥（默认值） |
| `FLASK_DEBUG` | 可选 | 设为 `1` 启用调试模式 |
| `ADMIN_DEFAULT_PASSWORD` | 可选 | init-db 时默认管理员密码 |

## API 路由

| 路由 | 说明 |
|------|------|
| `/` | 首页（最近阅读 10 本） |
| `/books` | 书架列表（分类/状态/关键词筛选） |
| `/books/<id>` | 书籍详情（划线笔记、笔记） |
| `/highlights/search` | 全局划线搜索 |
| `/stats` | 阅读统计仪表盘 |

## 许可证

MIT
