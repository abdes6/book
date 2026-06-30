from datetime import datetime, date, timedelta
from flask import render_template, jsonify, redirect, url_for, request as flask_request
from flask import current_app
from flask_login import current_user
from app.main import bp
from app.extensions import frontend_login_required
from app.models import Book, Category, Highlight, ReadStat, DailyReadStat, ReadGoal, db
from app.weread.api import get_shelf
from app.weread.importer import import_highlights_for_book
from app.weread.stats_sync import sync_all_stats
from sqlalchemy import func, extract


@bp.route('/')
@frontend_login_required
def index():
    weread_books = []
    try:
        data = get_shelf()
        if data and 'books' in data:
            sorted_books = sorted(data.get('books', []), key=lambda b: b.get('readUpdateTime', 0) or 0, reverse=True)
            for b in sorted_books[:10]:
                local = Book.query.filter_by(weread_book_id=str(b.get('bookId', ''))).first()
                weread_books.append({
                    'title': b.get('title', ''),
                    'author': b.get('author', ''),
                    'cover': b.get('cover', ''),
                    'book_id': b.get('bookId', ''),
                    'finished': b.get('finishReading', 0),
                    'local_id': local.id if local else None,
                })
    except Exception:
        weread_books = None
    return render_template('index.html', weread_books=weread_books)


@bp.route('/stats')
@frontend_login_required
def stats():
    user_id = int(current_user.get_id().replace('u_', ''))
    sync_all_stats(user_id)

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

    today = date.today()
    days_30 = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        r = DailyReadStat.query.filter_by(user_id=user_id, date=d).first()
        seconds = r.total_read_time if r else 0
        days_30.append({'date': d.isoformat(), 'minutes': round(seconds / 60, 1)})

    year_days = {}
    year_rows = DailyReadStat.query.filter(
        DailyReadStat.user_id == user_id,
        extract('YEAR', DailyReadStat.date) == datetime.utcnow().year
    ).all()
    for r in year_rows:
        year_days[r.date.isoformat()] = r.total_read_time

    months_12 = []
    for i in range(11, -1, -1):
        m = datetime.utcnow().month - i
        y = datetime.utcnow().year
        if m <= 0:
            m += 12
            y -= 1
        ps = datetime(y, m, 1)
        r = _find_stat('monthly', period_start=ps)
        seconds = r.total_read_time if r else 0
        months_12.append({'month': f'{y}-{m:02d}', 'minutes': round(seconds / 60, 1)})

    categories = []
    if overall and overall.get('preferCategory'):
        categories = overall['preferCategory']

    prefer_time = []
    if overall_raw and overall_raw.prefer_time:
        prefer_time = overall_raw.prefer_time

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

    weekday_names = ['', '周日', '周一', '周二', '周三', '周四', '周五', '周六']
    weekday_rows = db.session.query(
        extract('DAYOFWEEK', DailyReadStat.date).label('dow'),
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

    now_dt = datetime.utcnow()
    year_goal = ReadGoal.query.filter_by(
        user_id=user_id, year=now_dt.year, month=None
    ).first()
    month_goal = ReadGoal.query.filter_by(
        user_id=user_id, year=now_dt.year, month=now_dt.month
    ).first()
    yearly_seconds = db.session.query(func.sum(DailyReadStat.total_read_time)).filter(
        DailyReadStat.user_id == user_id,
        extract('YEAR', DailyReadStat.date) == now_dt.year
    ).scalar() or 0
    monthly_seconds = db.session.query(func.sum(DailyReadStat.total_read_time)).filter(
        DailyReadStat.user_id == user_id,
        extract('YEAR', DailyReadStat.date) == now_dt.year,
        extract('MONTH', DailyReadStat.date) == now_dt.month
    ).scalar() or 0

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
    user_id = int(current_user.get_id().replace('u_', ''))
    year = flask_request.form.get('year', type=int, default=datetime.utcnow().year)
    month = flask_request.form.get('month', type=int)
    target = flask_request.form.get('target_read_time', type=int, default=0)
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
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'invalid date'}), 400
    user_id = int(current_user.get_id().replace('u_', ''))
    r = DailyReadStat.query.filter_by(user_id=user_id, date=d).first()
    return jsonify({
        'date': date_str,
        'total_read_time': r.total_read_time if r else 0,
    })
@bp.route('/books')
@frontend_login_required
def book_list():
    from flask import request
    cid = request.args.get('category', type=int)
    sf = request.args.get('status')
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    query = Book.query
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


@bp.route('/books/<int:id>')
@frontend_login_required
def book_detail(id):
    book = Book.query.get_or_404(id)
    book.last_viewed_at = datetime.now()
    db.session.commit()
    return render_template('books/detail.html', book=book)


@bp.route('/books/<int:id>/highlights')
@frontend_login_required
def book_highlights(id):
    book = Book.query.get_or_404(id)
    exists = Highlight.query.filter_by(book_id=book.id).first()
    if not exists and book.weread_book_id:
        try:
            import_highlights_for_book(book)
        except Exception as e:
            current_app.logger.warning('导入划线失败: %s', e)
            return jsonify({'highlights': [], 'error': '导入划线失败: ' + str(e)}), 500

    highlights = Highlight.query.filter_by(book_id=book.id).order_by(
        Highlight.chapter_uid, Highlight.created_at).all()

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
