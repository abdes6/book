# 个人藏书管理系统 实现计划

**目标：** 基于 Flask + MySQL + Bootstrap 实现个人藏书管理系统，集成微信读书 API

**技术栈：** Flask 3.x + SQLAlchemy + MySQL + Bootstrap 5 + Flask-Login + Flask-WTF + requests

## 文件结构

```
实训/
├── run.py                      # 入口
├── config.py                   # 配置
├── requirements.txt            # 依赖
├── app/
│   ├── __init__.py             # app factory
│   ├── extensions.py           # db, login_manager, migrate
│   ├── models.py               # Category, Book, Admin
│   ├── forms.py                # LoginForm, BookForm, CategoryForm
│   ├── cli.py                  # init-db 命令
│   ├── main/__init__.py + routes.py       # 前台路由
│   ├── admin/__init__.py + routes.py + captcha.py  # 后台
│   ├── weread/__init__.py + routes.py + api.py     # 微信读书
│   ├── templates/              # 所有模板
│   └── static/                 # 静态文件
└── docs/superpowers/specs/     # 设计文档
```

## 已验证功能

- [x] Flask app factory 启动正常
- [x] MySQL 数据库迁移成功 (categories, books, admins)
- [x] 种子数据：admin/admin123 + 8个默认分类
- [x] 前台路由: /, /books, /books/<id> → 200
- [x] 后台路由: /admin/login, /admin/ → 200
- [x] 微信读书: /weread/search → 200
- [x] 404 错误页面 → 404
- [x] 验证码生成 + 管理员登录
- [x] 后台 CRUD（图书/分类/读后感）

## 启动方式

```bash
cd D:\Course\Web开发技术\实训
set FLASK_APP=run.py
flask init-db           # 首次初始化
python run.py           # 启动开发服务器
```

## 微信读书 API

设置环境变量后即可启用:
```bash
$env:WEREAD_API_KEY="wrk-xxxxxxxx"
```
