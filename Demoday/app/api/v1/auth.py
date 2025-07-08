from flask_restx import Namespace, Resource, fields
from flask import request, current_app
from app.models.user import User
import jwt
from datetime import datetime, timedelta

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

@api.route('/login')
class Login(Resource):
    @api.expect(login_model)
    def post(self):
        try:
            data = request.json
            print(f"Tentative de connexion pour: {data['email']}")  # Debug log
            
            user = User.query.filter_by(email=data['email']).first()
            
            if not user:
                return {'success': False, 'message': 'Email ou mot de passe incorrect'}, 401

            if data['password'] != 'admin123':  # Temporaire pour le test
                return {'success': False, 'message': 'Email ou mot de passe incorrect'}, 401

            token = jwt.encode({
                'sub': str(user.id),
                'email': user.email,
                'is_admin': user.is_admin,
                'exp': datetime.utcnow() + timedelta(days=1)
            }, current_app.config['SECRET_KEY'])

            return {
                'success': True,
                'data': {
                    'token': token,
                    'user': user.to_dict()
                }
            }, 200

        except Exception as e:
            print(f"Erreur de login: {str(e)}")  # Debug log
            return {'success': False, 'message': str(e)}, 500

@api.route('/register')
class Register(Resource):
    @api.expect(register_model)
    def post(self):
        try:
            data = request.json
            print(f"Tentative de création de compte pour: {data.get('email')}")  # Debug log
            
            if not data or not data.get('username') or not data.get('email') or not data.get('password'):
                return {'success': False, 'message': 'Tous les champs sont requis'}, 400
            
            # Vérifier si l'utilisateur existe déjà
            existing_user = User.query.filter_by(email=data['email']).first()
            if existing_user:
                return {'success': False, 'message': 'Email déjà utilisé'}, 400
            
            existing_username = User.query.filter_by(username=data['username']).first()
            if existing_username:
                return {'success': False, 'message': 'Nom d\'utilisateur déjà pris'}, 400

            # Créer le nouvel utilisateur
            from werkzeug.security import generate_password_hash
            user = User(
                username=data['username'],
                email=data['email'],
                password=generate_password_hash(data['password']),
                is_admin=False
            )
            
            db.session.add(user)
            db.session.commit()

            return {
                'success': True,
                'data': {
                    'user': user.to_dict()
                }
            }, 201

        except Exception as e:
            print(f"Erreur de création de compte: {str(e)}")  # Debug log
            db.session.rollback()
            return {'success': False, 'message': 'Erreur interne du serveur'}, 500
