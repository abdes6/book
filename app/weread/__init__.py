from flask import Blueprint

bp = Blueprint('weread', __name__)

from app.weread import routes
