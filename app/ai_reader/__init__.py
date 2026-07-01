from flask import Blueprint
bp = Blueprint('ai_reader', __name__)
from app.ai_reader import routes
