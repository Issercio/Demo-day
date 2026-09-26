from flask import Blueprint, jsonify, request

from app.api.v1.auth_utils import admin_required_response, json_internal_error, load_current_user_optional
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
        row = patch_contact(
            contact_id,
            status=data.get('status'),
            reply_text=data.get('reply') if 'reply' in data else data.get('reply_text'),
        )
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
    try:
        return jsonify(today_dashboard())
    except Exception:
        from app.extensions import db
        db.session.rollback()
        try:
            from app.services.shop_ops import ensure_ops_schema
            ensure_ops_schema()
            return jsonify(today_dashboard())
        except Exception:
            return json_internal_error()


@ops_bp.route('/settings', methods=['GET'])
def get_settings_route():
    from app.services.shop_commerce import public_settings
    return jsonify(public_settings())


@ops_bp.route('/settings', methods=['PUT'])
def put_settings_route():
    denied = admin_required_response()
    if denied:
        return denied
    from app.services.shop_commerce import update_settings, public_settings
    try:
        update_settings(request.get_json(silent=True) or {})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify(public_settings())


@ops_bp.route('/shipping', methods=['GET'])
def shipping_quote_route():
    from app.services.shop_commerce import quote_shipping_details
    ftype = (request.args.get('type') or '').strip().lower()
    address = request.args.get('address') or ''
    try:
        details = quote_shipping_details(ftype, address)
    except ValueError as exc:
        return jsonify({'error': str(exc), 'shipping': None}), 400
    return jsonify({
        'shipping': float(details['shipping']),
        'zone': details['zone'],
        'overseas': details['overseas'],
        'carrier': details['carrier'],
        'eta': details['eta'],
    })


@ops_bp.route('/promo/quote', methods=['GET'])
def quote_promo_route():
    from app.services.shop_commerce import apply_promo
    code = request.args.get('code') or ''
    subtotal = request.args.get('subtotal') or '0'
    try:
        row, discount = apply_promo(code, subtotal)
    except ValueError as exc:
        return jsonify({'error': str(exc), 'discount': 0}), 400
    return jsonify({
        'discount': float(discount),
        'code': row.code if row else None,
    })


@ops_bp.route('/promos', methods=['GET'])
def list_promos_route():
    denied = admin_required_response()
    if denied:
        return denied
    from app.services.shop_commerce import list_promos
    return jsonify({'promos': list_promos()})


@ops_bp.route('/promos', methods=['POST'])
def create_promo_route():
    denied = admin_required_response()
    if denied:
        return denied
    from app.services.shop_commerce import create_promo
    try:
        row = create_promo(request.get_json(silent=True) or {})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'promo': row.to_dict()}), 201


@ops_bp.route('/promos/<int:promo_id>', methods=['PATCH'])
def patch_promo_route(promo_id):
    denied = admin_required_response()
    if denied:
        return denied
    from app.services.shop_commerce import set_promo_active
    data = request.get_json(silent=True) or {}
    try:
        row = set_promo_active(promo_id, data.get('active'))
    except KeyError:
        return jsonify({'error': 'Code introuvable'}), 404
    return jsonify({'promo': row.to_dict()})


@ops_bp.route('/subscriptions', methods=['GET'])
def list_subscriptions_route():
    user, error = load_current_user_optional()
    if error:
        body, status = error
        return jsonify(body), status
    if user is None:
        return jsonify({'error': 'Authentification requise'}), 401
    from app.services.subscription_ops import list_for_user
    admin = bool(getattr(user, 'is_admin', False))
    return jsonify({'subscriptions': list_for_user(user, include_all=admin)})


@ops_bp.route('/subscriptions/<int:subscription_id>', methods=['PATCH'])
def patch_subscription_route(subscription_id):
    user, error = load_current_user_optional()
    if error:
        body, status = error
        return jsonify(body), status
    if user is None:
        return jsonify({'error': 'Authentification requise'}), 401
    data = request.get_json(silent=True) or {}
    from app.services.subscription_ops import mark_delivered, set_status
    admin = bool(getattr(user, 'is_admin', False))
    try:
        if data.get('deliver'):
            if not admin:
                return jsonify({'error': 'Réservé à l\'atelier'}), 403
            row = mark_delivered(subscription_id)
        elif 'status' in data:
            row = set_status(subscription_id, data.get('status'), user=user, admin=admin)
        else:
            return jsonify({'error': 'Aucun champ à mettre à jour.'}), 400
    except KeyError:
        return jsonify({'error': 'Abonnement introuvable'}), 404
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'subscription': row.to_dict()})
