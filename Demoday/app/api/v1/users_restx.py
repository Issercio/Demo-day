from flask_restx import Namespace, Resource, fields
from flask import request, current_app
from app.extensions import db
from app.models.user import User
from werkzeug.security import generate_password_hash

api = Namespace('users', description='Gestion des utilisateurs')

user_public_model = api.model('UserPublic', {
    'id': fields.Integer(readOnly=True),
    'username': fields.String(required=True, description='Nom d\'utilisateur'),
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
    def get(self):
        """Liste tous les utilisateurs (admin uniquement)"""
        return User.query.all()

    @api.expect(user_create_model)
    @api.marshal_with(user_public_model, code=201)
    def post(self):
        """Crée un nouvel utilisateur (admin seulement si token admin)"""
        data = api.payload
        # Vérification stricte de tous les champs obligatoires
        if not data.get('username') or not data.get('email') or not data.get('password'):
            api.abort(400, "Les champs username, email et password sont obligatoires.")
        if User.query.filter_by(username=data['username']).first():
            api.abort(409, "Un utilisateur avec ce nom existe déjà")
        if User.query.filter_by(email=data['email']).first():
            api.abort(409, "Un utilisateur avec cet email existe déjà")

        if data.get('is_admin', False):
            auth_header = request.headers.get('Authorization')
            if not auth_header or auth_header != f"Bearer {current_app.config['ADMIN_TOKEN']}":
                api.abort(401, "Token admin requis pour créer un utilisateur admin.")

        user = User(
            username=data['username'],
            email=data['email'],
            password=generate_password_hash(data['password']),
            is_admin=data.get('is_admin', False)
        )
        db.session.add(user)
        db.session.commit()
        return user, 201

@api.route('/<int:user_id>')
class UserResource(Resource):
    @api.marshal_with(user_public_model)
    def get(self, user_id):
        """Affiche un utilisateur (admin uniquement)"""
        return User.query.get_or_404(user_id)

    @api.expect(user_update_model)
    @api.marshal_with(user_public_model)
    def put(self, user_id):
        """Modifie un utilisateur (admin uniquement)"""
        user = User.query.get_or_404(user_id)
        data = api.payload
        if 'username' in data:
            user.username = data['username']
        if 'email' in data:
            user.email = data['email']
        if 'password' in data:
            user.password = generate_password_hash(data['password'])
        if 'is_admin' in data:
            user.is_admin = data['is_admin']
        db.session.commit()
        return user

    def delete(self, user_id):
        """Supprime un utilisateur (admin uniquement)"""
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return {'message': 'Utilisateur supprimé'}
