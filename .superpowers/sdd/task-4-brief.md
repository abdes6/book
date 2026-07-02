### Task 4: 前端模板

**Files:**
- Create: `app/templates/ai_reader/index.html`

**Produces:** 主页面

- [ ] **Step 1: 创建 `app/templates/ai_reader/index.html`**

```html
{% extends 'base.html' %}
{% block title %}AI 读书助手{% endblock %}
{% block content %}
<div class="row" style="height:calc(100vh - 120px);">
  <div class="col-3 border-end overflow-auto" style="background:var(--cream);">
    <h5 class="my-3">📚 选择书籍</h5>
    <input type="text" id="book-search" class="form-control mb-3" placeholder="搜索书名/作者...">
    <div id="book-list" class="list-group"></div>
  </div>
  <div class="col-9 d-flex flex-column">
    <div id="placeholder" class="text-center text-muted mt-5 flex-grow-1">
      <h4>请从左侧选择一本书</h4>
      <p>选中后即可使用 AI 对话、摘要、书评、分析、推荐功能</p>
    </div>
    <div id="ai-panel" class="d-none flex-grow-1 d-flex flex-column">
      <ul class="nav nav-tabs" id="aiTabs">
        <li class="nav-item"><button class="nav-link active" data-tab="chat">对话</button></li>
        <li class="nav-item"><button class="nav-link" data-tab="summary">摘要</button></li>
        <li class="nav-item"><button class="nav-link" data-tab="review">书评</button></li>
        <li class="nav-item"><button class="nav-link" data-tab="analysis">分析</button></li>
        <li class="nav-item"><button class="nav-link" data-tab="recommend">推荐</button></li>
      </ul>
      <div class="tab-content flex-grow-1 d-flex flex-column overflow-auto p-3" id="aiTabContent">
        <div class="tab-pane active d-flex flex-column flex-grow-1" id="tab-chat">
          <div id="chat-messages" class="flex-grow-1 overflow-auto mb-3"></div>
          <div class="input-group">
            <input type="text" id="chat-input" class="form-control" placeholder="输入你的问题...">
            <button class="btn btn-primary" id="chat-send">发送</button>
          </div>
        </div>
        <div class="tab-pane d-none" id="tab-summary"><div class="ai-content"></div></div>
        <div class="tab-pane d-none" id="tab-review"><div class="ai-content"></div></div>
        <div class="tab-pane d-none" id="tab-analysis"><div class="ai-content"></div></div>
        <div class="tab-pane d-none" id="tab-recommend"><div class="ai-content"></div></div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
{% block scripts %}
<script>
(function(){
  var currentBookId = null;

  fetch('{{ url_for("ai_reader.book_list") }}').then(function(r){ return r.json(); }).then(function(books){
    var el = document.getElementById('book-list');
    books.forEach(function(b){
      var a = document.createElement('a');
      a.className = 'list-group-item list-group-item-action';
      a.href = '#';
      a.dataset.id = b.id;
      a.innerHTML = '<strong>' + escapeHtml(b.title) + '</strong><br><small>' + escapeHtml(b.author) + '</small>';
      a.addEventListener('click', function(e){
        e.preventDefault();
        selectBook(b.id, b.title);
        document.querySelectorAll('#book-list .active').forEach(function(x){ x.classList.remove('active'); });
        a.classList.add('active');
      });
      el.appendChild(a);
    });
  });

  document.getElementById('book-search').addEventListener('input', function(){
    var q = this.value.toLowerCase();
    document.querySelectorAll('#book-list .list-group-item').forEach(function(item){
      item.style.display = item.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });

  document.querySelectorAll('#aiTabs .nav-link').forEach(function(tab){
    tab.addEventListener('click', function(){
      document.querySelectorAll('#aiTabs .nav-link').forEach(function(t){ t.classList.remove('active'); });
      tab.classList.add('active');
      document.querySelectorAll('.tab-pane').forEach(function(p){ p.classList.add('d-none'); });
      var target = document.getElementById('tab-' + tab.dataset.tab);
      target.classList.remove('d-none');
      if(currentBookId) loadTabContent(tab.dataset.tab, currentBookId, target);
    });
  });

  document.getElementById('chat-send').addEventListener('click', sendChat);
  document.getElementById('chat-input').addEventListener('keydown', function(e){
    if(e.key === 'Enter') sendChat();
  });

  function selectBook(id, title){
    currentBookId = id;
    document.getElementById('placeholder').classList.add('d-none');
    var panel = document.getElementById('ai-panel');
    panel.classList.remove('d-none');
    document.getElementById('chat-messages').innerHTML = '';
    document.getElementById('chat-input').value = '';
    document.querySelectorAll('.ai-content').forEach(function(el){ el.innerHTML = ''; });
    document.getElementById('tab-chat').classList.remove('d-none');
    document.querySelectorAll('.tab-pane').forEach(function(p){
      if(p.id !== 'tab-chat') p.classList.add('d-none');
    });
    document.querySelectorAll('#aiTabs .nav-link').forEach(function(t){
      t.classList.toggle('active', t.dataset.tab === 'chat');
    });
    fetch('/ai-reader/' + id + '/chat').then(function(r){ return r.json(); }).then(function(data){
      if(data.messages){
        var el = document.getElementById('chat-messages');
        data.messages.forEach(function(m){
          addChatBubble(m.role, m.content);
        });
      }
    });
  }

  function loadTabContent(tab, bookId, targetEl){
    if(targetEl.dataset.loaded) return;
    targetEl.innerHTML = '<div class="text-center py-5"><div class="spinner-border"></div><p class="mt-2 text-muted">正在生成...</p></div>';
    fetch('/ai-reader/' + bookId + '/' + tab).then(function(r){ return r.json(); }).then(function(data){
      targetEl.dataset.loaded = '1';
      if(data.error){
        targetEl.innerHTML = '<div class="alert alert-warning">' + escapeHtml(data.error) + '</div>';
      } else {
        var html = data.content ? '<div class="p-3 rounded" style="background:var(--cream);white-space:pre-wrap;">' + escapeHtml(data.content) + '</div>' : '';
        if(data.recommendations){
          html = data.recommendations.map(function(r){
            return '<div class="card mb-2"><div class="card-body">' + escapeHtml(r) + '</div></div>';
          }).join('');
        }
        html += '<div class="mt-2"><button class="btn btn-sm btn-outline-secondary" onclick="regenerate(this,\'' + tab + '\',' + bookId + ')">重新生成</button></div>';
        targetEl.innerHTML = html;
      }
    }).catch(function(){
      targetEl.innerHTML = '<div class="alert alert-danger">加载失败</div>';
    });
  }

  function regenerate(btn, tab, bookId){
    var target = btn.closest('.tab-pane');
    target.dataset.loaded = '';
    loadTabContent(tab, bookId, target);
  }

  function sendChat(){
    if(!currentBookId) return;
    var input = document.getElementById('chat-input');
    var msg = input.value.trim();
    if(!msg) return;
    input.value = '';
    addChatBubble('user', msg);
    var el = document.getElementById('chat-messages');
    var loading = document.createElement('div');
    loading.className = 'text-muted py-2';
    loading.textContent = 'AI 正在思考...';
    el.appendChild(loading);
    el.scrollTop = el.scrollHeight;
    fetch('/ai-reader/' + currentBookId + '/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg})
    }).then(function(r){ return r.json(); }).then(function(data){
      loading.remove();
      if(data.error){
        addChatBubble('assistant', '⚠️ ' + data.error);
      } else {
        addChatBubble('assistant', data.reply);
      }
    }).catch(function(){
      loading.remove();
      addChatBubble('assistant', '⚠️ 网络错误，请重试');
    });
  }

  function addChatBubble(role, text){
    var el = document.getElementById('chat-messages');
    var div = document.createElement('div');
    div.className = 'mb-2 p-2 rounded ' + (role === 'user' ? 'text-end' : '');
    div.style.background = role === 'user' ? 'var(--accent)' : 'var(--cream)';
    div.style.whiteSpace = 'pre-wrap';
    div.textContent = text;
    el.appendChild(div);
    el.scrollTop = el.scrollHeight;
  }

  function escapeHtml(text){
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(text));
    return d.innerHTML;
  }
})();
</script>
{% endblock %}
```

---

