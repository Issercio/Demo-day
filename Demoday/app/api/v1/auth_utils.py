from flask import request
from functools import wraps
from app.models.user import User

TOKENS = {}

def register_token(token, user_id):
    TOKENS[token] = user_id

def require_admin_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or token not in TOKENS:
            return {"message": "Token manquant ou invalide"}, 401
        user_id = TOKENS[token]
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return {"message": "Accès réservé aux administrateurs"}, 403
        return f(*args, **kwargs)
    return decorated
