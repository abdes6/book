# 图片附件 + 手动调大小 — 实现计划

> 将图片从 markdown 嵌入改为独立附件，支持编辑时选择展示尺寸，查看时点击放大。

**Goal:** 图片上传后不插入 textarea，以附件形式关联笔记；编辑时每张图片可选小/中/大尺寸；查看时点击放大预览。

**Architecture:** 前端 JS 管理图片列表 + 隐藏 JSON 字段传递；后端存 NoteImage 记录 + `display_size` 字段；详情页用 Bootstrap modal 做 lightbox。

---

### Task 1: 模型加字段 + 关系 + 迁移

**Files:** `app/models.py`

**Changes:**

1. `NoteImage` 类末尾添加 `display_size` 字段：
```python
display_size = db.Column(db.String(10), default='medium')
```

2. `NoteImage` 类末尾添加关系（实现 `note.images` 反向引用）：
```python
note_ref = db.relationship('Note', backref=db.backref('images', lazy='dynamic',
                            order_by='NoteImage.uploaded_at'))
```

3. 生成并运行迁移：
```powershell
flask db migrate -m "add display_size to note_image"
flask db upgrade
```

---

### Task 2: 修改 `upload_image` 返回值

**Files:** `app/notes/routes.py`

将第 117 行：
```python
return jsonify({'url': url, 'markdown': f'![]({url})'})
```

改为：
```python
return jsonify({
    'url': url,
    'stored_path': f'uploads/notes/{new_name}',
    'original_name': secure_filename(file.filename)
})
```

---

### Task 3: 修改 `note_create` 处理图片附件

**Files:** `app/notes/routes.py`

```python
@bp.route('/create/<int:book_id>', methods=['GET', 'POST'])
@frontend_login_required
def note_create(book_id):
    book = Book.query.get_or_404(book_id)
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

        import json
        for img_data in json.loads(request.form.get('attached_images', '[]')):
            db.session.add(NoteImage(
                note_id=note.id,
                filename=img_data.get('name', ''),
                stored_path=img_data.get('path', ''),
                display_size=img_data.get('size', 'medium'),
            ))
        db.session.commit()
        flash('笔记保存成功', 'success')
        return redirect(url_for('notes.note_detail', id=note.id))
    return render_template('notes/create.html', form=form, book=book)
```

---

### Task 4: 修改 `note_detail` 传图片

**Files:** `app/notes/routes.py`

在 `note_detail` 中，`note = Note.query.get_or_404(id)` 之后添加：
```python
images = NoteImage.query.filter_by(note_id=note.id).order_by(NoteImage.uploaded_at).all()
return render_template('notes/detail.html', note=note, images=images)
```

---

### Task 5: 修改 `note_edit` 支持图片增删改尺寸

**Files:** `app/notes/routes.py`

```python
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

        import json

        # 1. 更新已有图片的尺寸
        for key, val in request.form.items():
            if key.startswith('existing_size_'):
                img_id = int(key.split('_')[2])
                img = NoteImage.query.get(img_id)
                if img and img.note_id == note.id and val in ('small', 'medium', 'large'):
                    img.display_size = val

        # 2. 删除被移除的图片
        for img_id in json.loads(request.form.get('removed_image_ids', '[]')):
            img = NoteImage.query.get(img_id)
            if img and img.note_id == note.id:
                file_path = os.path.join(current_app.root_path, 'static', img.stored_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
                db.session.delete(img)

        # 3. 添加新上传的图片
        for img_data in json.loads(request.form.get('new_images', '[]')):
            db.session.add(NoteImage(
                note_id=note.id,
                filename=img_data.get('name', ''),
                stored_path=img_data.get('path', ''),
                display_size=img_data.get('size', 'medium'),
            ))

        db.session.commit()
        flash('笔记已更新', 'success')
        return redirect(url_for('notes.note_detail', id=note.id))

    existing_images = NoteImage.query.filter_by(note_id=note.id)\
        .order_by(NoteImage.uploaded_at).all()
    return render_template('notes/edit.html', form=form, note=note,
                          existing_images=existing_images)
```

---

### Task 6: 重写 `create.html`

**Files:** `app/templates/notes/create.html`

完整内容替换：

```html
{% extends 'base.html' %}
{% block title %}写笔记{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-lg-10">
        <h4 class="mb-3">为《{{ book.title }}》写笔记</h4>
        <form method="post">
            {{ form.hidden_tag() }}
            <div class="mb-3">
                {{ form.title.label(class='form-label') }}
                {{ form.title(class='form-control', placeholder='给这篇笔记起个标题') }}
                {% for e in form.title.errors %}<div class="text-danger">{{ e }}</div>{% endfor %}
            </div>
            <div class="mb-3">
                {{ form.content.label(class='form-label') }}
                {{ form.content(class='form-control', rows=20, placeholder='支持 Markdown 语法...', id='note-editor') }}
            </div>
            <div class="mb-3">
                <div class="d-flex align-items-center gap-2 mb-2">
                    <span class="form-label mb-0">附图</span>
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="document.getElementById('image-input').click()">+ 上传</button>
                    <input type="file" id="image-input" accept="image/*" style="display:none">
                </div>
                <div id="image-preview" class="d-flex flex-wrap gap-3"></div>
                <input type="hidden" name="attached_images" id="attached-images" value="[]">
            </div>
            {{ form.submit(class='btn btn-primary') }}
            <a href="{{ url_for('main.book_detail', id=book.id) }}" class="btn btn-outline-secondary">取消</a>
        </form>
    </div>
</div>
{% endblock %}
{% block scripts %}
<script>
var images = [];

document.getElementById('image-input').addEventListener('change', function(e) {
    var file = e.target.files[0];
    if (!file) return;
    var formData = new FormData();
    formData.append('image', file);
    fetch('{{ url_for("notes.upload_image") }}', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.url) {
            images.push({url: data.url, path: data.stored_path, name: data.original_name, size: 'medium'});
            renderPreview();
        }
    })
    .catch(function() { alert('上传失败'); });
});

function renderPreview() {
    var div = document.getElementById('image-preview');
    div.innerHTML = '';
    images.forEach(function(img, i) {
        var wrap = document.createElement('div');
        wrap.className = 'card';
        wrap.style.width = '160px';
        wrap.innerHTML =
            '<img src="' + img.url + '" style="height:100px;width:100%;object-fit:cover" class="card-img-top">'
            + '<div class="card-body p-2">'
            + '<select class="form-select form-select-sm mb-1" onchange="changeSize(' + i + ', this.value)">'
            + '<option value="small"' + (img.size==='small'?' selected':'') + '>小</option>'
            + '<option value="medium"' + (img.size==='medium'?' selected':'') + '>中</option>'
            + '<option value="large"' + (img.size==='large'?' selected':'') + '>大</option>'
            + '</select>'
            + '<button type="button" class="btn btn-sm btn-outline-danger w-100" onclick="removeImage(' + i + ')">删除</button>'
            + '</div>';
        div.appendChild(wrap);
    });
    syncHidden();
}

function changeSize(idx, val) {
    images[idx].size = val;
}

function removeImage(idx) {
    images.splice(idx, 1);
    renderPreview();
}

function syncHidden() {
    document.getElementById('attached-images').value = JSON.stringify(
        images.map(function(i) { return {path: i.path, name: i.name, size: i.size}; })
    );
}
</script>
{% endblock %}
```

---

### Task 7: 重写 `edit.html`

**Files:** `app/templates/notes/edit.html`

```html
{% extends 'base.html' %}
{% block title %}编辑笔记{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-lg-10">
        <h4 class="mb-3">编辑笔记</h4>
        <form method="post">
            {{ form.hidden_tag() }}
            <div class="mb-3">
                {{ form.title.label(class='form-label') }}
                {{ form.title(class='form-control') }}
                {% for e in form.title.errors %}<div class="text-danger">{{ e }}</div>{% endfor %}
            </div>
            <div class="mb-3">
                {{ form.content.label(class='form-label') }}
                {{ form.content(class='form-control', rows=20, id='note-editor') }}
            </div>
            <div class="mb-3">
                <div class="d-flex align-items-center gap-2 mb-2">
                    <span class="form-label mb-0">附图</span>
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="document.getElementById('image-input').click()">+ 上传</button>
                    <input type="file" id="image-input" accept="image/*" style="display:none">
                </div>
                <div id="image-preview" class="d-flex flex-wrap gap-3">
                    {% for img in existing_images %}
                    <div class="card existing-image" data-id="{{ img.id }}" style="width:160px">
                        <img src="{{ url_for('static', filename=img.stored_path) }}" style="height:100px;width:100%;object-fit:cover" class="card-img-top">
                        <div class="card-body p-2">
                            <select class="form-select form-select-sm mb-1" name="existing_size_{{ img.id }}">
                                <option value="small" {% if img.display_size == 'small' %}selected{% endif %}>小</option>
                                <option value="medium" {% if img.display_size == 'medium' %}selected{% endif %}>中</option>
                                <option value="large" {% if img.display_size == 'large' %}selected{% endif %}>大</option>
                            </select>
                            <button type="button" class="btn btn-sm btn-outline-danger w-100" onclick="removeExisting({{ img.id }})">删除</button>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                <input type="hidden" name="new_images" id="new-images" value="[]">
                <input type="hidden" name="removed_image_ids" id="removed-image-ids" value="[]">
            </div>
            {{ form.submit(class='btn btn-primary') }}
            <a href="{{ url_for('notes.note_detail', id=note.id) }}" class="btn btn-outline-secondary">取消</a>
        </form>
    </div>
</div>
{% endblock %}
{% block scripts %}
<script>
var newImages = [];
var removedIds = [];

document.getElementById('image-input').addEventListener('change', function(e) {
    var file = e.target.files[0];
    if (!file) return;
    var formData = new FormData();
    formData.append('image', file);
    fetch('{{ url_for("notes.upload_image") }}', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.url) {
            newImages.push({url: data.url, path: data.stored_path, name: data.original_name, size: 'medium'});
            renderNewPreview();
        }
    })
    .catch(function() { alert('上传失败'); });
});

function renderNewPreview() {
    var div = document.getElementById('image-preview');
    // Remove existing-image cards, keep only new-image cards
    newImages.forEach(function(img, i) {
        // Check if this image is already rendered
        if (document.querySelector('[data-new-idx="' + i + '"]')) return;
        var wrap = document.createElement('div');
        wrap.className = 'card';
        wrap.style.width = '160px';
        wrap.setAttribute('data-new-idx', i);
        wrap.innerHTML =
            '<img src="' + img.url + '" style="height:100px;width:100%;object-fit:cover" class="card-img-top">'
            + '<div class="card-body p-2">'
            + '<select class="form-select form-select-sm mb-1" onchange="changeNewSize(' + i + ', this.value)">'
            + '<option value="small">小</option><option value="medium" selected>中</option><option value="large">大</option>'
            + '</select>'
            + '<button type="button" class="btn btn-sm btn-outline-danger w-100" onclick="removeNewImage(' + i + ')">删除</button>'
            + '</div>';
        div.appendChild(wrap);
    });
    syncNewHidden();
}

function changeNewSize(idx, val) { newImages[idx].size = val; }

function removeNewImage(idx) { newImages.splice(idx, 1); document.querySelector('[data-new-idx="' + idx + '"]').remove(); syncNewHidden(); }

function removeExisting(imgId) {
    removedIds.push(imgId);
    document.querySelector('[data-id="' + imgId + '"]').style.display = 'none';
    document.getElementById('removed-image-ids').value = JSON.stringify(removedIds);
}

function syncNewHidden() {
    document.getElementById('new-images').value = JSON.stringify(
        newImages.map(function(i) { return {path: i.path, name: i.name, size: i.size}; })
    );
}
</script>
{% endblock %}
```

---

### Task 8: 修改 `detail.html` 展示图片 + Lightbox

**Files:** `app/templates/notes/detail.html`

在第 20 行 `{{ note.content|markdown|safe }}` 之后、返回按钮之前添加附图区：

```html
{% if images %}
<div class="mt-4">
    <h5>附图</h5>
    <div class="d-flex flex-wrap gap-3">
        {% for img in images %}
        {% set size_map = {'small':120, 'medium':250, 'large':400} %}
        {% set px = size_map[img.display_size] or 250 %}
        <a href="javascript:void(0)" onclick="showLightbox('{{ url_for('static', filename=img.stored_path) }}')">
            <img src="{{ url_for('static', filename=img.stored_path) }}"
                 alt="{{ img.filename }}"
                 style="max-height:{{ px }}px;max-width:100%"
                 class="rounded border">
        </a>
        {% endfor %}
    </div>
</div>
{% endif %}
```

并在模板底部 `{% endblock %}` 前添加 Lightbox 模态框 + 脚本：

```html
<div class="modal fade" id="lightboxModal" tabindex="-1">
    <div class="modal-dialog modal-xl modal-dialog-centered">
        <div class="modal-body text-center p-0">
            <img id="lightboxImage" src="" style="max-width:100%;max-height:90vh" class="rounded">
        </div>
    </div>
</div>

<script>
function showLightbox(src) {
    document.getElementById('lightboxImage').src = src;
    new bootstrap.Modal('#lightboxModal').show();
}
</script>
```

注意：需要确认 `base.html` 已经加载了 Bootstrap 5 JS（用于 Modal）。如果只用 CDN 的 `bootstrap.bundle.min.js` 则直接可用。

---

### Task 9: 重写 `book_notes` JSON 接口（预览截断方式）

**Files:** `app/notes/routes.py`

目前的 `book_notes` 返回 `preview: (n.content or '')[:100]`，可能截到图片描述。无内容时预览会为空。不需要改——因为图片不再嵌入 content，所以预览只显示文字，更干净。

但编辑页面跳转从图书详情页改为笔记详情页更好：

在 `app/templates/books/detail.html` 中，笔记列表的标题链接从：
```
{{ url_for("notes.note_detail", id=0) }}
```
改为直接链接到 `notes.note_detail`。这部分在之前的 Task 6 已经做了，不需要额外改。
```
