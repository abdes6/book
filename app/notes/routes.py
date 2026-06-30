import os
import json
import uuid
from datetime import datetime
from urllib.parse import quote
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, Response, abort
from flask_login import current_user
from werkzeug.utils import secure_filename
from app.extensions import csrf, frontend_login_required
from app.notes import bp
from app.notes.forms import NoteForm
from app.models import db, Book, Note, NoteImage

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route('/book/<int:book_id>')
@frontend_login_required
def book_notes(book_id):
    notes = Note.query.filter_by(user_id=current_user.id, book_id=book_id)\
        .order_by(Note.updated_at.desc()).all()
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'preview': (n.content or '')[:100],
        'updated_at': n.updated_at.strftime('%Y-%m-%d %H:%M') if n.updated_at else '',
    } for n in notes])


@bp.route('/create/<int:book_id>', methods=['GET', 'POST'])
@frontend_login_required
def note_create(book_id):
    book = Book.query.filter_by(id=book_id, user_id=current_user.id).first_or_404()
    form = NoteForm()
    if form.validate_on_submit():
        note = Note(
            user_id=current_user.id,
            book_id=book.id,
            title=form.title.data,
            content=form.content.data,
        )
        db.session.add(note)
        db.session.flush()

        for img_data in json.loads(request.form.get('attached_images', '[]')):
            db.session.add(NoteImage(
                note_id=note.id,
                filename=img_data.get('name', ''),
                stored_path=img_data.get('path', ''),
                display_width=img_data.get('width'),
            ))
        db.session.commit()
        flash('笔记保存成功', 'success')
        return redirect(url_for('notes.note_detail', id=note.id))
    return render_template('notes/create.html', form=form, book=book)


@bp.route('/<int:id>')
@frontend_login_required
def note_detail(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        flash('无权访问', 'danger')
        return redirect(url_for('main.index'))
    images = NoteImage.query.filter_by(note_id=note.id)\
        .order_by(NoteImage.uploaded_at).all()
    return render_template('notes/detail.html', note=note, images=images)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@frontend_login_required
def note_edit(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        flash('无权操作', 'danger')
        return redirect(url_for('main.index'))

    form = NoteForm(obj=note)

    if form.validate_on_submit():
        note.title = form.title.data
        note.content = form.content.data
        note.updated_at = datetime.now()

        for key, val in request.form.items():
            if key.startswith('existing_width_'):
                img_id = int(key.split('_')[2])
                try:
                    w = int(val)
                    img = NoteImage.query.get(img_id)
                    if img and img.note_id == note.id:
                        img.display_width = w
                except (ValueError, IndexError):
                    pass

        for img_id in json.loads(request.form.get('removed_image_ids', '[]')):
            img = NoteImage.query.get(img_id)
            if img and img.note_id == note.id:
                file_path = os.path.join(current_app.root_path, 'static', img.stored_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
                db.session.delete(img)

        for img_data in json.loads(request.form.get('new_images', '[]')):
            db.session.add(NoteImage(
                note_id=note.id,
                filename=img_data.get('name', ''),
                stored_path=img_data.get('path', ''),
                display_width=img_data.get('width'),
            ))

        db.session.commit()
        flash('笔记已更新', 'success')
        return redirect(url_for('notes.note_detail', id=note.id))

    existing_images = NoteImage.query.filter_by(note_id=note.id)\
        .order_by(NoteImage.uploaded_at).all()
    return render_template('notes/edit.html', form=form, note=note,
                          existing_images=existing_images)


@csrf.exempt
@bp.route('/<int:id>/delete', methods=['POST'])
@frontend_login_required
def note_delete(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        flash('无权操作', 'danger')
        return redirect(url_for('main.index'))
    book_id = note.book_id
    images = NoteImage.query.filter_by(note_id=note.id).all()
    for img in images:
        file_path = os.path.join(current_app.root_path, 'static', img.stored_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(img)
    db.session.delete(note)
    db.session.commit()
    flash('笔记已删除', 'success')
    return redirect(url_for('main.book_detail', id=book_id, _anchor='mynotes'))


@bp.route('/<int:id>/export/markdown')
@frontend_login_required
def export_markdown(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        abort(403)
    return Response(
        note.content or '',
        mimetype='text/markdown',
        headers={'Content-Disposition': f"attachment; filename=\"note.md\"; filename*=UTF-8''{quote(note.title + '.md')}"}
    )


@bp.route('/<int:id>/export/pdf')
@frontend_login_required
def export_pdf(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        abort(403)
    html = render_template('notes/export_pdf.html', note=note)
    return Response(
        html,
        mimetype='text/html',
        headers={'Content-Disposition': f"attachment; filename=\"note.html\"; filename*=UTF-8''{quote(note.title + '.html')}"}
    )


@bp.route('/upload-image', methods=['POST'])
@csrf.exempt
@frontend_login_required
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': '未选择文件'}), 400
    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': '不支持的文件格式'}), 400

    file.seek(0, os.SEEK_END)
    if file.tell() > 5 * 1024 * 1024:
        return jsonify({'error': '文件大小不能超过 5MB'}), 400
    file.seek(0)

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'notes')
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.rsplit('.', 1)[1].lower()
    new_name = f"{current_user.id}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}.{ext}"
    save_path = os.path.join(upload_dir, new_name)
    file.save(save_path)

    url = url_for('static', filename=f'uploads/notes/{new_name}')
    return jsonify({
        'url': url,
        'stored_path': f'uploads/notes/{new_name}',
        'original_name': secure_filename(file.filename),
    })
