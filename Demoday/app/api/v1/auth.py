from flask_restx import Namespace, Resource, fields
from flask import request
from app.models.user import User
from werkzeug.security import check_password_hash

api = Namespace('auth', description='Authentification')

login_model = api.model('Login', {
    'email': fields.String(required=True, description="Adresse email"),
    'password': fields.String(required=True, description="Mot de passe")
})

user_public_model = api.model('UserPublic', {
    'id': fields.Integer(readOnly=True),
    'email': fields.String(required=True, description='Adresse email'),
    'first_name': fields.String(description='Prénom'),
    'last_name': fields.String(description='Nom'),
    'is_admin': fields.Boolean(description='Administrateur')
})

@api.route('/login')
class Login(Resource):
    @api.expect(login_model)
    @api.marshal_with(user_public_model)
    def post(self):
        """
        Authentifie un utilisateur par email et mot de passe.
        Retourne les infos publiques de l'utilisateur si succès, sinon 401.
        """
        data = request.json
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            api.abort(400, "Email and password required")

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            return user
        api.abort(401, "Invalid credentials")
