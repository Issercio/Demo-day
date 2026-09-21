from functools import wraps

import jwt
from flask import current_app, jsonify, request

from app.extensions import db
from app.models.user import User

TOKENS = {}


def register_token(token, user_id):
    TOKENS[token] = user_id


def _extract_bearer_token():
    auth = request.headers.get('Authorization', '') or ''
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return auth.strip() or None  # JWT nu, sans préfixe Bearer


def get_token_payload():
    """Lit le JWT du header Authorization et vérifie la signature + l'expiration."""
    token = _extract_bearer_token()
    if not token:
        return None, ({'success': False, 'message': 'Authentification requise'}, 401)

    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])  # HS256 only : pas d'algo none
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, ({'success': False, 'message': 'Session expirée'}, 401)
    except Exception:
        return None, ({'success': False, 'message': 'Token invalide'}, 401)


def load_current_user():
    """Charge l'utilisateur en base. is_admin du JWT n'est jamais utilisé pour autoriser."""
    payload, error = get_token_payload()
    if error:
        return None, error
    try:
        user_id = int(payload.get('sub'))
    except (TypeError, ValueError):
        return None, ({'success': False, 'message': 'Token invalide'}, 401)
    user = db.session.get(User, user_id)
    if user is None:
        return None, ({'success': False, 'message': 'Utilisateur introuvable'}, 401)
    return user, None


def load_current_user_optional():
    """Comme load_current_user, mais sans token = visiteur (pas d'erreur 401)."""
    if not _extract_bearer_token():
        return None, None
    return load_current_user()


def admin_required_response():
    """401/403 si le JWT est invalide ou si is_admin en base est faux (pas le claim JWT)."""
    user, error = load_current_user()
    if error:
        body, status = error
        return jsonify(body), status
    if not user.is_admin:
        # is_admin lu en base, pas le claim JWT (un JWT falsifié ne suffit pas).
        return jsonify({'success': False, 'message': 'Accès réservé aux administrateurs'}), 403
    return None


def self_or_admin_required_response(user_id):
    """Propriétaire du compte ou fleuriste — les rôles viennent de la table users."""
    user, error = load_current_user()
    if error:
        body, status = error
        return jsonify(body), status
    if user.is_admin or str(user.id) == str(user_id):
        return None
    return jsonify({'success': False, 'message': 'Accès refusé'}), 403


def require_admin_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)  # preflight CORS : pas d'auth
        user, error = load_current_user()
        if error:
            return error
        if not user.is_admin:
            return {'success': False, 'message': 'Accès réservé aux administrateurs'}, 403
        return f(*args, **kwargs)
    return decorated


def require_self_or_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)  # preflight CORS : pas d'auth
        user, error = load_current_user()
        if error:
            return error
        user_id = kwargs.get('user_id')
        if user_id is None and len(args) >= 2:
            user_id = args[1]
        if user.is_admin or str(user.id) == str(user_id):
            return f(*args, **kwargs)
        return {'success': False, 'message': 'Accès refusé'}, 403
    return decorated
