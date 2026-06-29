import requests
from flask import current_app

BASE_URL = 'https://i.weread.qq.com/api/agent/gateway'
SKILL_VERSION = '1.0.3'


def _headers():
    key = current_app.config.get('WEREAD_API_KEY', '')
    if not key:
        raise ValueError('请设置环境变量 WEREAD_API_KEY')
    return {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}


def get_shelf():
    return requests.post(BASE_URL, json={
        'api_name': '/shelf/sync',
        'skill_version': SKILL_VERSION
    }, headers=_headers(), timeout=5, proxies={'http': '', 'https': ''}).json()


def get_bookmarklist(book_id):
    return requests.post(BASE_URL, json={
        'api_name': '/book/bookmarklist',
        'bookId': str(book_id),
        'skill_version': SKILL_VERSION
    }, headers=_headers(), timeout=5, proxies={'http': '', 'https': ''}).json()
