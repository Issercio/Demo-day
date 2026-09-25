from flask import Blueprint, jsonify, request

from app.api.v1.auth_utils import admin_required_response, load_current_user_optional
from app.services.shop_ops import (
    clear_cart,
    create_contact,
    guest_token_from,
    list_contacts,
    load_cart_items,
    merge_guest_into_user,
    patch_contact,
    save_cart_items,
    today_dashboard,
)

ops_bp = Blueprint('shop_ops', __name__)


def _identity():
    user, error = load_current_user_optional()
    if error:
        return None, None, error
    token = guest_token_from(request.headers.get('X-Cart-Token'))
    return user, token, None


@ops_bp.route('/cart', methods=['GET'])
def get_cart():
    user, token, error = _identity()
    if error:
        body, status = error
        return jsonify(body), status
    if user and token:
        items = merge_guest_into_user(user.id, token)
    else:
        items = load_cart_items(user_id=user.id if user else None, token=None if user else token)
    return jsonify({'items': items, 'count': sum(int(item.get('quantity') or 1) for item in items)})


@ops_bp.route('/cart', methods=['PUT'])
def put_cart():
    user, token, error = _identity()
    if error:
        body, status = error
        return jsonify(body), status
    if not user and not token:
        token = guest_token_from(str(request.get_json(silent=True) or {}).get('guest_token') or '')
    data = request.get_json(silent=True) or {}
    try:
        items = save_cart_items(
            data.get('items') or [],
            user_id=user.id if user else None,
            token=None if user else token,
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'items': items, 'count': sum(int(item.get('quantity') or 1) for item in items)})


@ops_bp.route('/cart', methods=['DELETE'])
def delete_cart():
    user, token, error = _identity()
    if error:
        body, status = error
        return jsonify(body), status
    clear_cart(user_id=user.id if user else None, token=token)
    return jsonify({'items': [], 'count': 0})


@ops_bp.route('/contact', methods=['POST'])
def post_contact():
    data = request.get_json(silent=True) or {}
    try:
        row = create_contact(data)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'message': 'Demande envoyée.', 'id': row.id}), 201


@ops_bp.route('/contact', methods=['GET'])
def get_contact():
    denied = admin_required_response()
    if denied:
        return denied
    return jsonify({'requests': list_contacts()})


@ops_bp.route('/contact/<int:contact_id>', methods=['PATCH'])
def update_contact(contact_id):
    denied = admin_required_response()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    try:
        row = patch_contact(contact_id, data.get('status'))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except KeyError:
        return jsonify({'error': 'Demande introuvable'}), 404
    return jsonify({'request': row.to_dict()})


@ops_bp.route('/atelier/today', methods=['GET'])
def atelier_today():
    denied = admin_required_response()
    if denied:
        return denied
    return jsonify(today_dashboard())
