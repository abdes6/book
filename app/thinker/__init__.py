from flask import Blueprint

bp = Blueprint('thinker', __name__)

from app.thinker import routes
