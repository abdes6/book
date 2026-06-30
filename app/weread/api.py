import requests
from flask import current_app, has_request_context
from flask_login import current_user

BASE_URL = 'https://i.weread.qq.com/api/agent/gateway'
SKILL_VERSION = '1.0.3'


def _headers():
    key = ''
    if has_request_context() and current_user.is_authenticated:
        key = getattr(current_user, 'weread_api_key', '') or ''
    if not key:
        key = current_app.config.get('WEREAD_API_KEY', '')
    if not key:
        raise ValueError('微信读书 API Key 未设置，请在登录时填写')
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


def get_readdata(mode='monthly', base_time=0):
    return requests.post(BASE_URL, json={
        'api_name': '/readdata/detail',
        'mode': mode,
        'baseTime': base_time,
        'skill_version': SKILL_VERSION
    }, headers=_headers(), timeout=5, proxies={'http': '', 'https': ''}).json()
