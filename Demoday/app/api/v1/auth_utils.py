from functools import wraps

import jwt
from flask import current_app, jsonify, request

TOKENS = {}


def register_token(token, user_id):
    TOKENS[token] = user_id


def _extract_bearer_token():
    auth = request.headers.get('Authorization', '') or ''
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return auth.strip() or None


def get_token_payload():
    """Lit le JWT du header Authorization et vérifie la signature + l'expiration."""
    token = _extract_bearer_token()
    if not token:
        return None, ({'success': False, 'message': 'Authentification requise'}, 401)

    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, ({'success': False, 'message': 'Session expirée'}, 401)
    except Exception:
        return None, ({'success': False, 'message': 'Token invalide'}, 401)


def admin_required_response():
    """For blueprint views: JSON response if the caller is not an admin, else None."""
    payload, error = get_token_payload()
    if error:
        body, status = error
        return jsonify(body), status
    if not payload.get('is_admin'):
        return jsonify({'success': False, 'message': 'Accès réservé aux administrateurs'}), 403
    return None


def self_or_admin_required_response(user_id):
    """For blueprint views: allow the owner or an admin."""
    payload, error = get_token_payload()
    if error:
        body, status = error
        return jsonify(body), status
    if payload.get('is_admin') or str(payload.get('sub')) == str(user_id):
        return None
    return jsonify({'success': False, 'message': 'Accès refusé'}), 403


def require_admin_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
        payload, error = get_token_payload()
        if error:
            return error
        if not payload.get('is_admin'):
            return {'success': False, 'message': 'Accès réservé aux administrateurs'}, 403
        return f(*args, **kwargs)
    return decorated


def require_self_or_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
        payload, error = get_token_payload()
        if error:
            return error
        user_id = kwargs.get('user_id')
        if user_id is None and len(args) >= 2:
            user_id = args[1]
        if payload.get('is_admin') or str(payload.get('sub')) == str(user_id):
            return f(*args, **kwargs)
        return {'success': False, 'message': 'Accès refusé'}, 403
    return decorated
