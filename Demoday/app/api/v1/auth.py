from flask_restx import Namespace, Resource, fields
from flask import request, current_app
from sqlalchemy import func
from app.models.user import User
from app.extensions import db
from app.api.v1.auth_utils import load_current_user
from app.services.login_lockout import (
    clear_failed_logins,
    lockout_error,
    record_failed_login,
)
from app.services.account_verification import (
    CHANNELS,
    check_code,
    clear_code,
    issue_code,
    normalize_phone,
)
import jwt
from datetime import datetime, timedelta, timezone

api = Namespace('auth', description='Authentification')

login_model = api.model('Login', {
    'email': fields.String(description="Email ou nom d'utilisateur"),
    'username': fields.String(description="Nom d'utilisateur (alternative à email)"),
    'password': fields.String(required=True)
})

register_model = api.model('Register', {
    'username': fields.String(required=True),
    'email': fields.String(required=True),
    'password': fields.String(required=True),
    'phone': fields.String(description='Optionnel, pour un code SMS'),
    'channel': fields.String(description='email ou sms'),
})

verify_model = api.model('Verify', {
    'email': fields.String(required=True),
    'code': fields.String(required=True),
})

resend_model = api.model('ResendCode', {
    'email': fields.String(required=True),
    'channel': fields.String,
    'phone': fields.String,
})

forgot_model = api.model('ForgotPassword', {
    'email': fields.String(required=True),
    'channel': fields.String,
})

reset_model = api.model('ResetPassword', {
    'email': fields.String(required=True),
    'code': fields.String(required=True),
    'new_password': fields.String(required=True),
})

change_model = api.model('ChangePassword', {
    'current_password': fields.String(required=True),
    'new_password': fields.String(required=True),
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


def _demo_payload(code):
    # En classe : le code est visible comme la carte 4242. En prod : MAIL_SERVER l'envoie.
    return {
        'demo_code': code,
        'demo_hint': 'Mode démo (pas de SMTP/SMS opérateur) : entrez ce code à 6 chiffres.',
    }


@api.route('/login')
class Login(Resource):
    @api.expect(login_model)
    def post(self):
        try:
            data = request.json or {}
            identifier = (data.get('email') or data.get('username') or '').strip()
            password = data.get('password') or ''
            if not identifier or not password:
                return {'success': False, 'message': 'Identifiant et mot de passe requis'}, 400

            # Après inscription on se connecte au nom d'utilisateur ; l'email reste accepté.
            user = User.query.filter(func.lower(User.email) == identifier.lower()).first()
            if user is None:
                user = User.query.filter_by(username=identifier).first()
            if user is None:
                user = User.query.filter(func.lower(User.username) == identifier.lower()).first()
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

            if not user.email_verified:
                return {
                    'success': False,
                    'needs_verification': True,
                    'email': user.email,
                    'message': 'Compte non vérifié. Entrez le code reçu par email ou SMS.',
                }, 403

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
            channel = (data.get('channel') or 'email').strip().lower()
            if channel not in CHANNELS:
                channel = 'email'

            if not username or not email or not password:
                return {'success': False, 'message': 'Tous les champs sont requis'}, 400
            if len(password) < 6:
                return {'success': False, 'message': 'Mot de passe trop court (6 caractères min.)'}, 400

            phone = normalize_phone(data.get('phone'))
            if phone is False:
                return {'success': False, 'message': 'Numéro de téléphone invalide'}, 400
            if channel == 'sms' and not phone:
                return {'success': False, 'message': 'Un numéro est requis pour un code SMS'}, 400

            if User.query.filter_by(email=email).first():
                return {'success': False, 'message': 'Email déjà utilisé'}, 400

            if User.query.filter_by(username=username).first():
                return {'success': False, 'message': 'Nom d\'utilisateur déjà pris'}, 400

            # Un client ne peut pas s'auto-promouvoir admin via le JSON d'inscription.
            user = User(
                username=username,
                email=email,
                password='x',  # NOT NULL ; le hash réel est posé par set_password juste après
                is_admin=False,
                email_verified=False,
                phone=phone,
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()
            code = issue_code(user, channel=channel, purpose='verify')

            return {
                'success': True,
                'data': {
                    'user': user.to_dict(),
                    **_demo_payload(code),
                }
            }, 201

        except Exception:
            current_app.logger.exception('Erreur de création de compte')
            db.session.rollback()
            return {'success': False, 'message': 'Erreur interne du serveur'}, 500


@api.route('/verify')
class Verify(Resource):
    @api.expect(verify_model)
    def post(self):
        data = request.json or {}
        email = (data.get('email') or '').strip()
        code = (data.get('code') or '').strip()
        if not email or not code:
            return {'success': False, 'message': 'Email et code requis'}, 400
        user = User.query.filter(func.lower(User.email) == email.lower()).first()
        if not user or not check_code(user, code, purpose='verify'):
            return {'success': False, 'message': 'Code invalide ou expiré'}, 400
        user.email_verified = True
        clear_code(user)
        db.session.commit()
        return {
            'success': True,
            'data': {
                'token': _issue_token(user),
                'user': user.to_dict(),
            },
        }, 200


@api.route('/resend-code')
class ResendCode(Resource):
    @api.expect(resend_model)
    def post(self):
        data = request.json or {}
        email = (data.get('email') or '').strip()
        channel = (data.get('channel') or 'email').strip().lower()
        if channel not in CHANNELS:
            channel = 'email'
        user = User.query.filter(func.lower(User.email) == email.lower()).first() if email else None
        # Message générique : on ne révèle pas si l'email existe.
        generic = {'success': True, 'message': 'Si un compte existe, un nouveau code a été envoyé.'}
        if not user:
            return generic, 200
        phone = normalize_phone(data.get('phone'))
        if phone is False:
            return {'success': False, 'message': 'Numéro de téléphone invalide'}, 400
        if phone:
            user.phone = phone
        if channel == 'sms' and not user.phone:
            return {'success': False, 'message': 'Un numéro est requis pour un code SMS'}, 400
        purpose = 'verify' if not user.email_verified else (user.verify_purpose or 'verify')
        code = issue_code(user, channel=channel, purpose=purpose if purpose in ('verify', 'reset') else 'verify')
        return {**generic, **_demo_payload(code), 'channel': channel}, 200


@api.route('/forgot-password')
class ForgotPassword(Resource):
    @api.expect(forgot_model)
    def post(self):
        data = request.json or {}
        email = (data.get('email') or '').strip()
        channel = (data.get('channel') or 'email').strip().lower()
        if channel not in CHANNELS:
            channel = 'email'
        generic = {
            'success': True,
            'message': 'Si un compte existe pour cet email, un code de réinitialisation a été envoyé.',
        }
        user = User.query.filter(func.lower(User.email) == email.lower()).first() if email else None
        if not user:
            return generic, 200
        if channel == 'sms' and not user.phone:
            channel = 'email'
        code = issue_code(user, channel=channel, purpose='reset')
        return {**generic, **_demo_payload(code), 'email': user.email}, 200


@api.route('/reset-password')
class ResetPassword(Resource):
    @api.expect(reset_model)
    def post(self):
        data = request.json or {}
        email = (data.get('email') or '').strip()
        code = (data.get('code') or '').strip()
        new_password = data.get('new_password') or ''
        if not email or not code or not new_password:
            return {'success': False, 'message': 'Email, code et nouveau mot de passe requis'}, 400
        if len(new_password) < 6:
            return {'success': False, 'message': 'Mot de passe trop court (6 caractères min.)'}, 400
        user = User.query.filter(func.lower(User.email) == email.lower()).first()
        if not user or not check_code(user, code, purpose='reset'):
            return {'success': False, 'message': 'Code invalide ou expiré'}, 400
        user.set_password(new_password)
        clear_code(user)
        clear_failed_logins(user)
        db.session.commit()
        return {'success': True, 'message': 'Mot de passe mis à jour. Vous pouvez vous connecter.'}, 200


@api.route('/change-password')
class ChangePassword(Resource):
    @api.expect(change_model)
    def post(self):
        user, error = load_current_user()
        if error:
            return error
        data = request.json or {}
        current_password = data.get('current_password') or ''
        new_password = data.get('new_password') or ''
        if not current_password or not new_password:
            return {'success': False, 'message': 'Mot de passe actuel et nouveau requis'}, 400
        if len(new_password) < 6:
            return {'success': False, 'message': 'Mot de passe trop court (6 caractères min.)'}, 400
        if not user.check_password(current_password):
            return {'success': False, 'message': 'Mot de passe actuel incorrect'}, 401
        user.set_password(new_password)
        db.session.commit()
        return {'success': True, 'message': 'Mot de passe modifié.', 'user': user.to_dict()}, 200
