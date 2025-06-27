from flask_restx import Namespace, Resource, fields
from flask import request
from app.models.user import User
from werkzeug.security import check_password_hash
import secrets
from app.api.v1.auth_utils import register_token

api = Namespace('auth', description='Authentification')

login_model = api.model('Login', {
    'username': fields.String(required=True, description="Nom d'utilisateur"),
    'password': fields.String(required=True, description="Mot de passe")
})

token_model = api.model('Token', {
    'token': fields.String(description="Token d'authentification"),
    'is_admin': fields.Boolean(description="Utilisateur admin"),
    'user_id': fields.Integer(description="ID utilisateur"),
    'username': fields.String(description="Nom d'utilisateur")
})

@api.route('/login')
class Login(Resource):
    @api.expect(login_model)
    @api.marshal_with(token_model)
    def post(self):
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            api.abort(400, "Username and password required")

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            token = secrets.token_hex(16)
            register_token(token, user.id)
            return {
                'token': token,
                'is_admin': user.is_admin,
                'user_id': user.id,
                'username': user.username
            }
        api.abort(401, "Invalid credentials")
