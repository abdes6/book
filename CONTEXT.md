# 个人藏书管理系统 — 上下文摘要

## 目标
基于 Flask + MySQL + 微信读书 API 的个人藏书管理系统，支持书架同步、划线笔记导入、阅读统计和前端用户认证。

## 技术栈
- Python 3.x + Flask 3.x + SQLAlchemy + MySQL + Flask-Migrate
- Bootstrap 5 (CDN) + 自定义 CSS 设计系统
- Flask-Login + Flask-WTF + CSRF 保护
- 虚拟环境：`C:\Users\admin\my_env\Scripts\python.exe`
- Git 仓库：`https://github.com/abdes6/book.git`

## 项目结构
```
D:\Course\Web开发技术\实训\
├── app/
│   ├── __init__.py          # 应用工厂, Jinja2 过滤器(fmt_seconds, fmt_compare), 蓝图注册
│   ├── models.py            # Book, Category, Highlight, Admin, User
│   ├── forms.py             # UserLoginForm, RegisterForm
│   ├── cli.py               # 命令行工具(init-db, import-weread, import-highlights 等)
│   ├── extensions.py        # db, login_manager, migrate, csrf 初始化
│   ├── static/
│   │   └── css/custom.css   # 设计系统(210行): 暖白色板+Playfair Display+Inter+卡片动效
│   ├── main/
│   │   ├── __init__.py
│   │   └── routes.py        # 首页(/), 藏书列表(/books), 详情(/books/<id>), 划线JSON, 统计(/stats)
│   ├── auth/
│   │   ├── __init__.py
│   │   └── routes.py        # 登录(/auth/login), 注册(/auth/register), 退出
│   ├── admin/
│   │   └── routes.py        # 后台管理(admin/login, dashboard, CRUD)
│   └── weread/
│       ├── __init__.py
│       ├── api.py           # get_shelf(), get_bookmarklist(), get_readdata()
│       └── importer.py      # import_shelf_to_db(), import_highlights_for_book()
├── templates/
│   ├── base.html            # 白底导航栏+Google Fonts+自定义CSS
│   ├── index.html           # Hero区+最近阅读(微信读书前10)
│   ├── stats.html           # 四维度概览卡+阅读排行+偏好分析+周期对比
│   ├── books/
│   │   ├── list.html        # 分类/状态筛选+网格展示(4列)
│   │   └── detail.html      # 封面+信息+划线笔记(按章分组, 色标)
│   ├── auth/
│   │   ├── login.html       # 居中卡片式登录
│   │   └── register.html    # 居中卡片式注册
│   └── admin/
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── books.html, book_form.html
│       ├── categories.html
│       └── notes.html
├── migrations/versions/     # Flask-Migrate 迁移文件
├── skills/frontend-design/  # skillhub 安装的前端设计 skill(已 gitignore)
├── CONTEXT.md               # 本文件
├── config.py                # 配置
├── run.py                   # 入口
├── start.ps1                # 启动脚本(设环境变量+关代理)
├── requirements.txt
└── .gitignore
```

## Git 提交历史
```
30801d2 feat: 阅读统计页面 + 前端界面整体美化(Book-Theme-DS) + 用户登录注册 + last_viewed_at
195fc37 feat: 微信读书划线导入 + 状态模型简化 + JS/后端错误修复
f5b1d02 feat: 微信读书分类替换手动分类
cc602b1 feat: 个人藏书管理系统 - Flask + MySQL + 微信读书集成
```

## 数据库
- MySQL: `root/Aa123456@localhost:3306/book_collection`
- 5 张表: `category`, `book`, `admin`, `highlight`, `user`
- 种子数据: admin/admin123, 19 个微信读书分类, 786 本书

## 关键设计决策
| 决策 | 说明 |
|------|------|
| 前端用户ID前缀 | `User.get_id()` 返回 `u_{id}`, `load_user()` 按前缀区分 User 和 Admin |
| 首页数据源 | WeRead API `/shelf/sync` 按 `readUpdateTime` 排序，非本地 DB |
| 划线笔记 | 首次访问详情页时按需导入并缓存，`weread_bookmark_id` 去重 |
| 阅读统计 | 直接调 WeRead API `/readdata/detail` 4 种模式，不做本地缓存 |
| 代理 | API 调用禁用系统代理 `proxies={'http':'','https':''}`, timeouot=5s |
| 前端设计 | 暖白书卷风: `#F7F3ED` 底 + `#2C3E50` 墨色字 + `#C0392B` 红褐点缀 |
| 字体 | Playfair Display(标题) + Inter(正文), 避免 Bootstrap 默认感 |

## 微信读书 API
- `WEREAD_API_KEY=wrk-Ima2_MxuSCKzqbZRepR6ZAAA`
- 使用的接口: `/shelf/sync`, `/book/bookmarklist`, `/readdata/detail`, `/user/notebooks`
- 786 本书, 490 本有笔记, 6110 条笔记

## 启动方式
```powershell
.\start.ps1
```
