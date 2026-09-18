from flask_restx import Namespace, Resource, fields
from flask import request
from app.extensions import db
from app.models.user import User
from app.api.v1.auth_utils import require_admin_token, require_self_or_admin

api = Namespace('users', description='Gestion des utilisateurs')

user_public_model = api.model('UserPublic', {
    'id': fields.Integer(readOnly=True),
    'username': fields.String(description='Nom d\'utilisateur'),
    'email': fields.String(required=True, description='Adresse email'),
    'is_admin': fields.Boolean(description='Administrateur')
})

user_create_model = api.model('UserCreate', {
    'username': fields.String(required=True, description='Nom d\'utilisateur'),
    'email': fields.String(required=True, description='Adresse email'),
    'password': fields.String(required=True, description='Mot de passe', min_length=6),
    'is_admin': fields.Boolean(description='Administrateur', default=False)
})

user_update_model = api.model('UserUpdate', {
    'username': fields.String(description='Nom d\'utilisateur'),
    'email': fields.String(description='Adresse email'),
    'password': fields.String(description='Mot de passe', min_length=6),
    'is_admin': fields.Boolean(description='Administrateur')
})


@api.route('')
class UserList(Resource):
    @api.marshal_list_with(user_public_model)
    @require_admin_token
    def get(self):
        """Liste tous les utilisateurs (admin uniquement)"""
        return User.query.all()

    @api.expect(user_create_model)
    @api.marshal_with(user_public_model, code=201)
    @require_admin_token
    def post(self):
        """Crée un nouvel utilisateur (admin uniquement)."""
        data = api.payload or {}
        username = (data.get('username') or '').strip()
        email = (data.get('email') or '').strip()
        password = data.get('password') or ''
        if not username or not email or not password:
            api.abort(400, "username, email et password sont obligatoires.")
        if User.query.filter_by(email=email).first():
            api.abort(409, "Un utilisateur avec cet email existe déjà")
        if User.query.filter_by(username=username).first():
            api.abort(409, "Nom d'utilisateur déjà pris")

        user = User(
            username=username,
            email=email,
            password='x',
            is_admin=bool(data.get('is_admin', False))
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user, 201


@api.route('/<int:user_id>')
class UserResource(Resource):
    @api.marshal_with(user_public_model)
    @require_self_or_admin
    def get(self, user_id):
        user = db.session.get(User, user_id)
        if user is None:
            api.abort(404, 'Utilisateur introuvable')
        return user

    @api.expect(user_update_model)
    @api.marshal_with(user_public_model)
    @require_admin_token
    def put(self, user_id):
        user = db.session.get(User, user_id)
        if user is None:
            api.abort(404, 'Utilisateur introuvable')
        data = api.payload or {}
        if 'username' in data:
            user.username = data['username']
        if 'email' in data:
            user.email = data['email']
        if 'password' in data:
            user.set_password(data['password'])
        if 'is_admin' in data:
            user.is_admin = data['is_admin']
        db.session.commit()
        return user

    @require_self_or_admin
    def delete(self, user_id):
        user = db.session.get(User, user_id)
        if user is None:
            api.abort(404, 'Utilisateur introuvable')
        db.session.delete(user)
        db.session.commit()
        return {'message': 'Utilisateur supprimé'}
