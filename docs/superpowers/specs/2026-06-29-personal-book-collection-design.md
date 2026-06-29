# 个人藏书管理系统 — 设计与需求分析文档

## 1. 项目概述

**项目名称**：个人藏书管理系统  
**课程**：Web综合开发实训  
**学校**：浙江树人大学 · 信息科技学院 · 数字媒体技术 2023级  
**技术栈**：Python Flask + SQLAlchemy + MySQL + Bootstrap 5 + Flask-WTF + Flask-Login + Flask-Migrate  
**外部集成**：微信读书 API（搜索书库、导入书籍、热门推荐）

## 2. 系统架构

```
个人藏书管理系统（Flask）
├── 前台（面向用户）
│   ├── 首页 —— 热门推荐、搜索入口
│   ├── 书籍浏览 —— 按分类/状态筛选
│   ├── 书籍详情 —— 信息、评分、读后感
│   ├── 微信读书搜索 —— 搜索书库并查看详情
│   └── 微信读书导入 —— 一键导入到个人收藏
│
├── 后台（管理员）
│   ├── 管理员登录（验证码 + 装饰器）
│   ├── 图书管理（增删改查）
│   ├── 分类管理
│   ├── 读后感管理
│   └── 数据统计
│
└── 微信读书 API 集成层
    ├── 搜索书籍 /store/search
    ├── 书籍详情 /book/info
    └── 推荐好书 /store/recommend
```

## 3. 前台功能模块

| 模块 | 功能点 |
|------|--------|
| 首页 | 轮播推荐、最近添加、热门书籍、搜索栏 |
| 书籍浏览 | 全部书籍列表、按分类筛选、按状态筛选（想读/在读/已读）、搜索书名/作者 |
| 书籍详情 | 封面、书名、作者、ISBN、简介、分类、评分、阅读状态切换、写读后感 |
| 微信读书搜索 | 输入关键词搜索微信读书书库、展示结果、点击查看详情 |
| 微信读书导入 | 从搜索结果中一键导入到个人收藏 |

## 4. 后台功能模块

| 模块 | 功能点 |
|------|--------|
| 管理员登录 | 表单验证、验证码、登录装饰器 |
| 图书管理 | 书籍列表、新增/编辑/删除书籍 |
| 分类管理 | 增删改分类（文学、科幻、历史、技术等） |
| 读后感管理 | 查看所有读后感、审核/删除 |
| 数据统计 | 书籍总数、各分类数量、阅读状态分布 |

## 5. 数据库设计

### categories 分类表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT (PK) | 主键，自增 |
| name | VARCHAR(50) | 分类名称（唯一） |

### books 书籍表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT (PK) | 主键，自增 |
| title | VARCHAR(200) | 书名 |
| author | VARCHAR(100) | 作者 |
| isbn | VARCHAR(20) | ISBN，唯一 |
| cover_url | VARCHAR(500) | 封面图片URL |
| summary | TEXT | 简介 |
| rating | DECIMAL(2,1) | 个人评分（0.0-5.0） |
| status | ENUM('want','reading','done') | 阅读状态 |
| notes | TEXT | 读后感 |
| category_id | INT (FK) | 外键，关联 categories.id |
| imported | BOOLEAN | 是否从微信读书导入 |
| weread_book_id | VARCHAR(50) | 微信读书ID |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### admins 管理员表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT (PK) | 主键，自增 |
| username | VARCHAR(50) | 用户名（唯一） |
| password_hash | VARCHAR(200) | 密码（哈希） |
| created_at | DATETIME | 创建时间 |

## 6. 页面路由

### 前台路由
| 路由 | 方法 | 页面 | 说明 |
|------|------|------|------|
| `/` | GET | 首页 | 推荐、最近添加 |
| `/books` | GET | 书籍列表 | 筛选、分页 |
| `/books/<int:id>` | GET | 书籍详情 | 完整信息 |
| `/books/search` | GET | 搜索结果 | 本地搜索 |
| `/weread/search` | GET/POST | 微信读书搜索 | 搜索书库 |
| `/weread/import/<book_id>` | POST | 导入 | 导入到收藏 |

### 后台路由
| 路由 | 方法 | 页面 |
|------|------|------|
| `/admin/login` | GET/POST | 管理员登录 |
| `/admin/logout` | GET | 登出 |
| `/admin` | GET | 后台首页/统计 |
| `/admin/books` | GET | 图书管理列表 |
| `/admin/books/create` | GET/POST | 新增书籍 |
| `/admin/books/<int:id>/edit` | GET/POST | 编辑书籍 |
| `/admin/books/<int:id>/delete` | POST | 删除书籍 |
| `/admin/categories` | GET/POST | 分类管理 |
| `/admin/notes` | GET | 读后感管理 |

## 7. 技术选型

| 层面 | 技术 |
|------|------|
| 后端框架 | Flask + Blueprints（蓝图） |
| ORM | Flask-SQLAlchemy |
| 数据库迁移 | Flask-Migrate |
| 数据库 | MySQL |
| 前端 UI | Bootstrap 5 |
| 模板引擎 | Jinja2 |
| 表单验证 | Flask-WTF + CAPTCHA |
| 登录认证 | Flask-Login + @login_required 装饰器 |
| API 集成 | requests 库 |

## 8. 页面结构

### 前台
| 页面 | 布局 |
|------|------|
| 首页 | 顶部导航（Logo + 搜索栏 + 分类导航）、轮播推荐Banner、最近添加卡片（4列网格）、热门排行 |
| 书籍列表 | 左侧筛选栏（分类+阅读状态）、右侧卡片网格、分页 |
| 书籍详情 | 左封面大图、右信息区（书名/作者/ISBN/分类/简介/评分/状态切换/读后感） |
| 微信读书搜索 | 搜索框 + 结果列表（封面缩略图+书名+作者+评分+导入按钮） |

### 后台
| 页面 | 布局 |
|------|------|
| 登录页 | 居中表单 + 验证码 |
| 后台首页 | 统计信息卡片 |
| 图书管理 | 表格列表 + 顶部新增按钮 |
| 新增/编辑 | 表单（书名/作者/ISBN/分类/封面URL/简介/评分/状态/读后感） |
| 分类管理 | 列表 + 内联增删改 |
| 读后感管理 | 表格列表（书籍名/摘要/时间/操作） |

## 9. 微信读书API集成

- API 地址：`https://i.weread.qq.com/api/agent/gateway`
- 鉴权：`Authorization: Bearer $WEREAD_API_KEY`
- 使用接口：
  - `/store/search` — 搜索书籍
  - `/book/info` — 获取书籍详情
  - `/store/recommend` — 热门推荐
- 请求体需携带 `skill_version: "1.0.3"`
- 导入流程：搜索 → 选择 → 调用详情接口 → 存入本地数据库
