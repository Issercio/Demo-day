from flask import Blueprint, request, jsonify, session
from app.models.user import User
from app import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        # Ici, on peut stocker l'id utilisateur dans la session (connexion par cookie)
        session['user_id'] = user.id
        return jsonify({'message': 'Login successful', 'user': user.username}), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401
