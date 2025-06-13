from flask import Blueprint, jsonify, request
from ...persistence.user_repository import UserRepository

users_bp = Blueprint('users', __name__)
user_repository = UserRepository()

@users_bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = user_repository.get_by_id(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404
        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_admin': user.is_admin,
            'password': user.password
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@users_bp.route('', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        user = user_repository.create(data)
        return jsonify({
            'message': 'Utilisateur créé avec succès',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_admin': user.is_admin,
                'password': user.password
            }
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
