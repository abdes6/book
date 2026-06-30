from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired


class NoteForm(FlaskForm):
    title = StringField('笔记标题', validators=[DataRequired()])
    content = TextAreaField('笔记内容')
    submit = SubmitField('保存')
