from app.weread import bp


@bp.route('/ping')
def ping():
    return 'ok'
