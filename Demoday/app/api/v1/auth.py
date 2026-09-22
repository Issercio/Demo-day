from flask_restx import Namespace, Resource, fields
from flask import request, current_app
from sqlalchemy import func
from app.models.user import User
from app.extensions import db
from app.services.login_lockout import (
    clear_failed_logins,
    lockout_error,
    record_failed_login,
)
import jwt
from datetime import datetime, timedelta, timezone

api = Namespace('auth', description='Authentification')

login_model = api.model('Login', {
    'email': fields.String(required=True),
    'password': fields.String(required=True)
})

register_model = api.model('Register', {
    'username': fields.String(required=True),
    'email': fields.String(required=True),
    'password': fields.String(required=True)
})


def _issue_token(user):
    # `sub` = id utilisateur (Bearer). `is_admin` est informatif : le serveur relit la DB.
    # `exp` force la reconnexion après 24h.
    return jwt.encode(
        {
            'sub': str(user.id),
            'email': user.email,
            'is_admin': user.is_admin,
            'exp': datetime.now(timezone.utc) + timedelta(days=1),
        },
        current_app.config['SECRET_KEY'],
        algorithm='HS256',
    )


@api.route('/login')
class Login(Resource):
    @api.expect(login_model)
    def post(self):
        try:
            data = request.json or {}
            email = (data.get('email') or '').strip()
            password = data.get('password') or ''
            if not email or not password:
                return {'success': False, 'message': 'Email et mot de passe requis'}, 400

            user = User.query.filter(func.lower(User.email) == email.lower()).first()  # casse ignorée
            if user:
                blocked = lockout_error(user)
                if blocked:
                    return blocked
            if not user or not user.check_password(password):
                if user:
                    blocked = record_failed_login(user)
                    if blocked:
                        return blocked
                return {'success': False, 'message': 'Email ou mot de passe incorrect'}, 401

            clear_failed_logins(user)
            # Migration douce : bcrypt / mot de passe en clair → hash Werkzeug.
            if not user.has_modern_hash():
                user.set_password(password)
                db.session.commit()

            return {
                'success': True,
                'data': {
                    'token': _issue_token(user),
                    'user': user.to_dict()
                }
            }, 200

        except Exception:
            current_app.logger.exception('Erreur de login')
            return {'success': False, 'message': 'Erreur interne du serveur'}, 500


@api.route('/register')
class Register(Resource):
    @api.expect(register_model)
    def post(self):
        try:
            data = request.json or {}
            username = (data.get('username') or '').strip()
            email = (data.get('email') or '').strip()
            password = data.get('password') or ''

            if not username or not email or not password:
                return {'success': False, 'message': 'Tous les champs sont requis'}, 400

            if User.query.filter_by(email=email).first():
                return {'success': False, 'message': 'Email déjà utilisé'}, 400

            if User.query.filter_by(username=username).first():
                return {'success': False, 'message': 'Nom d\'utilisateur déjà pris'}, 400

            # Un client ne peut pas s'auto-promouvoir admin via le JSON d'inscription.
            user = User(
                username=username,
                email=email,
                password='x',  # NOT NULL ; le hash réel est posé par set_password juste après
                is_admin=False
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            return {
                'success': True,
                'data': {
                    'token': _issue_token(user),
                    'user': user.to_dict()
                }
            }, 201

        except Exception:
            current_app.logger.exception('Erreur de création de compte')
            db.session.rollback()
            return {'success': False, 'message': 'Erreur interne du serveur'}, 500
