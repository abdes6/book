"""
数据模型层
---------
11 张表，采用多租户设计：所有用户数据通过 user_id 外键隔离。
Book 为核心实体，关联 Highlight、Note、BookChat、BookAIContent。
ReadStat / DailyReadStat / ReadGoal 构成阅读统计子系统。
Thinker / Conversation 构成 AI 哲学家对话子系统。

关键设计决策：
- 管理员合并到 users 表（首个注册用户即为管理员，密码由 init-db CLI 命令设置）
- User.get_id() 返回 'u_{id}' 前缀字符串，load_user() 反向解析
- 书架同步不物理删除，改为 shelved=False 软删除
- 关联关系使用 cascade='all, delete-orphan' 确保删除 Book 时清理所有子数据
"""

from datetime import datetime, date
from sqlalchemy import UniqueConstraint
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager


# ══════════════════════════════════════════════════════════════════════
# 分类表
# ══════════════════════════════════════════════════════════════════════

class Category(db.Model):
    """微信读书分类，如 文学、历史、哲学宗教 等 19 个预设分类。"""
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    books = db.relationship('Book', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


# ══════════════════════════════════════════════════════════════════════
# 图书表 — 核心实体
# ══════════════════════════════════════════════════════════════════════

class Book(db.Model):
    """
    图书是系统核心实体。每本书归属于一个用户（多租户）。
    weread_book_id 是从微信读书 API 导入时的唯一标识，用于去重和同步。
    shelved=False 表示该书已从微信读书书架移除，但本地保留（软删除）。
    """
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    author = db.Column(db.String(100))
    isbn = db.Column(db.String(20))
    cover_url = db.Column(db.String(500))
    summary = db.Column(db.Text)
    rating = db.Column(db.Numeric(2, 1), default=0.0)
    status = db.Column(db.String(10), default='reading', index=True)  # 'reading' | 'done'
    notes = db.Column(db.Text)         # 个人读后感（区别于 Note 表的长文笔记）
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True)
    imported = db.Column(db.Boolean, default=False)  # 是否来自微信读书
    shelved = db.Column(db.Boolean, default=True, index=True)  # 是否在书架（软删除标记）
    weread_book_id = db.Column(db.String(50), index=True)  # 微信读书 bookId，导入去重键
    progress = db.Column(db.Integer, default=0)            # 阅读进度 0-100（预留）
    last_read_at = db.Column(db.DateTime, nullable=True)   # 最近阅读时间（取自 readUpdateTime）
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    last_viewed_at = db.Column(db.DateTime, nullable=True)  # 用户在本地最后查看时间

    # ── 关联关系 ──
    owner = db.relationship('User', backref=db.backref('books', lazy='dynamic'))
    highlights = db.relationship('Highlight', backref='book', lazy='dynamic',
                                 cascade='all, delete-orphan',
                                 order_by='Highlight.chapter_uid, Highlight.created_at')

    def __repr__(self):
        return f'<Book {self.title}>'


# ══════════════════════════════════════════════════════════════════════
# 划线笔记表
# ══════════════════════════════════════════════════════════════════════

class Highlight(db.Model):
    """
    微信读书划线笔记。按需导入（首次访问书籍详情时触发）。
    weread_bookmark_id 用于去重：同一划线不会重复导入。
    color_style 0-5 对应微信读书的六种划线颜色。
    """
    __tablename__ = 'highlights'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False, index=True)
    weread_bookmark_id = db.Column(db.String(100), nullable=False)  # 去重键
    chapter_uid = db.Column(db.Integer, default=0)      # 章节编号
    chapter_title = db.Column(db.String(200), default='')  # 章节标题
    mark_text = db.Column(db.Text, nullable=False)      # 划线文本
    range = db.Column(db.String(100))                   # 在章节中的位置
    color_style = db.Column(db.Integer, default=0)      # 颜色 0-5
    created_at = db.Column(db.DateTime)                 # 划线创建时间（微信读书侧）
    imported_at = db.Column(db.DateTime, default=datetime.now)  # 导入时间


# ══════════════════════════════════════════════════════════════════════
# 用户表
# ══════════════════════════════════════════════════════════════════════

class User(UserMixin, db.Model):
    """
    用户模型，同时承担管理员角色（首个注册用户即为管理员）。
    get_id() 返回带前缀的字符串 'u_{id}'，用于区分用户和废弃的 Admin 模型。
    weread_api_key 是每个用户自己的微信读书 API 密钥，用于调用书架/划线/统计 API。
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    weread_api_key = db.Column(db.String(500), default='', nullable=True)
    shelf_synced = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        """使用 Werkzeug 哈希存储密码，不存明文。"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        """返回带 u_ 前缀的 ID 字符串，供 Flask-Login 使用。"""
        return f'u_{self.id}'

    @property
    def safe_id(self):
        """返回纯整数 ID，路由中使用 current_user.safe_id 避免重复解析。"""
        return self.id


# ── Flask-Login 用户加载器 ──────────────────────────────────────────
# 从 session 中恢复用户对象，兼容 'u_' 前缀和纯数字两种格式

@login_manager.user_loader
def load_user(user_id):
    uid = int(user_id[2:]) if user_id.startswith('u_') else int(user_id)
    return User.query.get(uid)


# ══════════════════════════════════════════════════════════════════════
# 笔记与图片表
# ══════════════════════════════════════════════════════════════════════

class Note(db.Model):
    """
    用户长文笔记，Markdown 格式。每篇笔记关联一本书，可选关联一条划线。
    支持导出为 Markdown 文件或 HTML（打印为 PDF）。
    """
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False, index=True)
    highlight_id = db.Column(db.Integer, db.ForeignKey('highlights.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)  # Markdown 格式
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    author = db.relationship('User', backref=db.backref('notes', lazy='dynamic'))
    book = db.relationship('Book', backref=db.backref('user_notes', lazy='dynamic',
                                                      cascade='all, delete-orphan',
                                                      order_by='Note.updated_at.desc()'))
    highlight = db.relationship('Highlight', backref=db.backref('notes', lazy='dynamic'))


class NoteImage(db.Model):
    """笔记中嵌入的图片附件，支持拖拽调整显示宽度。"""
    __tablename__ = 'note_images'

    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('notes.id'), nullable=True)
    filename = db.Column(db.String(200), nullable=False)
    stored_path = db.Column(db.String(300), nullable=False)  # 相对于 static/ 的路径
    display_width = db.Column(db.Integer, nullable=True)     # 用户调整后的显示宽度
    uploaded_at = db.Column(db.DateTime, default=datetime.now)

    note_ref = db.relationship('Note', backref=db.backref('images', lazy='dynamic',
                                cascade='all, delete-orphan',
                                order_by='NoteImage.uploaded_at'))


# ══════════════════════════════════════════════════════════════════════
# 阅读统计表 — 聚合统计数据
# ══════════════════════════════════════════════════════════════════════

class ReadStat(db.Model):
    """
    微信读书聚合统计，支持 4 种时间维度：weekly / monthly / annually / overall。
    唯一约束 (user_id, mode, period_start) 确保每个周期只有一条记录。
    5 分钟 TTL 缓存：sync_all_stats() 检查最近 synced_at，避免频繁调用 API。
    """
    __tablename__ = "read_stat"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mode = db.Column(db.String(20), nullable=False)          # weekly|monthly|annually|overall
    period_start = db.Column(db.DateTime, nullable=False)   # 统计周期起始
    period_end = db.Column(db.DateTime, nullable=False)     # 统计周期结束
    total_read_time = db.Column(db.Integer, default=0)      # 总阅读时长（秒）
    read_days = db.Column(db.Integer, default=0)            # 阅读天数
    day_avg_read_time = db.Column(db.Integer, default=0)    # 日均阅读时长（秒）
    compare = db.Column(db.Float, nullable=True)            # 环比变化率
    read_longest = db.Column(db.JSON, nullable=True)        # 阅读最久的书
    read_stat = db.Column(db.JSON, nullable=True)           # 阅读统计摘要
    prefer_category = db.Column(db.JSON, nullable=True)     # 偏好分类
    prefer_time_word = db.Column(db.String(100), nullable=True)
    prefer_author = db.Column(db.JSON, nullable=True)       # 偏好作者
    prefer_time = db.Column(db.JSON, nullable=True)         # 偏好时段（24小时分布）
    read_rate = db.Column(db.Float, nullable=True)
    wr_read_time = db.Column(db.Integer, nullable=True)
    wr_listen_time = db.Column(db.Integer, nullable=True)
    raw_data = db.Column(db.JSON, nullable=True)            # 原始 API 响应
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "mode", "period_start"),)
    user = db.relationship("User", backref=db.backref("read_stats", lazy="dynamic"))


class DailyReadStat(db.Model):
    """
    每日阅读时长明细。唯一约束 (user_id, date)。
    数据源：微信读书 API 返回的 readTimes 字典（Unix时间戳 → 秒数）。
    用于绘制 30 日趋势图、年度热力图、连续阅读天数计算。
    """
    __tablename__ = "daily_read_stat"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    total_read_time = db.Column(db.Integer, default=0)  # 当天阅读总秒数
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "date"),)
    user = db.relationship("User", backref=db.backref("daily_read_stats", lazy="dynamic"))


class ReadGoal(db.Model):
    """
    阅读目标：支持年度目标和月度目标。
    month 为 NULL 表示年度目标，非 NULL 表示特定月度目标。
    """
    __tablename__ = "read_goal"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=True)           # NULL=年度目标
    target_read_time = db.Column(db.Integer, default=0)    # 目标阅读时长（秒）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "year", "month"),)
    user = db.relationship("User", backref=db.backref("read_goals", lazy="dynamic"))


# ══════════════════════════════════════════════════════════════════════
# AI 哲学家对话子系统
# ══════════════════════════════════════════════════════════════════════

class Thinker(db.Model):
    """
    哲学家配置。system_prompt 定义了该哲学家的性格、语气和知识背景。
    18 位预设哲学家：老子、孔子、苏格拉底、柏拉图、亚里士多德、庄子、
    康德、黑格尔、叔本华、尼采、弗雷格、弗洛伊德、阿德勒、荣格、罗素、
    维特根斯坦、萨特、加缪。
    """
    __tablename__ = "thinker"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)           # 显示名
    slug = db.Column(db.String(50), unique=True, nullable=False)  # URL 标识
    title = db.Column(db.String(100))                         # 头衔
    avatar_url = db.Column(db.String(500), default='')
    era = db.Column(db.String(50))                            # 时代
    school = db.Column(db.String(100))                        # 学派
    bio = db.Column(db.Text)
    system_prompt = db.Column(db.Text, nullable=False)        # AI 角色设定
    opening_line = db.Column(db.Text, nullable=True)          # 开场白（含 ===OPTIONS=== 格式）
    theme = db.Column(db.String(50), default='')              # 主题色名称
    sort_order = db.Column(db.Integer, default=0)             # 展示排序
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    conversations = db.relationship("Conversation", backref="thinker", lazy="dynamic",
                                    cascade="all, delete-orphan")


class Conversation(db.Model):
    """
    哲学家对话记录。messages 字段存储 JSON 数组 [{role, content, content_html}]。
    每种角色一条消息，content_html 是 Markdown 渲染后的 HTML。
    """
    __tablename__ = "conversation"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    thinker_id = db.Column(db.Integer, db.ForeignKey("thinker.id"), nullable=False)
    title = db.Column(db.String(200), default="新对话")       # 对话标题
    messages = db.Column(db.JSON, nullable=False, default=list)  # [{role, content, content_html}]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("conversations", lazy="dynamic"))


# ══════════════════════════════════════════════════════════════════════
# AI 阅读助手子系统
# ══════════════════════════════════════════════════════════════════════

class BookChat(db.Model):
    """
    与特定书籍的 AI 对话记录。每条消息包含 role 和 content 以及 content_html。
    对话历史会作为上下文发送给 DeepSeek API。
    """
    __tablename__ = 'book_chat'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False, index=True)
    title = db.Column(db.String(200), default='关于本书的对话')
    messages = db.Column(db.JSON, nullable=False, default=list)  # [{role, content, content_html}]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('book_chats', lazy='dynamic'))
    book = db.relationship('Book', backref=db.backref('book_chats', lazy='dynamic',
                                                      cascade='all, delete-orphan'))


class BookAIContent(db.Model):
    """
    书籍 AI 生成内容缓存。按 (user_id, book_id, content_type) 唯一。
    content_type: 'summary'(摘要) | 'review'(书评) | 'analysis'(划线分析)
    首次生成后缓存，用户可点击"重新生成"刷新。
    """
    __tablename__ = 'book_ai_content'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    content_type = db.Column(db.String(20), nullable=False)  # summary|review|analysis
    content = db.Column(db.Text, nullable=False)             # AI 生成的原始文本
    source_info = db.Column(db.Text, nullable=True)          # 数据来源说明（如"30条笔记"）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('user_id', 'book_id', 'content_type'),)
    user = db.relationship('User', backref=db.backref('ai_contents', lazy='dynamic'))
    book = db.relationship('Book', backref=db.backref('ai_contents', lazy='dynamic',
                                                       cascade='all, delete-orphan'))


# ══════════════════════════════════════════════════════════════════════
# 微信读书想法/点评表
# ══════════════════════════════════════════════════════════════════════

class Thought(db.Model):
    """
    微信读书"想法/点评"数据。包含划线想法、章节点评和整本书评三种类型。
    weread_review_id 用于去重：同一想法不会重复导入。
    highlight_id 为可空外键，划线想法通过 range/abstract 匹配到对应 Highlight。
    """
    __tablename__ = 'thoughts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False, index=True)
    highlight_id = db.Column(db.Integer, db.ForeignKey('highlights.id'), nullable=True, index=True)
    weread_review_id = db.Column(db.String(100), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    star = db.Column(db.Integer, default=-1)
    thought_type = db.Column(db.String(20), default='bookmark')
    chapter_name = db.Column(db.String(200), default='')
    is_finish = db.Column(db.Boolean, nullable=True)
    ref_range = db.Column(db.String(100), default='')
    ref_abstract = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, nullable=True)
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('thoughts', lazy='dynamic'))
    book = db.relationship('Book', backref=db.backref('thoughts', lazy='dynamic',
                                                       cascade='all, delete-orphan'))
    highlight = db.relationship('Highlight', backref=db.backref('thoughts', lazy='dynamic',
                                                                cascade='all, delete-orphan'))
