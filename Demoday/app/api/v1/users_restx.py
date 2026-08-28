from flask_restx import Namespace, Resource, fields
from flask import request, current_app
from app.extensions import db
from app.models.user import User
from werkzeug.security import generate_password_hash

api = Namespace('users', description='Gestion des utilisateurs')

user_public_model = api.model('UserPublic', {
    'id': fields.Integer(readOnly=True),
    'email': fields.String(required=True, description='Adresse email'),
    'first_name': fields.String(required=True, description='Prénom'),
    'last_name': fields.String(required=True, description='Nom'),
    'is_admin': fields.Boolean(description='Administrateur')
})

user_create_model = api.model('UserCreate', {
    'email': fields.String(required=True, description='Adresse email'),
    'password': fields.String(required=True, description='Mot de passe', min_length=6),
    'first_name': fields.String(required=True, description='Prénom'),
    'last_name': fields.String(required=True, description='Nom'),
    'is_admin': fields.Boolean(description='Administrateur', default=False)
})

user_update_model = api.model('UserUpdate', {
    'email': fields.String(description='Adresse email'),
    'password': fields.String(description='Mot de passe', min_length=6),
    'first_name': fields.String(description='Prénom'),
    'last_name': fields.String(description='Nom'),
    'is_admin': fields.Boolean(description='Administrateur')
})

@api.route('')
class UserList(Resource):
    @api.marshal_list_with(user_public_model)
    # @require_admin_token  # Active si tu veux restreindre la liste aux admins
    def get(self):
        """Liste tous les utilisateurs (admin uniquement)"""
        return User.query.all()

    @api.expect(user_create_model)
    @api.marshal_with(user_public_model, code=201)
    def post(self):
        """Crée un nouvel utilisateur (admin seulement si token admin)"""
        data = api.payload
        # Vérification stricte de tous les champs obligatoires
        if not data.get('email') or not data.get('password') or not data.get('first_name') or not data.get('last_name'):
            api.abort(400, "Tous les champs sont obligatoires sauf is_admin.")
        if User.query.filter_by(email=data['email']).first():
            api.abort(409, "Un utilisateur avec cet email existe déjà")

        # Si on veut créer un admin, il faut fournir le bon token dans l'en-tête Authorization
        if data.get('is_admin', False):
            auth_header = request.headers.get('Authorization')
            print("Authorization header reçu:", auth_header)  # DEBUG
            print("Attendu:", f"Bearer {current_app.config['ADMIN_TOKEN']}")  # DEBUG
            if not auth_header or auth_header != f"Bearer {current_app.config['ADMIN_TOKEN']}":
                api.abort(401, "Token admin requis pour créer un utilisateur admin.")

        user = User(
            email=data['email'],
            password=generate_password_hash(data['password']),
            first_name=data['first_name'],
            last_name=data['last_name'],
            is_admin=data.get('is_admin', False)
        )
        db.session.add(user)
        db.session.commit()
        return user, 201

@api.route('/<int:user_id>')
class UserResource(Resource):
    @api.marshal_with(user_public_model)
    # @require_admin_token
    def get(self, user_id):
        """Affiche un utilisateur (admin uniquement)"""
        return User.query.get_or_404(user_id)

    @api.expect(user_update_model)
    @api.marshal_with(user_public_model)
    # @require_admin_token
    def put(self, user_id):
        """Modifie un utilisateur (admin uniquement)"""
        user = User.query.get_or_404(user_id)
        data = api.payload
        if 'email' in data:
            user.email = data['email']
        if 'password' in data:
            user.password = generate_password_hash(data['password'])
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'is_admin' in data:
            user.is_admin = data['is_admin']
        db.session.commit()
        return user

    # @require_admin_token
    def delete(self, user_id):
        """Supprime un utilisateur (admin uniquement)"""
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return {'message': 'Utilisateur supprimé'}
