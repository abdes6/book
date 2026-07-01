import logging
import requests
from flask import has_request_context
from flask_login import current_user

BASE_URL = 'https://i.weread.qq.com/api/agent/gateway'
SKILL_VERSION = '1.0.3'

logger = logging.getLogger(__name__)


def _headers():
    if has_request_context() and current_user.is_authenticated:
        key = getattr(current_user, 'weread_api_key', '') or ''
        if key:
            return {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    raise ValueError('微信读书 API Key 未设置，请在 个人中心 > 更新 API Key 中设置')


def _post(payload, api_key=None):
    """发送 POST 请求并处理错误。出错时返回空 dict。"""
    if api_key:
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    else:
        headers = _headers()
    try:
        resp = requests.post(BASE_URL, json=payload, headers=headers,
                             timeout=5, proxies={'http': '', 'https': ''})
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.warning('微信读书 API 超时: %s', payload.get('api_name', ''))
    except requests.exceptions.HTTPError as e:
        logger.warning('微信读书 API HTTP 错误 %s: %s', resp.status_code, str(e)[:200])
    except requests.exceptions.RequestException as e:
        logger.warning('微信读书 API 请求失败: %s', str(e)[:200])
    except ValueError as e:
        logger.warning('微信读书 API JSON 解析失败: %s', str(e)[:200])
    return {}


def get_shelf(api_key=None):
    return _post({
        'api_name': '/shelf/sync',
        'skill_version': SKILL_VERSION
    }, api_key=api_key)


def get_bookmarklist(book_id):
    return _post({
        'api_name': '/book/bookmarklist',
        'bookId': str(book_id),
        'skill_version': SKILL_VERSION
    })


def get_readdata(mode='monthly', base_time=0):
    return _post({
        'api_name': '/readdata/detail',
        'mode': mode,
        'baseTime': base_time,
        'skill_version': SKILL_VERSION
    })
