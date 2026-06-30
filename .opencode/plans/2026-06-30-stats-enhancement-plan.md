# 阅读统计增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为现有个人藏书管理系统添加图表可视化、阅读日历、阅读目标追踪与习惯洞察，并引入数据持久化层。

**Architecture:** Chart.js 4.x (CDN) + 纯 CSS Grid 热力图 + MySQL 3张新表 (ReadStat, DailyReadStat, ReadGoal)。首次访问 `/stats` 时按需从 WeRead API 同步历史数据到本地，后续秒级加载。

**Tech Stack:** Flask 3.x, SQLAlchemy, MySQL, Chart.js 4.x (CDN), Bootstrap 5

## Global Constraints

- 所有 Python 字符串使用双引号
- 数据库使用 MySQL `root/Aa123456@localhost:3306/book_collection`
- 虚拟环境: `C:\Users\admin\my_env\Scripts\python.exe`
- 前端用户ID前缀 `u_{id}` 模式，`frontend_login_required` 在 `app/extensions.py`
- WeRead API 调用禁用系统代理 `proxies={'http':'','https':''}`, timeout=5s
- API response 用 `.get()` 访问字段避免 KeyError

---

### Task 1: 新增 ReadStat + DailyReadStat 模型

**Files:**
- Modify: `app/models.py`（在文件末尾增加模型类）

**Interfaces:**
- Consumes: 无
- Produces: `ReadStat`, `DailyReadStat` ORM 类（供 Task 3 同步服务使用）
- Produces: `read_stats` / `daily_read_stats` backrefs on User model

**Steps:**

- [ ] **Step 1: Add ReadStat model**

在 `app/models.py` 末尾添加：

```python
class ReadStat(db.Model):
    __tablename__ = "read_stat"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    mode = Column(String(20), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    total_read_time = Column(Integer, default=0)
    read_days = Column(Integer, default=0)
    day_avg_read_time = Column(Integer, default=0)
    compare = Column(Float, nullable=True)
    read_longest = Column(JSON, nullable=True)
    read_stat = Column(JSON, nullable=True)
    prefer_category = Column(JSON, nullable=True)
    prefer_time_word = Column(String(100), nullable=True)
    prefer_author = Column(JSON, nullable=True)
    prefer_time = Column(JSON, nullable=True)
    read_rate = Column(Float, nullable=True)
    wr_read_time = Column(Integer, nullable=True)
    wr_listen_time = Column(Integer, nullable=True)
    raw_data = Column(JSON, nullable=True)
    synced_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "mode", "period_start"),)
    user = relationship("User", backref="read_stats")
```

- [ ] **Step 2: Add DailyReadStat model**

```python
class DailyReadStat(db.Model):
    __tablename__ = "daily_read_stat"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    date = Column(Date, nullable=False)
    total_read_time = Column(Integer, default=0)
    synced_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "date"),)
    user = relationship("User", backref="daily_read_stats")
```

- [ ] **Step 3: 添加导入**

确保文件顶部已有 `from datetime import datetime`，若无则在文件顶部添加 `from datetime import datetime, date`。

- [ ] **Step 4: 创建迁移并升级**

```bash
C:\Users\admin\my_env\Scripts\python.exe run.py db migrate -m "add read_stat and daily_read_stat"
C:\Users\admin\my_env\Scripts\python.exe run.py db upgrade
```

- [ ] **Step 5: Commit**

```bash
git add app/models.py migrations/versions/
git commit -m "feat: add ReadStat and DailyReadStat models for stats persistence"
```

---

### Task 2: 同期服务 app/weread/stats_sync.py

**Files:**
- Create: `app/weread/stats_sync.py`
- Modify: 无

**Interfaces:**
- Consumes: `get_readdata(mode, base_time)` from `app/weread/api.py`
- Consumes: `ReadStat`, `DailyReadStat` from `app/models.py`
- Produces: `sync_all_stats(user_id)` — 供 Task 4 路由调用

**Steps:**

- [ ] **Step 1: Create stats_sync.py**

```python
import logging
from datetime import datetime, date, timedelta
from app import db
from app.models import ReadStat, DailyReadStat
from app.weread.api import get_readdata

logger = logging.getLogger(__name__)


def sync_all_stats(user_id):
    latest = ReadStat.query.filter_by(user_id=user_id).order_by(ReadStat.synced_at.desc()).first()
    if latest and latest.synced_at and latest.synced_at.date() == date.today():
        return

    overall = get_readdata("overall")
    if not overall or not overall.get("totalReadTime"):
        logger.warning("WeRead API overall failed")
        return

    _save_read_stat(user_id, "overall", overall)

    regist_time = overall.get("registTime", 0)
    regist_year = datetime.fromtimestamp(regist_time).year if regist_time else 2020
    current_year = datetime.utcnow().year

    for year in range(regist_year, current_year + 1):
        existing = ReadStat.query.filter_by(
            user_id=user_id, mode="annually",
            period_start=datetime(year, 1, 1)
        ).first()
        if existing:
            continue
        ts = int(datetime(year, 7, 1).timestamp())
        data = get_readdata("annually", base_time=ts)
        if data and data.get("totalReadTime") is not None:
            _save_read_stat(user_id, "annually", data, period_start=datetime(year, 1, 1))
            daily = data.get("dailyReadTimes") or {}
            _save_daily_read_times(user_id, daily)

    weekly = get_readdata("weekly")
    if weekly:
        _save_read_stat(user_id, "weekly", weekly)

    monthly = get_readdata("monthly")
    if monthly:
        _save_read_stat(user_id, "monthly", monthly)

    today_daily = DailyReadStat.query.filter_by(user_id=user_id, date=date.today()).first()
    if today_daily:
        today_daily.synced_at = datetime.utcnow()
        db.session.commit()


def _parse_period(mode, base_time=0):
    now = datetime.utcnow()
    if mode == "weekly":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=7)
    elif mode == "monthly":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end = now.replace(year=now.year + 1, month=1, day=1)
        else:
            end = now.replace(month=now.month + 1, day=1)
        return start, end
    elif mode == "annually":
        if base_time:
            y = datetime.fromtimestamp(base_time).year
        else:
            y = now.year
        return datetime(y, 1, 1), datetime(y + 1, 1, 1)
    elif mode == "overall":
        return datetime(2000, 1, 1), datetime(2100, 1, 1)
    return now, now


def _save_read_stat(user_id, mode, data, period_start=None):
    ps, pe = _parse_period(mode)
    if period_start:
        ps = period_start
    read_stat = ReadStat(
        user_id=user_id,
        mode=mode,
        period_start=ps,
        period_end=pe,
        total_read_time=data.get("totalReadTime", 0),
        read_days=data.get("readDays", 0),
        day_avg_read_time=data.get("dayAverageReadTime", 0),
        compare=data.get("compare"),
        read_longest=data.get("readLongest"),
        read_stat=data.get("readStat"),
        prefer_category=data.get("preferCategory"),
        prefer_time_word=data.get("preferTimeWord"),
        prefer_author=data.get("preferAuthor"),
        prefer_time=data.get("preferTime"),
        read_rate=data.get("readRate"),
        wr_read_time=data.get("wrReadTime"),
        wr_listen_time=data.get("wrListenTime"),
        raw_data=data,
        synced_at=datetime.utcnow()
    )
    db.session.merge(read_stat)
    db.session.commit()


def _save_daily_read_times(user_id, daily_dict):
    for ts_str, seconds in daily_dict.items():
        try:
            day = datetime.fromtimestamp(int(ts_str)).date()
        except (ValueError, OSError):
            continue
        existing = DailyReadStat.query.filter_by(user_id=user_id, date=day).first()
        if existing:
            existing.total_read_time = int(seconds)
            existing.synced_at = datetime.utcnow()
        else:
            stat = DailyReadStat(
                user_id=user_id, date=day,
                total_read_time=int(seconds),
                synced_at=datetime.utcnow()
            )
            db.session.add(stat)
    db.session.commit()
```

- [ ] **Step 2: Commit**

```bash
git add app/weread/stats_sync.py
git commit -m "feat: add WeRead stats sync service"
```

---

### Task 3: CLI 命令 sync-stats

**Files:**
- Modify: `app/cli.py`

**Steps:**

- [ ] **Step 1: Add sync-stats command**

在 `app/cli.py` 末尾添加：

```python
@cli.command("sync-stats")
@click.option("--force", is_flag=True, help="Force full re-sync")
@with_appcontext
def sync_stats(force):
    from app.weread.stats_sync import sync_all_stats
    from app.models import ReadStat, DailyReadStat, User
    if force:
        ReadStat.query.delete()
        DailyReadStat.query.delete()
        db.session.commit()
        click.echo("Cleared cached stats")
    users = User.query.all()
    for user in users:
        sync_all_stats(user.id)
        click.echo(f"Synced stats for user {user.id}")
    click.echo("Done")
```

确保顶部有 `import click`。

- [ ] **Step 2: Commit**

```bash
git add app/cli.py
git commit -m "feat: add sync-stats CLI command"
```

---

### Task 4: 重写 /stats 路由

**Files:**
- Modify: `app/main/routes.py`

**Interfaces:**
- Consumes: `sync_all_stats(user_id)` from Task 2
- Consumes: `ReadStat`, `DailyReadStat` from models
- Produces: template context for `stats.html`

**Steps:**

- [ ] **Step 1: 读取当前 stats 路由**

`app/main/routes.py` 中 `/stats` 路由 (~line 35-55)。

- [ ] **Step 2: 重写路由**

```python
from datetime import datetime, date, timedelta
from app.weread.stats_sync import sync_all_stats
from app.models import ReadStat, DailyReadStat
from sqlalchemy import func

@bp.route("/stats")
@frontend_login_required
def stats():
    user_id = int(current_user.id.replace("u_", ""))
    sync_all_stats(user_id)

    weekly_raw = ReadStat.query.filter_by(user_id=user_id, mode="weekly").order_by(ReadStat.period_start.desc()).first()
    monthly_raw = ReadStat.query.filter_by(user_id=user_id, mode="monthly").order_by(ReadStat.period_start.desc()).first()
    annually_raw = ReadStat.query.filter_by(user_id=user_id, mode="annually", period_start=datetime(datetime.utcnow().year, 1, 1)).first()
    overall_raw = ReadStat.query.filter_by(user_id=user_id, mode="overall").first()

    def fmt_stat(s):
        return s and {
            "totalReadTime": s.total_read_time,
            "readDays": s.read_days,
            "dayAverageReadTime": s.day_avg_read_time,
            "compare": s.compare,
            "readLongest": s.read_longest,
            "readStat": s.read_stat,
            "preferCategory": s.prefer_category,
            "preferTimeWord": s.prefer_time_word,
            "preferAuthor": s.prefer_author,
        } or None

    weekly = fmt_stat(weekly_raw)
    monthly = fmt_stat(monthly_raw)
    annually = fmt_stat(annually_raw)
    overall = fmt_stat(overall_raw)

    # 近30天阅读数据
    days_30 = []
    for i in range(29, -1, -1):
        d = date.today() - timedelta(days=i)
        record = DailyReadStat.query.filter_by(user_id=user_id, date=d).first()
        seconds = record.total_read_time if record else 0
        days_30.append({"date": d.isoformat(), "minutes": round(seconds / 60, 1)})

    # 年度阅读日历数据
    year_days = {}
    year_records = DailyReadStat.query.filter(
        DailyReadStat.user_id == user_id,
        func.extract("YEAR", DailyReadStat.date) == datetime.utcnow().year
    ).all()
    for r in year_records:
        year_days[r.date.isoformat()] = r.total_read_time

    # 近12月月度阅读
    months_12 = []
    for i in range(11, -1, -1):
        m = datetime.utcnow().month - i
        y = datetime.utcnow().year
        if m <= 0:
            m += 12
            y -= 1
        ps = datetime(y, m, 1)
        record = ReadStat.query.filter_by(user_id=user_id, mode="monthly", period_start=ps).first()
        seconds = record.total_read_time if record else 0
        months_12.append({"month": f"{y}-{m:02d}", "minutes": round(seconds / 60, 1)})

    # 分类分布
    categories = []
    if overall and overall.get("preferCategory"):
        categories = overall["preferCategory"]

    # 时段分布
    prefer_time = []
    if overall_raw and overall_raw.prefer_time:
        prefer_time = overall_raw.prefer_time

    chart_data = {
        "dailyTrend": days_30,
        "calendar": year_days,
        "monthlyTrend": months_12,
        "categories": categories,
        "preferTime": prefer_time
    }

    return render_template("stats.html", weekly=weekly, monthly=monthly,
                           annually=annually, overall=overall,
                           chart_data=chart_data)
```

- [ ] **Step 3: Commit**

```bash
git add app/main/routes.py
git commit -m "feat: rewrite /stats route with local DB caching"
```

---

### Task 5: stats.html 模板骨架改造

**Files:**
- Modify: `app/templates/stats.html`

**Steps:**

- [ ] **Step 1: 读取当前 stats.html**

- [ ] **Step 2: 嵌入图表数据 JSON + 图表容器**

在文件顶部（extends/base block 之后）添加：

```html
{% if chart_data %}
<script id="stats-chart-data" type="application/json">{{ chart_data | tojson | safe }}</script>
{% endif %}
```

在现有四卡片下方添加图表区域：

```html
<div class="row mt-4">
  <div class="col-12">
    <div class="card">
      <div class="card-body">
        <h5 class="card-title">📊 阅读趋势</h5>
        <canvas id="dailyTrendChart" height="100"></canvas>
      </div>
    </div>
  </div>
</div>

<div class="row mt-4">
  <div class="col-md-6">
    <div class="card">
      <div class="card-body">
        <h5 class="card-title">🥧 分类分布</h5>
        <canvas id="categoryChart" height="200"></canvas>
      </div>
    </div>
  </div>
  <div class="col-md-6">
    <div class="card">
      <div class="card-body">
        <h5 class="card-title">📈 月度趋势</h5>
        <canvas id="monthlyTrendChart" height="200"></canvas>
      </div>
    </div>
  </div>
</div>

<div class="row mt-4">
  <div class="col-12">
    <div class="card">
      <div class="card-body">
        <h5 class="card-title">🌡️ 年度阅读日历</h5>
        <div id="heatmap-calendar" class="heatmap-container"></div>
      </div>
    </div>
  </div>
</div>

<div class="row mt-4">
  <div class="col-md-6">
    <div class="card">
      <div class="card-body">
        <h5 class="card-title">🕐 阅读时段分布</h5>
        <canvas id="timeRadarChart" height="200"></canvas>
      </div>
    </div>
  </div>
  <div class="col-md-6">
    <div class="card">
      <div class="card-body">
        <h5 class="card-title">🎯 阅读目标</h5>
        <div id="goal-section">
          <p class="text-muted">即将上线</p>
        </div>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: 添加 Chart.js CDN**

在 `base.html` 或 `stats.html` 中（body 末尾）添加：

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="{{ url_for('static', filename='js/stats.js') }}"></script>
```

- [ ] **Step 4: Commit**

```bash
git add app/templates/stats.html app/templates/base.html
git commit -m "feat: add chart containers and Chart.js CDN to stats page"
```

---

### Task 6: stats.js — 图表初始化

**Files:**
- Create: `app/static/js/stats.js`

**Steps:**

- [ ] **Step 1: Create stats.js**

```javascript
document.addEventListener("DOMContentLoaded", function () {
  const el = document.getElementById("stats-chart-data");
  if (!el) return;
  const data = JSON.parse(el.textContent);

  // ── 每日阅读趋势 ──
  const dailyCtx = document.getElementById("dailyTrendChart");
  if (dailyCtx && data.dailyTrend) {
    const labels = data.dailyTrend.map(d => d.date.slice(5));
    const values = data.dailyTrend.map(d => d.minutes);
    const movingAvg = values.map((v, i) => {
      if (i < 6) return null;
      let sum = 0;
      for (let j = i - 6; j <= i; j++) sum += values[j];
      return +(sum / 7).toFixed(1);
    });
    new Chart(dailyCtx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          { label: "每日阅读(分钟)", data: values, backgroundColor: "rgba(192,57,43,0.5)", borderRadius: 3 },
          { label: "7日平均", data: movingAvg, type: "line", borderColor: "#2C3E50", borderWidth: 2, pointRadius: 0, fill: false }
        ]
      },
      options: { responsive: true, plugins: { legend: { position: "top" } } }
    });
  }

  // ── 分类分布饼图 ──
  const catCtx = document.getElementById("categoryChart");
  if (catCtx && data.categories && data.categories.length) {
    const labels = data.categories.map(c => c.categoryTitle || "其他");
    const values = data.categories.map(c => c.readingCount || c.val || 1);
    const colors = ["#C0392B","#E67E22","#F1C40F","#2ECC71","#3498DB","#9B59B6","#1ABC9C","#E91E63"];
    new Chart(catCtx, {
      type: "doughnut",
      data: { labels: labels, datasets: [{ data: values, backgroundColor: colors.slice(0, labels.length) }] },
      options: { responsive: true, plugins: { legend: { position: "right" } } }
    });
  }

  // ── 月度趋势 ──
  const monthCtx = document.getElementById("monthlyTrendChart");
  if (monthCtx && data.monthlyTrend) {
    new Chart(monthCtx, {
      type: "bar",
      data: {
        labels: data.monthlyTrend.map(d => d.month),
        datasets: [{ label: "阅读时长(分钟)", data: data.monthlyTrend.map(d => d.minutes), backgroundColor: "rgba(52,152,219,0.6)", borderRadius: 3 }]
      },
      options: { responsive: true, plugins: { legend: { display: false } } }
    });
  }

  // ── 阅读时段雷达图 ──
  const timeCtx = document.getElementById("timeRadarChart");
  if (timeCtx && data.preferTime && data.preferTime.length) {
    const labels = ["6-8点","8-10点","10-12点","12-14点","14-16点","16-18点","18-20点","20-22点","22-0点","0-2点","2-4点","4-6点"];
    const values = data.preferTime;
    if (values.length === 24) {
      const grouped = [];
      for (let i = 0; i < 24; i += 2) {
        grouped.push(values[i] + (values[i+1] || 0));
      }
      new Chart(timeCtx, {
        type: "radar",
        data: { labels: labels, datasets: [{ label: "阅读时长(秒)", data: grouped, backgroundColor: "rgba(192,57,43,0.2)", borderColor: "#C0392B" }] },
        options: { responsive: true, scales: { r: { beginAtZero: true } } }
      });
    }
  }

  // ── 年度阅读日历热力图 ──
  const heatEl = document.getElementById("heatmap-calendar");
  if (heatEl && data.calendar) {
    const year = new Date().getFullYear();
    const startDate = new Date(year, 0, 1);
    const endDate = new Date(year, 11, 31);
    const startDay = startDate.getDay();

    const table = document.createElement("div");
    table.style.cssText = "display:grid;grid-template-rows:repeat(7,14px);grid-auto-flow:column;gap:3px;overflow-x:auto;padding:8px 0";

    const monthLabels = document.createElement("div");
    monthLabels.style.cssText = "display:flex;gap:3px;margin-bottom:4px;font-size:11px;color:#666";
    const months = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];
    months.forEach(m => { const s = document.createElement("span"); s.textContent = m; s.style.width = "calc(100% / 12)"; monthLabels.appendChild(s); });
    heatEl.appendChild(monthLabels);

    const dayLabels = document.createElement("div");
    dayLabels.style.cssText = "display:grid;grid-template-rows:repeat(7,14px);gap:3px;font-size:10px;color:#999;text-align:right;padding-right:4px";
    ["一","三","五"].forEach(d => { const s = document.createElement("span"); s.textContent = d; dayLabels.appendChild(s); });
    heatEl.appendChild(dayLabels);

    const grid = document.createElement("div");
    grid.style.cssText = "display:grid;grid-template-rows:repeat(7,14px);grid-auto-flow:column;gap:3px";

    const emptyStart = startDay === 0 ? 6 : startDay - 1;
    for (let i = 0; i < emptyStart; i++) {
      const e = document.createElement("div"); e.style.width = "14px"; e.style.height = "14px"; grid.appendChild(e);
    }

    for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
      const iso = d.toISOString().slice(0, 10);
      const secs = data.calendar[iso] || 0;
      const cell = document.createElement("div");
      cell.style.cssText = "width:14px;height:14px;border-radius:2px;cursor:pointer";
      if (secs === 0) cell.style.backgroundColor = "#ebedf0";
      else if (secs < 1800) cell.style.backgroundColor = "#9be9a8";
      else if (secs < 3600) cell.style.backgroundColor = "#40c463";
      else if (secs < 7200) cell.style.backgroundColor = "#30a14e";
      else cell.style.backgroundColor = "#216e39";
      cell.title = `${iso}: ${Math.round(secs / 60)}分钟`;
      cell.addEventListener("click", () => { alert(`📅 ${iso}\n⏱ ${Math.round(secs / 60)}分钟`); });
      grid.appendChild(cell);
    }

    heatEl.appendChild(grid);
  }
});
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/stats.js
git commit -m "feat: add stats.js with Chart.js charts and heatmap calendar"
```

---

### Task 7: 阅读目标模型 + 习惯洞察

**Files:**
- Modify: `app/models.py` (添加 ReadGoal)
- Modify: `app/main/routes.py` (添加目标编辑路由 + 洞察计算)
- Modify: `app/templates/stats.html` (添加目标卡片和洞察，替换占位)
- Modify: `app/static/js/stats.js` (添加目标进度条 UI)

**Steps:**

- [ ] **Step 1: Add ReadGoal model**

在 `app/models.py` 末尾添加：

```python
class ReadGoal(db.Model):
    __tablename__ = "read_goal"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=True)
    target_read_time = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "year", "month"),)
    user = relationship("User", backref="read_goals")
```

- [ ] **Step 2: 迁移**

```bash
C:\Users\admin\my_env\Scripts\python.exe run.py db migrate -m "add read_goal"
C:\Users\admin\my_env\Scripts\python.exe run.py db upgrade
```

- [ ] **Step 3: 添加目标编辑路由**

在 `app/main/routes.py` 中新增：

```python
from app.models import ReadGoal
from flask import request, jsonify

@bp.route("/stats/goal/edit", methods=["POST"])
@frontend_login_required
def edit_goal():
    user_id = int(current_user.id.replace("u_", ""))
    year = request.form.get("year", type=int, default=datetime.utcnow().year)
    month = request.form.get("month", type=int)
    target = request.form.get("target_read_time", type=int, default=0)
    goal = ReadGoal.query.filter_by(user_id=user_id, year=year, month=month).first()
    if goal:
        goal.target_read_time = target
    else:
        goal = ReadGoal(user_id=user_id, year=year, month=month, target_read_time=target)
        db.session.add(goal)
    db.session.commit()
    return jsonify({"ok": True})

@bp.route("/stats/daily/<date_str>")
@frontend_login_required
def daily_detail(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "invalid date"}), 400
    user_id = int(current_user.id.replace("u_", ""))
    record = DailyReadStat.query.filter_by(user_id=user_id, date=d).first()
    return jsonify({
        "date": date_str,
        "total_read_time": record.total_read_time if record else 0,
    })
```

- [ ] **Step 4: 在 stats 路由中计算习惯洞察**

在 `stats()` 路由的 chart_data 中添加洞察字段：

```python
# ── 习惯洞察 ──
daily_records = DailyReadStat.query.filter(
    DailyReadStat.user_id == user_id,
).order_by(DailyReadStat.date.desc()).all()

current_streak = 0
longest_streak = 0
streak = 0
for r in sorted(daily_records, key=lambda x: x.date):
    if r.total_read_time > 0:
        streak += 1
        longest_streak = max(longest_streak, streak)
    else:
        streak = 0
for r in daily_records:
    if r.total_read_time > 0:
        current_streak += 1
    else:
        break

# 最活跃星期
weekday_reads = db.session.query(
    func.extract("DAYOFWEEK", DailyReadStat.date).label("dow"),
    func.avg(DailyReadStat.total_read_time).label("avg_time")
).filter(DailyReadStat.user_id == user_id, DailyReadStat.total_read_time > 0).group_by("dow").all()
weekday_labels = ["", "周日","周一","周二","周三","周四","周五","周六"]
most_active_day = ""
most_active_avg = 0
for row in weekday_reads:
    label = weekday_labels[int(row.dow)] if int(row.dow) < len(weekday_labels) else ""
    if row.avg_time and float(row.avg_time) > most_active_avg:
        most_active_avg = float(row.avg_time)
        most_active_day = label

# 阅读目标
year_goal = ReadGoal.query.filter_by(user_id=user_id, year=datetime.utcnow().year, month=None).first()
month_goal = ReadGoal.query.filter_by(user_id=user_id, year=datetime.utcnow().year, month=datetime.utcnow().month).first()
yearly_seconds = db.session.query(func.sum(DailyReadStat.total_read_time)).filter(
    DailyReadStat.user_id == user_id,
    func.extract("YEAR", DailyReadStat.date) == datetime.utcnow().year
).scalar() or 0
monthly_seconds = db.session.query(func.sum(DailyReadStat.total_read_time)).filter(
    DailyReadStat.user_id == user_id,
    func.extract("YEAR", DailyReadStat.date) == datetime.utcnow().year,
    func.extract("MONTH", DailyReadStat.date) == datetime.utcnow().month
).scalar() or 0

insights = {
    "current_streak": current_streak,
    "longest_streak": longest_streak,
    "most_active_day": most_active_day,
    "year_goal_target": year_goal.target_read_time if year_goal else 0,
    "year_goal_current": yearly_seconds,
    "month_goal_target": month_goal.target_read_time if month_goal else 0,
    "month_goal_current": monthly_seconds,
}
chart_data["insights"] = insights
```

- [ ] **Step 5: 更新 stats.html 目标区域**

替换 `🎯 阅读目标` 卡片内容为：

```html
<div id="goal-section">
  <div class="mb-3">
    <small class="text-muted">🎯 年度目标</small>
    <div class="d-flex justify-content-between">
      <span id="year-progress-text">{{ '%d' % (insights.year_goal_current/3600) if insights else 0 }}h / {{ '%d' % (insights.year_goal_target/3600) if insights and insights.year_goal_target else 0 }}h</span>
      <span id="year-progress-pct">{{ '%.0f' % (insights.year_goal_current/insights.year_goal_target*100) if insights and insights.year_goal_target else 0 }}%</span>
    </div>
    <div class="progress" style="height:8px">
      <div id="year-progress-bar" class="progress-bar bg-danger" role="progressbar"
           style="width:{{ '%.0f' % (insights.year_goal_current/insights.year_goal_target*100) if insights and insights.year_goal_target else 0 }}%"></div>
    </div>
  </div>
  <div class="mb-3">
    <small class="text-muted">📅 本月目标</small>
    <div class="d-flex justify-content-between">
      <span id="month-progress-text">{{ '%d' % (insights.month_goal_current/3600) if insights else 0 }}h / {{ '%d' % (insights.month_goal_target/3600) if insights and insights.month_goal_target else 0 }}h</span>
      <span id="month-progress-pct">{{ '%.0f' % (insights.month_goal_current/insights.month_goal_target*100) if insights and insights.month_goal_target else 0 }}%</span>
    </div>
    <div class="progress" style="height:8px">
      <div id="month-progress-bar" class="progress-bar bg-warning" role="progressbar"
           style="width:{{ '%.0f' % (insights.month_goal_current/insights.month_goal_target*100) if insights and insights.month_goal_target else 0 }}%"></div>
    </div>
  </div>
  <div>
    <small class="text-muted">🔥 连续阅读</small>
    <div class="d-flex justify-content-between">
      <span>当前: <strong>{{ insights.current_streak if insights else 0 }}</strong> 天</span>
      <span>最长: <strong>{{ insights.longest_streak if insights else 0 }}</strong> 天</span>
      <span>最爱: <strong>{{ insights.most_active_day if insights else '--' }}</strong></span>
    </div>
  </div>
  <hr>
  <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#goalModal">设置目标</button>
</div>
```

添加 Modal：

```html
<div class="modal fade" id="goalModal" tabindex="-1">
  <div class="modal-dialog modal-sm">
    <div class="modal-content">
      <form id="goalForm">
        <div class="modal-header"><h6 class="modal-title">设置阅读目标</h6><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
        <div class="modal-body">
          <div class="mb-3">
            <label>年度目标(小时)</label>
            <input type="number" id="goal-year" class="form-control" value="{{ '%d' % (insights.year_goal_target/3600) if insights and insights.year_goal_target else 500 }}">
          </div>
          <div class="mb-3">
            <label>本月目标(小时)</label>
            <input type="number" id="goal-month" class="form-control" value="{{ '%d' % (insights.month_goal_target/3600) if insights and insights.month_goal_target else 50 }}">
          </div>
        </div>
        <div class="modal-footer">
          <button type="submit" class="btn btn-primary btn-sm">保存</button>
        </div>
      </form>
    </div>
  </div>
</div>
```

- [ ] **Step 6: 在 stats.js 中处理目标表单提交**

在 `stats.js` 末尾添加：

```javascript
const goalForm = document.getElementById("goalForm");
if (goalForm) {
  goalForm.addEventListener("submit", function(e) {
    e.preventDefault();
    const year = document.getElementById("goal-year").value;
    const month = document.getElementById("goal-month").value;
    const formData = new FormData();
    formData.append("year", new Date().getFullYear());
    formData.append("target_read_time", parseInt(year) * 3600);
    formData.append("month", new Date().getMonth() + 1);
    formData.append("target_read_time", parseInt(month) * 3600);
    fetch("/stats/goal/edit", { method: "POST", body: formData })
      .then(r => r.json()).then(() => location.reload());
  });
}
```

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/main/routes.py app/templates/stats.html app/static/js/stats.js
git commit -m "feat: add reading goals and habit insights"
```

---

### Task 8: 最终测试与微调

**Files:**
- Test: 启动应用并访问 `/stats`

**Steps:**

- [ ] **Step 1: 启动应用**

```bash
.\start.ps1
```

- [ ] **Step 2: 访问 /stats 查看页面是否正常渲染**

- [ ] **Step 3: 修复任何 JS/CSS 问题**

- [ ] **Step 4: 运行 sync-stats CLI 测试**

```bash
C:\Users\admin\my_env\Scripts\python.exe run.py sync-stats
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: complete stats enhancement with charts, calendar, goals and insights"
```
