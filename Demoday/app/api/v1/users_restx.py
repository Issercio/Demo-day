from flask_restx import Namespace, Resource, fields
from app.extensions import db
from app.models.user import User
from werkzeug.security import generate_password_hash

api = Namespace('users', description='Gestion des utilisateurs')

user_model = api.model('User', {
    'id': fields.Integer(readOnly=True),
    'username': fields.String(required=True, description='Nom d\'utilisateur'),
    'password': fields.String(required=True, description='Mot de passe', min_length=6)
})

user_update_model = api.model('UserUpdate', {
    'username': fields.String(description='Nom d\'utilisateur'),
    'password': fields.String(description='Mot de passe', min_length=6)
})

@api.route('')
class UserList(Resource):
    @api.marshal_list_with(user_model, mask={'password': False})
    def get(self):
        """Liste tous les utilisateurs (sans mot de passe)"""
        return User.query.all()

    @api.expect(user_model)
    def post(self):
        """Crée un nouvel utilisateur"""
        data = api.payload
        user = User(
            username=data['username'],
            password=generate_password_hash(data['password'])
        )
        db.session.add(user)
        db.session.commit()
        return {'id': user.id, 'username': user.username}, 201

@api.route('/<int:user_id>')
class UserResource(Resource):
    @api.marshal_with(user_model, mask={'password': False})
    def get(self, user_id):
        """Affiche un utilisateur (sans mot de passe)"""
        return User.query.get_or_404(user_id)

    @api.expect(user_update_model)
    def put(self, user_id):
        """Modifie un utilisateur"""
        user = User.query.get_or_404(user_id)
        data = api.payload
        if 'username' in data:
            user.username = data['username']
        if 'password' in data:
            user.password = generate_password_hash(data['password'])
        db.session.commit()
        return {'message': 'Utilisateur mis à jour', 'user': user.username}

    def delete(self, user_id):
        """Supprime un utilisateur"""
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return {'message': 'Utilisateur supprimé'}
