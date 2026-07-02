"""
应用入口
-------
启动方式：python run.py 或通过 start.ps1 脚本调用。

执行流程：
1. 从 config.py 导入 Config（触发 .env 加载和 os.environ 填充）
2. 校验必需环境变量存在（SECRET_KEY / DATABASE_URL / DEEPSEEK_API_KEY）
3. 调用 create_app() 创建 Flask 实例
4. 以 debug 模式启动（由 FLASK_DEBUG 环境变量控制，默认关闭）
"""

import os
import sys

from config import Config  # 触发 config.py 顶层的 .env 加载逻辑

if __name__ == '__main__':
    # ── 启动前校验：必需环境变量不能为空 ──
    missing = []
    if not Config.SECRET_KEY:
        missing.append('SECRET_KEY')
    if not Config.SQLALCHEMY_DATABASE_URI:
        missing.append('DATABASE_URL')
    if not Config.DEEPSEEK_API_KEY:
        missing.append('DEEPSEEK_API_KEY')
    if missing:
        print(f'[FATAL] 缺少必需的环境变量: {", ".join(missing)}', file=sys.stderr)
        print('请创建 .env 文件并设置以上变量，参考 .env.example', file=sys.stderr)
        sys.exit(1)

    from app import create_app
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app = create_app()
    app.run(debug=debug)
