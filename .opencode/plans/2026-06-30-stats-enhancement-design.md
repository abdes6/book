# 阅读统计增强 — 设计文档

## 概述

在现有阅读统计页面上，新增图表可视化、年度阅读日历、阅读目标追踪、习惯洞察四大功能，并引入数据持久化层以支持历史趋势分析和秒级加载。

## 技术选型

| 层面 | 选型 | 理由 |
|------|------|------|
| 图表库 | Chart.js 4.x (CDN) | 轻量(60KB)，Bootstrap 项目惯例，支持柱状/饼图/折线/雷达图 |
| 日历热力图 | 纯 CSS Grid + 自研 | 不引入额外依赖，GitHub 风格 |
| 数据持久化 | MySQL 新表 (ReadStat + DailyReadStat) | 按需同步，避免每次调用 WeRead API |
| 同步策略 | 访问 `/stats` 时按需触发 | 首次全量同步历史年份，后续增量补当天 |

## 架构图

```
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│  WeRead API  │ ──→  │  SyncService  │ ──→  │  MySQL 本地   │
│  /readdata/  │      │  stats_sync  │      │  read_stat   │
│  detail      │      │  .py         │      │  daily_read  │
└─────────────┘      └──────┬───────┘      │  _stat       │
                            │              └──────┬───────┘
                            │                     │
                     ┌──────┴───────┐      ┌──────┴───────┐
                     │  CLI 命令     │      │  /stats 路由  │
                     │  sync-stats  │      │  读取本地数据  │
                     └──────────────┘      └──────┬───────┘
                                                  │
                                          ┌──────┴───────┐
                                          │  stats.html   │
                                          │  stats.js     │
                                          │  (Chart.js)   │
                                          └──────────────┘
```

## Phase 1: 数据持久化基础设施

### 新增模型

#### `ReadStat` — 周期聚合统计

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | - |
| user_id | FK → user.id | 关联用户 |
| mode | String(20) | `weekly`/`monthly`/`annually`/`overall` |
| period_start | DateTime | 周期起始(周一/月初/年初) |
| period_end | DateTime | 周期结束 |
| total_read_time | Integer | 总阅读时长(秒) |
| read_days | Integer | 有效阅读天数 |
| day_avg_read_time | Integer | 自然日均时长(秒) |
| compare | Float, nullable | 与上期对比比例 |
| read_longest | JSON | 读书排行 top 10 |
| read_stat | JSON | 阅读统计摘要(读过/读完/笔记等) |
| prefer_category | JSON | 偏好分类数组 |
| prefer_time_word | String(100) | 偏好时段文案 |
| prefer_author | JSON | 偏好作者数组 |
| prefer_time | JSON | 24h 时段分布数组 |
| read_rate | Float, nullable | 文字阅读占比% |
| wr_read_time | Integer, nullable | 文字阅读时长(秒) |
| wr_listen_time | Integer, nullable | 听书时长(秒) |
| raw_data | JSON | API 原始回包(备用) |
| synced_at | DateTime | 同步时间戳 |
| UniqueConstraint | (user_id, mode, period_start) | 避免重复 |

#### `DailyReadStat` — 每日阅读时长

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | - |
| user_id | FK → user.id | 关联用户 |
| date | Date | 日期(唯一 per user) |
| total_read_time | Integer | 当日阅读总时长(秒) |
| synced_at | DateTime | 同步时间戳 |
| UniqueConstraint | (user_id, date) | 避免重复 |

### 同步服务 (`app/weread/stats_sync.py`)

```
sync_all_stats(user_id):
  1. 从 ReadStat 查出最近同步时间
  2. 若从未同步或同步时间 > 1天:
     a. 调 get_readdata('overall') → 获取 registTime + 总览数据
     b. 从 registTime 推算应同步的年份范围
     c. 逐年调 get_readdata('annually', baseTime=...)
        → 解析 dailyReadTimes → 写入 DailyReadStat
        → 解析 aggregate 字段 → 写入 ReadStat(mode='annually')
     d. 调 get_readdata('weekly'/'monthly') → 写入 ReadStat
        → 解析 readTimes(日均分桶) → 补充 DailyReadStat
  3. 更新 ReadStat.synced_at

get_read_stat(user_id, mode, period_start):
  - 从 DB 查询缓存，若在有效期内直接返回
  - 否则触发异步同步(首次进入页面时)
```

### CLI 命令

```
flask sync-stats          # 手动触发同步
flask sync-stats --force  # 强制全量重新同步
```

### 同步范围控制

- 通过 `overall.registTime` 获取用户注册时间，不查询注册前的数据
- 已同步过的年份不再重复拉取（除非 `--force`）
- 当天数据只查询一次

## Phase 2: 图表可视化 + 阅读日历

### 页面布局

```
┌──────────────────────────────────────────────────────┐
│ [周卡片] [月卡片] [年卡片] [总卡片] (保留现有, 数据改本地)│
├──────────────────────────────────────────────────────┤
│ 📊 阅读趋势图 (Chart.js 柱状+折线混合)                  │
│ X轴: 近30天日期, Y轴: 阅读时长(分钟)                    │
│ 柱状=每日阅读, 折线=7日移动平均                         │
├───────────────────┬──────────────────────────────────┤
│ 🥧 分类分布饼图     │ 📈 月度阅读趋势(近12月柱状图)       │
│ preferCategory     │ ReadStat.monthly 聚合             │
├───────────────────┴──────────────────────────────────┤
│ 🌡️ 年度阅读日历                                       │
│ 7行 × ~53列 Grid, 每格=1天, 色阶: 0→浅灰→深蓝→深绿    │
│ 点击格子弹出当日详情(读书排行)                          │
├──────────────────────────────────────────────────────┤
│ 🕐 阅读时段分布 (Chart.js 雷达图)                      │
│ 24h, 从早6点起, preferTime 数据                        │
├──────────────────────────────────────────────────────┤
│ 阅读排行 + 偏好分析 (保留现有样式)                      │
└──────────────────────────────────────────────────────┘
```

### JavaScript 组织

- 新建 `app/static/js/stats.js` — 单文件管理所有图表
- DOMContentLoaded 时读取隐藏的 JSON 数据容器，初始化各 chart
- Chart.js CDN: `https://cdn.jsdelivr.net/npm/chart.js@4`

### 热力图实现

```
年度日历: 7行(周一到周日) × 最多53列(一年周数)
- 每个格子 = 一个 <div>, 宽高 ~14px, gap: 3px
- CSS Grid: grid-template-rows: repeat(7, 14px)
- 颜色映射: 0 → #ebedf0 | 1-30min → #9be9a8 | 30-60min → #40c463 | 1-2h → #30a14e | >2h → #216e39
- 点击 → fetch `/stats/daily/<date>` → 弹出 modal 显示当日 top 书
- 工具提示: hover 显示日期和阅读时长
```

### 数据传递

Flask 路由在渲染 `stats.html` 时将图表数据序列化为 JSON，写入隐藏 `<script id="stats-data" type="application/json">`，JS 读取后初始化图表。

## Phase 3: 阅读目标追踪 + 习惯洞察

### 新增模型

#### `ReadGoal`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | - |
| user_id | FK → user.id | 关联用户 |
| year | Integer | 目标年份 |
| month | Integer, nullable | 目标月份(空=年度目标) |
| target_read_time | Integer | 目标阅读时长(秒) |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |
| UniqueConstraint | (user_id, year, month) | 每人每年/月一个目标 |

### 目标追踪 UI

```
┌───────────────┬───────────────┬───────────────┐
│ 🎯 年度目标     │ 📅 本月目标     │ 🔥 阅读连续   │
│ target: 500h   │ target: 50h    │ 当前: 15 天   │
│ current: 365h  │ current: 42h   │ 最长: 32 天   │
│ ████████░░ 73% │ ████████░░ 84%│ 更新于 今天   │
│ [编辑目标]     │ [编辑目标]     │               │
├───────────────┴───────────────┴───────────────┤
```

- 目标编辑: 点击 → 弹内联编辑框 → PUT 到 `/stats/goal/edit`
- 目标数据存在本地，不涉及 WeRead
- 自动从 `DailyReadStat` 累加当年/当月阅读时长

### 习惯洞察

| 洞察项 | 计算 SQL/逻辑 |
|--------|-------------|
| 🔥 当前连续阅读天数 | `SELECT date FROM daily_read_stat WHERE total_read_time>0 ORDER BY date DESC` → 倒推连续天数 |
| 🏆 最长连续阅读记录 | 扫描全部数据，找最大连续非零区间 |
| 📅 最活跃星期 | `SELECT DAYOFWEEK(date), AVG(total_read_time) ... GROUP BY DAYOFWEEK(date)` |
| 📚 读过/读完 | `ReadStat.readStat` 中提取 |
| 🎧 文字 vs 听书 | `readRate` + `wr_read_time / wr_listen_time` |
| ⏰ 偏好时段 | `preferTimeWord` + 雷达图 |

## 数据流 — 完整链路

```
用户访问 /stats
  → route 调用 get_local_stats(user_id)
    → 检查 ReadStat 最新同步时间
    → 若需同步: sync_all_stats(user_id)
      → get_readdata('overall') → 取 registTime
      → get_readdata('annually', baseTime=各年) → 取每日明细
      → get_readdata('weekly') → 取本周数据 (readTimes 日分桶)
      → get_readdata('monthly') → 取本月数据
      → 逐条写入 ReadStat + DailyReadStat
    → 从 DB 读取统计数据
    → 计算 streak / 活跃星期 / 目标进度
    → 序列化图表数据为 JSON
  → render_template('stats.html', ...)
  → stats.js 读取 JSON → 初始化 Chart.js 图表 + 热力图
```

## 边界 / 异常处理

| 场景 | 处理方式 |
|------|---------|
| WeRead API 超时/报错 | 使用本地缓存数据降级，页面提示"部分数据更新失败" |
| 首次同步大量历史年份 | 同步时在图标区域显示加载动画，完成后自动刷新 |
| 某年 API 无 `dailyReadTimes` | 该年跳过日级同步，仅存年度聚合数据 |
| 用户未设置目标 | 目标卡片显示"设置目标"按钮，不报错 |
| 数据库唯一约束冲突 | `session.merge()` 替代 `session.add()` |
| 极速操作(频繁 F5) | 同步任务加锁(文件锁或 DB 乐观锁)，防止并发 |

## 文件变更清单

### 新增文件
| 文件 | 用途 |
|------|------|
| `app/weread/stats_sync.py` | 同步服务 |
| `app/static/js/stats.js` | 图表初始化 + 热力图渲染 |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `app/models.py` | 新增 ReadStat, DailyReadStat, ReadGoal 模型 |
| `app/main/routes.py` | 重写 `/stats` 路由，新增 `/stats/goal/edit`, `/stats/daily/<date>` |
| `app/templates/stats.html` | 重写布局，嵌入图表容器 + 热力图 + 目标卡片 |
| `app/extensions.py` | 注册同步锁（如需） |
| `app/cli.py` | 新增 `sync-stats` 命令 |
| `app/__init__.py` | 无（蓝图已注册） |

### 数据库
- 创建 `flask db migrate -m "add read_stat, daily_read_stat, read_goal"`
- 执行 `flask db upgrade`

## 实施顺序

1. Phase 1: 模型 + 迁移 + 同步服务 + CLI + 路由改造
2. Phase 2: Chart.js 集成 + 热力图 + stats.js + 模板改造
3. Phase 3: ReadGoal 模型 + 目标卡片 + 习惯洞察计算
