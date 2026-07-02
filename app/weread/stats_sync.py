"""
阅读统计数据同步
---------------
从微信读书 API 拉取阅读统计数据并存入本地 ReadStat / DailyReadStat 表。

同步维度：
- overall   — 全部历史汇总（调用 1 次）
- annually  — 每年统计（注册年至今年，历史年份仅首次拉取）
- weekly    — 本周统计（每次同步都刷新）
- monthly   — 每月统计（仅当前月刷新，历史月份首次拉取后缓存）

缓存策略（5 分钟 TTL）：
- sync_all_stats() 入口检查最近 synced_at，避免高频调用
- 历史数据（去年及以前、之前月份）只拉一次，不会重复

数据存储：
- ReadStat：聚合统计，按 (user_id, mode, period_start) 唯一
- DailyReadStat：每日明细，按 (user_id, date) 唯一，数据源为 readTimes 字典
"""

import logging
from datetime import datetime, date, timedelta
from app import db
from app.models import ReadStat, DailyReadStat
from app.weread.api import get_readdata

logger = logging.getLogger(__name__)


def _parse_period(mode, base_time=0):
    """根据 mode 计算统计周期的起止时间。"""
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


def sync_all_stats(user_id, ttl_seconds=300):
    """
    全量同步用户的阅读统计数据。
    受 5 分钟 TTL 保护：如果最近一次同步在 TTL 内，直接返回。
    历史年份和月份仅在本地无数据时拉取，避免重复 API 调用。
    """
    # ── TTL 检查 ──
    latest = ReadStat.query.filter_by(user_id=user_id).order_by(
        ReadStat.synced_at.desc()
    ).first()
    if latest and latest.synced_at:
        elapsed = (datetime.utcnow() - latest.synced_at).total_seconds()
        if elapsed < ttl_seconds:
            return

    # ── overall（汇总）—— 必须成功，否则中断 ──
    overall = get_readdata("overall")
    if not overall:
        logger.warning("WeRead API overall failed")
        return
    _save_read_stat(user_id, "overall", overall)

    # ── annually（每年）—— 历史年份不重复拉取 ──
    regist_time = overall.get("registTime", 0)
    regist_year = datetime.fromtimestamp(regist_time).year if regist_time else 2020
    current_year = datetime.utcnow().year

    for year in range(regist_year, current_year + 1):
        existing = ReadStat.query.filter_by(
            user_id=user_id, mode="annually",
            period_start=datetime(year, 1, 1)
        ).first()
        if existing and year != current_year:   # 历史年份已有数据，跳过
            continue
        ts = int(datetime(year, 7, 1).timestamp())
        data = get_readdata("annually", base_time=ts)
        if data and data.get("totalReadTime") is not None:
            _save_read_stat(user_id, "annually", data,
                            period_start=datetime(year, 1, 1))

    # ── weekly（本周）—— 每次刷新 ──
    weekly = get_readdata("weekly")
    if weekly:
        _save_read_stat(user_id, "weekly", weekly)

    # ── monthly（每月）—— 仅当前月刷新 ──
    now = datetime.utcnow()
    for i in range(11, -1, -1):
        m = now.month - i
        y = now.year
        if m <= 0:
            m += 12
            y -= 1
        ps = datetime(y, m, 1)
        existing = ReadStat.query.filter_by(
            user_id=user_id, mode="monthly", period_start=ps
        ).first()
        if existing and (y != now.year or m != now.month):
            continue  # 历史月份已有数据，跳过
        ts = int(ps.timestamp())
        monthly_data = get_readdata("monthly", base_time=ts)
        if monthly_data:
            _save_read_stat(user_id, "monthly", monthly_data, period_start=ps)
            if monthly_data.get("readTimes"):
                _save_daily_from_readTimes(user_id, monthly_data["readTimes"])

    # ── 确保今天有日记录 ──
    existing_today = DailyReadStat.query.filter_by(
        user_id=user_id, date=date.today()
    ).first()
    if existing_today:
        existing_today.synced_at = datetime.utcnow()
        db.session.commit()


def _save_read_stat(user_id, mode, data, period_start=None):
    """
    保存或更新一条 ReadStat 记录。
    使用 upsert 模式：先查后改，避免重复插入。
    """
    ps, pe = _parse_period(mode)
    if period_start:
        ps = period_start

    if mode == "annually" and not period_start:
        base_time = data.get("baseTime")
        if base_time:
            ps = datetime.fromtimestamp(base_time)
            pe = datetime(ps.year + 1, 1, 1)

    existing = ReadStat.query.filter_by(
        user_id=user_id, mode=mode, period_start=ps
    ).first()

    if existing:
        # 更新已有记录
        existing.total_read_time = data.get("totalReadTime", 0)
        existing.read_days = data.get("readDays", 0)
        existing.day_avg_read_time = data.get("dayAverageReadTime", 0)
        existing.compare = data.get("compare")
        existing.read_longest = data.get("readLongest")
        existing.read_stat = data.get("readStat")
        existing.prefer_category = data.get("preferCategory")
        existing.prefer_time_word = data.get("preferTimeWord")
        existing.prefer_author = data.get("preferAuthor")
        existing.prefer_time = data.get("preferTime")
        existing.read_rate = data.get("readRate")
        existing.wr_read_time = data.get("wrReadTime")
        existing.wr_listen_time = data.get("wrListenTime")
        existing.raw_data = data
        existing.synced_at = datetime.utcnow()
    else:
        # 新建记录
        stat = ReadStat(
            user_id=user_id, mode=mode, period_start=ps, period_end=pe,
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
        db.session.add(stat)
    db.session.commit()


def _save_daily_from_readTimes(user_id, daily_dict):
    """
    从 readTimes 字典（Unix时间戳 → 阅读秒数）创建/更新每日统计记录。
    同时补全缺失日期的零读数记录。
    """
    if not daily_dict:
        return

    timestamps = []
    for ts_str, seconds in daily_dict.items():
        try:
            day = datetime.fromtimestamp(int(ts_str)).date()
            timestamps.append((day, int(seconds)))
        except (ValueError, OSError):
            continue

    # ── 保存/更新有数据的日期 ──
    saved_dates = set()
    for day, seconds in timestamps:
        saved_dates.add(day)
        existing = DailyReadStat.query.filter_by(user_id=user_id, date=day).first()
        if existing:
            existing.total_read_time = seconds
            existing.synced_at = datetime.utcnow()
        else:
            db.session.add(DailyReadStat(
                user_id=user_id, date=day,
                total_read_time=seconds,
                synced_at=datetime.utcnow()
            ))

    if not timestamps:
        return

    # ── 补全无数据的日期为 0 ──
    min_day = timestamps[0][0].replace(day=1)
    max_day = timestamps[-1][0]
    if max_day.month == datetime.utcnow().month:
        end_day = datetime.utcnow().date()
    else:
        end_day = max_day.replace(day=1)
        end_day = (end_day + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    d = min_day
    while d <= end_day:
        if d not in saved_dates:
            existing = DailyReadStat.query.filter_by(user_id=user_id, date=d).first()
            if not existing:
                db.session.add(DailyReadStat(
                    user_id=user_id, date=d,
                    total_read_time=0,
                    synced_at=datetime.utcnow()
                ))
        d += timedelta(days=1)
    db.session.commit()
