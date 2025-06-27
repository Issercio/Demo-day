from flask_restx import Namespace, Resource, fields
from app.extensions import db
from app.models.user import User
from werkzeug.security import generate_password_hash
from app.api.v1.auth_utils import require_admin_token

api = Namespace('users', description='Gestion des utilisateurs')

# Modèle public (jamais de mot de passe dans les réponses)
user_public_model = api.model('UserPublic', {
    'id': fields.Integer(readOnly=True),
    'username': fields.String(required=True, description='Nom d\'utilisateur'),
    'email': fields.String(required=True, description='Adresse email'),
    'is_admin': fields.Boolean(description='Administrateur')
})

# Modèle création (avec mot de passe)
user_create_model = api.model('UserCreate', {
    'username': fields.String(required=True, description='Nom d\'utilisateur'),
    'email': fields.String(required=True, description='Adresse email'),
    'password': fields.String(required=True, description='Mot de passe', min_length=6),
    'is_admin': fields.Boolean(description='Administrateur', default=False)
})

# Modèle update (mot de passe optionnel)
user_update_model = api.model('UserUpdate', {
    'username': fields.String(description='Nom d\'utilisateur'),
    'email': fields.String(description='Adresse email'),
    'password': fields.String(description='Mot de passe', min_length=6),
    'is_admin': fields.Boolean(description='Administrateur')
})

@api.route('')
class UserList(Resource):
    @api.marshal_list_with(user_public_model)
    @require_admin_token  # Seuls les admins peuvent lister tous les utilisateurs
    def get(self):
        """Liste tous les utilisateurs (admin uniquement)"""
        return User.query.all()

    @api.expect(user_create_model)
    @api.marshal_with(user_public_model, code=201)
    def post(self):
        """Crée un nouvel utilisateur"""
        data = api.payload
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
    @require_admin_token  # Seuls les admins peuvent voir un utilisateur précis
    def get(self, user_id):
        """Affiche un utilisateur (admin uniquement)"""
        return User.query.get_or_404(user_id)

    @api.expect(user_update_model)
    @api.marshal_with(user_public_model)
    @require_admin_token  # Seuls les admins peuvent modifier un utilisateur
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

    @require_admin_token  # Seuls les admins peuvent supprimer un utilisateur
    def delete(self, user_id):
        """Supprime un utilisateur (admin uniquement)"""
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return {'message': 'Utilisateur supprimé'}

# Exemple de route admin-only pour test
@api.route('/admin-only')
class AdminOnly(Resource):
    @require_admin_token
    def get(self):
        return {"message": "Bienvenue, admin !"}
