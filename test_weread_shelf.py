import sys
sys.stdout.reconfigure(encoding='utf-8')

from flask import Flask
from config import Config
import requests

app = Flask(__name__)
app.config.from_object(Config)

BASE_URL = 'https://i.weread.qq.com/api/agent/gateway'

passed = 0
failed = 0

def test(name, ok, detail=''):
    global passed, failed
    if ok:
        passed += 1
        print(f'  ✅ {name}')
    else:
        failed += 1
        msg = f'  ❌ {name}'
        if detail:
            msg += f' — {detail}'
        print(msg)


print('=== 微信读书书架测试 ===\n')

with app.app_context():
    key = app.config.get('WEREAD_API_KEY', '')
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    payload = {'api_name': '/shelf/sync', 'skill_version': '1.0.3'}

    # 1. API Key
    test('WEREAD_API_KEY 已配置', bool(key))

    # 2. API 调用
    try:
        resp = requests.post(BASE_URL, json=payload, headers=headers,
                             timeout=10, proxies={'http': '', 'https': ''})
        test('API 调用成功 (HTTP 200)', resp.status_code == 200, f'状态码={resp.status_code}')
        data = resp.json()
    except Exception as e:
        test(f'API 调用失败', False, str(e))
        data = {}

    if data:
        books = data.get('books', [])
        albums = data.get('albums', [])
        mp = data.get('mp')

        # 3. 书架结构
        test('books 字段存在且为列表',
             isinstance(books, list), f'类型={type(books).__name__}')
        test('albums 字段存在且为列表',
             isinstance(albums, list), f'类型={type(albums).__name__}')
        test('mp 字段存在', 'mp' in data)
        test(f'电子书: {len(books)} 本', True)
        if albums:
            test(f'有声书/专辑: {len(albums)} 本', True)
        if mp:
            test('文章收藏: 有', True)

        # 4. 书籍字段完整性（取前 3 本检查）
        sample = books[:3]
        for i, b in enumerate(sample):
            test(f'书[{i+1}] title 不为空',
                 bool(b.get('title')), repr(b.get('title')))
            test(f'书[{i+1}] author 不为空',
                 bool(b.get('author')), repr(b.get('author')))
            test(f'书[{i+1}] cover 不为空',
                 bool(b.get('cover')), b.get('cover', '')[:50])
            test(f'书[{i+1}] bookId 不为空',
                 bool(b.get('bookId')), b.get('bookId', ''))
            test(f'书[{i+1}] finishReading 存在',
                 'finishReading' in b)

        # 5. 状态统计
        finished = sum(1 for b in books if b.get('finishReading'))
        reading = len(books) - finished
        test(f'已读完: {finished} 本', True)
        test(f'阅读中: {reading} 本', True)

        # 6. 打印书架前 5 本
        print()
        print(f'--- 书架前 5 本 (共 {len(books)} 本) ---')
        for i, b in enumerate(books[:5]):
            status = '已读完 ✅' if b.get('finishReading') else '阅读中 📖'
            print(f'  {i+1}. 《{b.get("title", "?")}》 {b.get("author", "?")} — {status}')

    # 7. 汇总
    total = passed + failed
    print(f'\n=== 测试结果: {passed}/{total} 通过', end='')
    if failed > 0:
        print(f', {failed} 失败 ❌')
        sys.exit(1)
    else:
        print(' ✅')
        sys.exit(0)
