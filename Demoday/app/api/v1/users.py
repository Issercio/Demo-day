"""Unused leftover blueprint. Live user routes are in routes.py and users_restx.py."""
from flask import Blueprint, jsonify

users_bp = Blueprint('users', __name__)


@users_bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    return jsonify({'error': 'Introuvable'}), 404


@users_bp.route('', methods=['POST'])
def create_user():
    return jsonify({'error': 'Introuvable'}), 404
