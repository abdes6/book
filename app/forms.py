from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DecimalField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, Email, EqualTo


class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(1, 50)])
    password = PasswordField('密码', validators=[DataRequired()])
    captcha = StringField('验证码', validators=[DataRequired(), Length(4, 4)])
    submit = SubmitField('登录')


class BookForm(FlaskForm):
    title = StringField('书名', validators=[DataRequired(), Length(1, 200)])
    author = StringField('作者', validators=[Length(0, 100)])
    isbn = StringField('ISBN', validators=[Length(0, 20)])
    cover_url = StringField('封面URL', validators=[Length(0, 500)])
    summary = TextAreaField('简介')
    rating = DecimalField('评分', validators=[Optional(), NumberRange(0, 5)], places=1)
    status = SelectField('阅读状态', choices=[
        ('reading', '在读'), ('done', '读完')
    ])
    notes = TextAreaField('读后感')
    category_id = SelectField('分类', coerce=int, validators=[Optional()])
    submit = SubmitField('保存')


class CategoryForm(FlaskForm):
    name = StringField('分类名称', validators=[DataRequired(), Length(1, 50)])
    submit = SubmitField('添加')


class UserLoginForm(FlaskForm):
    email = StringField('邮箱', validators=[DataRequired(), Email(message='邮箱格式不正确')])
    password = PasswordField('密码', validators=[DataRequired()])
    remember = BooleanField('记住我')
    submit = SubmitField('登录')


class RegisterForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(2, 50)])
    email = StringField('邮箱', validators=[DataRequired(), Email(message='邮箱格式不正确')])
    password = PasswordField('密码', validators=[DataRequired(), Length(6, 50, message='密码至少6位')])
    confirm = PasswordField('确认密码', validators=[DataRequired(), EqualTo('password', message='两次密码不一致')])
    submit = SubmitField('注册')
