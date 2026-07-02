"""
前端主路由 — 首页、书架、书籍详情、阅读统计、划线搜索
---------------------------------------------------
所有路由需要用户登录（@frontend_login_required），数据按 user_id 隔离。
书架同步在 /books 和 /ai-reader/books 访问时自动触发增量同步。
"""

from datetime import datetime, date, timedelta
from flask import render_template, jsonify, redirect, url_for, request, current_app
from flask_login import current_user
from app.main import bp
from app.extensions import frontend_login_required
from app.models import Book, Category, Highlight, ReadStat, DailyReadStat, ReadGoal, db
from app.weread.api import get_shelf
from app.weread.importer import import_highlights_for_book
from app.weread.stats_sync import sync_all_stats
from sqlalchemy import func, extract


# ══════════════════════════════════════════════════════════════════════
# 首页
# ══════════════════════════════════════════════════════════════════════

@bp.route('/')
@frontend_login_required
def index():
    """
    首页：展示微信读书最近阅读的 10 本书（按 readUpdateTime 降序）。
    一次批量查询本地数据库匹配 weread_book_id，避免 N+1 查询。
    """
    weread_books = []
    try:
        data = get_shelf()
        if data and 'books' in data:
            sorted_books = sorted(data.get('books', []),
                                  key=lambda b: b.get('readUpdateTime', 0) or 0, reverse=True)
            top_10 = sorted_books[:10]
            # 一次 IN 查询获取所有本地匹配的图书
            weread_ids = [str(b.get('bookId', '')) for b in top_10]
            local_books = Book.query.filter(
                Book.weread_book_id.in_(weread_ids),
                Book.user_id == current_user.id
            ).all()
            local_map = {b.weread_book_id: b.id for b in local_books}
            for b in top_10:
                bid = str(b.get('bookId', ''))
                weread_books.append({
                    'title': b.get('title', ''),
                    'author': b.get('author', ''),
                    'cover': b.get('cover', ''),
                    'book_id': bid,
                    'finished': b.get('finishReading', 0),
                    'local_id': local_map.get(bid),
                })
    except Exception:
        weread_books = None
    return render_template('index.html', weread_books=weread_books)


# ══════════════════════════════════════════════════════════════════════
# 阅读统计页 — 图表数据 + 目标管理 + 连续记录
# ══════════════════════════════════════════════════════════════════════

@bp.route('/stats')
@frontend_login_required
def stats():
    """
    阅读统计仪表盘。触发 sync_all_stats 后从 ReadStat 和 DailyReadStat
    表聚合数据，构建 Chart.js 所需的 JSON 数据结构。

    页面展示：30 日趋势图、年度热力图、12 月柱状图、分类饼图、
    时段雷达图、连续阅读天数、阅读目标进度。
    """
    user_id = current_user.safe_id
    sync_all_stats(user_id)

    # ── 四维度统计概览卡 ──
    def _find_stat(mode, period_start=None):
        q = ReadStat.query.filter_by(user_id=user_id, mode=mode)
        if period_start:
            q = q.filter_by(period_start=period_start)
        return q.order_by(ReadStat.period_start.desc()).first()

    weekly_raw = _find_stat('weekly')
    monthly_raw = _find_stat('monthly')
    annually_raw = _find_stat('annually',
                              period_start=datetime(datetime.utcnow().year, 1, 1))
    overall_raw = _find_stat('overall')

    def _fmt(s):
        """序列化 ReadStat 对象为字典。"""
        if not s:
            return None
        return {
            'totalReadTime': s.total_read_time,
            'readDays': s.read_days,
            'dayAverageReadTime': s.day_avg_read_time,
            'compare': s.compare,
            'readLongest': s.read_longest,
            'readStat': s.read_stat,
            'preferCategory': s.prefer_category,
            'preferTimeWord': s.prefer_time_word,
            'preferAuthor': s.prefer_author,
        }

    weekly = _fmt(weekly_raw)
    monthly = _fmt(monthly_raw)
    annually = _fmt(annually_raw)
    overall = _fmt(overall_raw)
    if overall and overall.get('totalReadTime') is not None and overall.get('readDays'):
        if not overall.get('dayAverageReadTime') and overall['readDays']:
            overall['dayAverageReadTime'] = overall['totalReadTime'] // overall['readDays']

    # ── 30 日每日阅读趋势（一次范围查询替代 30 次单独查询）──
    today = date.today()
    start_30 = today - timedelta(days=29)
    daily_rows = DailyReadStat.query.filter(
        DailyReadStat.user_id == user_id,
        DailyReadStat.date >= start_30,
        DailyReadStat.date <= today
    ).all()
    daily_map = {r.date: r.total_read_time for r in daily_rows}
    days_30 = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        seconds = daily_map.get(d, 0)
        days_30.append({'date': d.isoformat(), 'minutes': round(seconds / 60, 1)})

    # ── 年度热力图数据 ──
    year_days = {}
    year_rows = DailyReadStat.query.filter(
        DailyReadStat.user_id == user_id,
        extract('YEAR', DailyReadStat.date) == datetime.utcnow().year
    ).all()
    for r in year_rows:
        year_days[r.date.isoformat()] = r.total_read_time

    # ── 12 月柱状图（一次 IN 查询替代 12 次单独查询）──
    months_periods = []
    for i in range(11, -1, -1):
        m = datetime.utcnow().month - i
        y = datetime.utcnow().year
        if m <= 0:
            m += 12
            y -= 1
        months_periods.append((y, m, datetime(y, m, 1)))
    monthly_stats = ReadStat.query.filter(
        ReadStat.user_id == user_id,
        ReadStat.mode == 'monthly',
        ReadStat.period_start.in_([p[2] for p in months_periods])
    ).all()
    monthly_map = {r.period_start: r.total_read_time for r in monthly_stats}
    months_12 = [{'month': f'{y}-{m:02d}',
                  'minutes': round(monthly_map.get(ps, 0) / 60, 1)}
                 for y, m, ps in months_periods]

    # ── 分类偏好和时段分布 ──
    categories = []
    if overall and overall.get('preferCategory'):
        categories = overall['preferCategory']

    prefer_time = []
    if overall_raw and overall_raw.prefer_time:
        prefer_time = overall_raw.prefer_time

    # ── 连续阅读天数 ──
    daily_records = DailyReadStat.query.filter(
        DailyReadStat.user_id == user_id,
    ).order_by(DailyReadStat.date.desc()).all()

    current_streak = 0
    for r in daily_records:
        if r.total_read_time > 0:
            current_streak += 1
        else:
            break

    longest_streak = 0
    streak = 0
    for r in sorted(daily_records, key=lambda x: x.date):
        if r.total_read_time > 0:
            streak += 1
            longest_streak = max(longest_streak, streak)
        else:
            streak = 0

    # ── 最活跃阅读日（按星期几分组统计平均阅读时长）──
    weekday_names = ['', '周日', '周一', '周二', '周三', '周四', '周五', '周六']
    weekday_rows = db.session.query(
        func.dayofweek(DailyReadStat.date).label('dow'),
        func.avg(DailyReadStat.total_read_time).label('avg_time')
    ).filter(
        DailyReadStat.user_id == user_id,
        DailyReadStat.total_read_time > 0
    ).group_by('dow').all()
    most_active_day = ''
    most_active_avg = 0
    for row in weekday_rows:
        idx = int(row.dow) if row.dow else 0
        label = weekday_names[idx] if idx < len(weekday_names) else ''
        if row.avg_time and float(row.avg_time) > most_active_avg:
            most_active_avg = float(row.avg_time)
            most_active_day = label

    # ── 阅读目标 ──
    now_dt = datetime.utcnow()
    year_goal = ReadGoal.query.filter_by(
        user_id=user_id, year=now_dt.year, month=None
    ).first()
    month_goal = ReadGoal.query.filter_by(
        user_id=user_id, year=now_dt.year, month=now_dt.month
    ).first()
    yearly_seconds = int(db.session.query(func.sum(DailyReadStat.total_read_time)).filter(
        DailyReadStat.user_id == user_id,
        extract('YEAR', DailyReadStat.date) == now_dt.year
    ).scalar() or 0)
    monthly_seconds = int(db.session.query(func.sum(DailyReadStat.total_read_time)).filter(
        DailyReadStat.user_id == user_id,
        extract('YEAR', DailyReadStat.date) == now_dt.year,
        extract('MONTH', DailyReadStat.date) == now_dt.month
    ).scalar() or 0)

    chart_data = {
        'dailyTrend': days_30,
        'calendar': year_days,
        'monthlyTrend': months_12,
        'categories': categories,
        'preferTime': prefer_time,
        'insights': {
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'most_active_day': most_active_day,
            'year_goal_target': year_goal.target_read_time if year_goal else 0,
            'year_goal_current': yearly_seconds,
            'month_goal_target': month_goal.target_read_time if month_goal else 0,
            'month_goal_current': monthly_seconds,
        }
    }

    return render_template('stats.html', weekly=weekly, monthly=monthly,
                           annually=annually, overall=overall,
                           chart_data=chart_data)


@bp.route('/stats/goal/edit', methods=['POST'])
@frontend_login_required
def edit_goal():
    """设置年度或月度阅读目标（JSON API）。"""
    user_id = current_user.safe_id
    year = request.form.get('year', type=int, default=datetime.utcnow().year)
    month = request.form.get('month', type=int)
    target = request.form.get('target_read_time', type=int, default=0)
    goal = ReadGoal.query.filter_by(user_id=user_id, year=year, month=month).first()
    if goal:
        goal.target_read_time = target
    else:
        goal = ReadGoal(user_id=user_id, year=year, month=month,
                        target_read_time=target)
        db.session.add(goal)
    db.session.commit()
    return jsonify({'ok': True})


@bp.route('/stats/daily/<date_str>')
@frontend_login_required
def daily_detail(date_str):
    """查询指定日期的阅读时长（JSON API）。"""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'invalid date'}), 400
    r = DailyReadStat.query.filter_by(user_id=current_user.safe_id, date=d).first()
    return jsonify({
        'date': date_str,
        'total_read_time': r.total_read_time if r else 0,
    })


# ══════════════════════════════════════════════════════════════════════
# 书架浏览
# ══════════════════════════════════════════════════════════════════════

@bp.route('/books')
@frontend_login_required
def book_list():
    """
    书架列表页：支持按分类、状态、关键词过滤，分页 12 本/页。
    每次访问触发增量 sync_shelf_for_user()（300s 缓存保护）。
    仅显示 shelved=True 的书（微信读书已下架的不显示）。
    """
    from app.weread.importer import sync_shelf_for_user
    try:
        sync_shelf_for_user(current_user.id)
    except Exception:
        current_app.logger.warning('书架同步失败，显示缓存数据', exc_info=True)

    cid = request.args.get('category', type=int)
    sf = request.args.get('status')
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    query = Book.query.filter_by(user_id=current_user.id, shelved=True)
    if cid:
        query = query.filter_by(category_id=cid)
    if sf in ('reading', 'done'):
        query = query.filter_by(status=sf)
    if q:
        query = query.filter(Book.title.contains(q) | Book.author.contains(q))
    pagination = query.order_by(Book.created_at.desc()).paginate(page=page, per_page=12)
    return render_template('books/list.html', pagination=pagination,
                           categories=Category.query.all(), current_category=cid,
                           current_status=sf, q=q)


# ══════════════════════════════════════════════════════════════════════
# 书籍详情
# ══════════════════════════════════════════════════════════════════════

@bp.route('/books/<int:id>')
@frontend_login_required
def book_detail(id):
    """书籍详情页：显示基本信息、进度、划线笔记（异步加载）、个人笔记。"""
    book = Book.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    book.last_viewed_at = datetime.now()
    # 懒加载简介：如果本地没有简介且来自微信读书，从 API 获取
    if not book.summary and book.weread_book_id:
        try:
            from app.weread.api import get_book_info
            info = get_book_info(book.weread_book_id)
            if info and info.get('intro'):
                book.summary = info['intro']
        except Exception:
            pass
    db.session.commit()
    return render_template('books/detail.html', book=book)


@bp.route('/books/<int:id>/highlights')
@frontend_login_required
def book_highlights(id):
    """
    返回指定书籍的划线笔记 JSON，按章节分组。
    首次访问时触发 import_highlights_for_book() 从微信读书 API 导入。
    """
    book = Book.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    exists = Highlight.query.filter_by(book_id=book.id, user_id=current_user.id).first()
    if not exists and book.weread_book_id:
        try:
            import_highlights_for_book(book, current_user.id)
        except Exception as e:
            current_app.logger.warning('导入划线失败: %s', e)
            return jsonify({'highlights': [], 'error': '导入划线失败: ' + str(e)}), 500

    highlights = Highlight.query.filter_by(book_id=book.id, user_id=current_user.id).order_by(
        Highlight.chapter_uid, Highlight.created_at).all()

    # 微信读书六种划线颜色映射
    color_map = {0: '#F9F3A7', 1: '#B5D8B5', 2: '#A7C7E7', 3: '#F0C0C0', 4: '#F5C792', 5: '#E8D5B7'}

    groups = {}
    for hl in highlights:
        key = hl.chapter_uid or 0
        if key not in groups:
            groups[key] = {'chapter_title': hl.chapter_title or '其他', 'items': []}
        groups[key]['items'].append({
            'id': hl.id,
            'mark_text': hl.mark_text,
            'color': color_map.get(hl.color_style, color_map[0]),
            'created_at': hl.created_at.strftime('%Y-%m-%d') if hl.created_at else '',
        })

    return jsonify({'highlights': list(groups.values())})


# ══════════════════════════════════════════════════════════════════════
# 全局划线搜索
# ══════════════════════════════════════════════════════════════════════

@bp.route('/highlights/search')
@frontend_login_required
def highlight_search():
    """
    跨书籍搜索划线笔记。使用 SQLAlchemy contains() 做 LIKE 模糊匹配，
    JOIN books 表获取书名和作者，分页 15 条/页。
    """
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    if not q or len(q) < 2:
        return render_template('highlights/search.html', pagination=None, q=q)

    query = Highlight.query.filter(
        Highlight.user_id == current_user.safe_id,
        Highlight.mark_text.contains(q)
    ).join(Book, Highlight.book_id == Book.id).add_columns(
        Highlight.id, Highlight.mark_text, Highlight.chapter_title,
        Highlight.color_style, Highlight.created_at,
        Book.id.label('book_id'), Book.cover_url.label('book_cover'),
        Book.title.label('book_title'), Book.author.label('book_author')
    ).order_by(Highlight.created_at.desc())

    pagination = query.paginate(page=page, per_page=15)
    return render_template('highlights/search.html', pagination=pagination, q=q)
