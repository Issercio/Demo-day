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
