"""
微信读书 API 集成层
------------------
通过统一的 Agent Gateway (https://i.weread.qq.com/api/agent/gateway) 调用微信读书后端。
所有请求携带 skill_version: "1.0.3" 和用户的 Bearer token 认证。

关键设计：
- _post() 是统一请求入口，封装了超时、HTTP 错误、网络异常的降级处理
- 失败时返回空 dict {}，调用方通过 if not data 安全短路
- get_shelf() 接受可选的 api_key 参数，用于无请求上下文的场景（如注册时导入）
"""

import logging
import requests
from flask import has_request_context
from flask_login import current_user

BASE_URL = 'https://i.weread.qq.com/api/agent/gateway'
SKILL_VERSION = '1.0.3'

logger = logging.getLogger(__name__)


def _headers():
    """
    从当前请求上下文获取用户的微信读书 API Key 构造认证头。
    仅在 Flask 请求上下文中可用；无上下文时调用方应传入 api_key 参数。
    """
    if has_request_context() and current_user.is_authenticated:
        key = getattr(current_user, 'weread_api_key', '') or ''
        if key:
            return {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    raise ValueError('微信读书 API Key 未设置，请在 个人中心 > 更新 API Key 中设置')


def _post(payload, api_key=None):
    """
    统一 POST 请求封装。
    - 超时 5 秒
    - 禁用系统代理（微信读书 API 需要直连）
    - 网络/HTTP/解析异常均捕获并返回空 dict
    """
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
    except requests.exceptions.HTTPError:
        logger.warning('微信读书 API HTTP 错误 %s: %s',
                       resp.status_code if 'resp' in dir() else '?',
                       payload.get('api_name', ''))
    except requests.exceptions.RequestException as e:
        logger.warning('微信读书 API 请求失败: %s', str(e)[:200])
    except ValueError as e:
        logger.warning('微信读书 API JSON 解析失败: %s', str(e)[:200])
    return {}


def get_shelf(api_key=None):
    """获取用户书架全部图书列表。"""
    return _post({
        'api_name': '/shelf/sync',
        'skill_version': SKILL_VERSION
    }, api_key=api_key)


def get_bookmarklist(book_id, api_key=None):
    """获取指定书籍的全部划线笔记（按章节组织）。"""
    return _post({
        'api_name': '/book/bookmarklist',
        'bookId': str(book_id),
        'skill_version': SKILL_VERSION
    }, api_key=api_key)


def get_book_info(book_id):
    """获取单本书的详细信息（含简介 intro）。"""
    return _post({
        'api_name': '/book/info',
        'bookId': str(book_id),
        'skill_version': SKILL_VERSION
    })


def get_readdata(mode='monthly', base_time=0):
    """
    获取阅读统计数据。
    mode: 'weekly' | 'monthly' | 'annually' | 'overall'
    base_time: Unix 时间戳，用于指定统计周期的基准时间
    """
    return _post({
        'api_name': '/readdata/detail',
        'mode': mode,
        'baseTime': base_time,
        'skill_version': SKILL_VERSION
    })
