from flask import Blueprint, request, jsonify
from flask_cors import CORS
from sqlalchemy import func, or_
from app.extensions import db
from app.models import Order
from app.models.order import PAID_LIKE, PREP_STATUSES
from app.api.v1.auth_utils import admin_required_response, load_current_user, load_current_user_optional
from app.services.checkout_service import (
    PaymentDeclined,
    checkout,
    payment_config,
    stripe_configured,
)
import logging

payments_bp = Blueprint('payments', __name__)
CORS(payments_bp, origins=[
    'http://localhost:8000',
    'http://localhost:5000',
    'http://127.0.0.1:5000',
])

logger = logging.getLogger(__name__)


def get_stripe_service():
    """Créer une instance du service Stripe avec le contexte de l'app"""
    from app.services.stripe_service import StripeService
    return StripeService()


def _current_user_id():
    user, error = load_current_user_optional()
    if error or not user:
        return None
    return user.id


@payments_bp.route('/config', methods=['GET'])
def get_payment_config():
    return jsonify(payment_config()), 200


@payments_bp.route('/checkout', methods=['POST'])
def create_checkout():
    """
    Enregistre une commande réelle et traite le paiement.

    Sans clés Stripe, le processeur de test accepte 4242...4242
    et refuse 4000...0002 / 4000...9995.
    """
    try:
        data = request.get_json() or {}
        user, error = load_current_user_optional()
        if error:
            body, status = error
            return jsonify(body), status
        if user:
            # Compte connecté : on prend l'email du JWT/DB, pas celui envoyé dans le body.
            data['email'] = user.email
            if not (data.get('name') or data.get('customer_name')):
                data['name'] = user.username
        order = checkout(data, user_id=user.id if user else None)
        return jsonify({
            'message': 'Paiement confirmé',
            'order': _serialize_order(user, order),
        }), 201
    except PaymentDeclined as exc:
        payload = {'error': str(exc)}
        if exc.order is not None:
            payload['order'] = _serialize_order(user, exc.order)
        return jsonify(payload), 402  # paiement refusé, commande failed enregistrée
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logger.exception('Erreur checkout: %s', exc)
        return jsonify({'error': 'Erreur interne du serveur'}), 500


@payments_bp.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """
    Crée un Payment Intent Stripe. Nécessite des clés Stripe valides.
    """
    if not stripe_configured():
        return jsonify({
            'error': 'Stripe n\'est pas configuré. Utilisez POST /api/v1/payments/checkout en mode test.',
            'mode': 'test',
        }), 503

    try:
        data = request.get_json()
        
        if not data or 'items' not in data or 'email' not in data:
            return jsonify({'error': 'Items et email requis'}), 400
        
        if not data['items']:
            return jsonify({'error': 'Au moins un item requis'}), 400
        
        for item in data['items']:
            if 'product_id' not in item or 'quantity' not in item:
                return jsonify({'error': 'Chaque item doit avoir product_id et quantity'}), 400
            if item['quantity'] <= 0:
                return jsonify({'error': 'La quantité doit être positive'}), 400

        if not data.get('user_id'):
            data['user_id'] = _current_user_id()

        stripe_service = get_stripe_service()
        result = stripe_service.create_payment_intent(data)
        
        return jsonify({
            'message': 'Payment Intent créé avec succès',
            'client_secret': result['client_secret'],
            'order_id': result['order_id'],
            'total_amount': result['total_amount'],
            'stripe_publishable_key': result['stripe_publishable_key']
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception('Erreur création payment intent: %s', e)
        return jsonify({'error': 'Erreur interne du serveur'}), 500


@payments_bp.route('/confirm-payment', methods=['POST'])
def confirm_payment():
    """
    Confirme un paiement après validation côté client
    """
    if not stripe_configured():
        return jsonify({'error': 'Stripe n\'est pas configuré'}), 503

    try:
        data = request.get_json()
        
        if not data or 'payment_intent_id' not in data:
            return jsonify({'error': 'payment_intent_id requis'}), 400
        
        stripe_service = get_stripe_service()
        result = stripe_service.confirm_payment(data['payment_intent_id'])
        
        return jsonify({
            'message': 'Paiement confirmé',
            'status': result['status'],
            'order': result['order']
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception('Erreur confirmation paiement: %s', e)
        return jsonify({'error': 'Erreur interne du serveur'}), 500


@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """
    Endpoint pour recevoir les webhooks Stripe
    """
    if not stripe_configured():
        return jsonify({'error': 'Stripe n\'est pas configuré'}), 503

    try:
        payload = request.get_data()
        sig_header = request.headers.get('Stripe-Signature')
        
        if not sig_header:
            return jsonify({'error': 'Signature manquante'}), 400
        
        stripe_service = get_stripe_service()
        result = stripe_service.handle_webhook(payload, sig_header)
        
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception('Erreur webhook: %s', e)
        return jsonify({'error': 'Erreur interne du serveur'}), 500


def _user_owns_order(user, order):
    """Le client ne lit que ses commandes (user_id ou même email)."""
    if user.is_admin:
        return True
    if order.user_id and order.user_id == user.id:
        return True
    order_email = (order.email or '').lower()
    user_email = (user.email or '').lower()
    return bool(order_email and user_email and order_email == user_email)


def _serialize_order(user, order):
    """Le client n'obtient pas l'id Stripe ; l'admin le voit pour le suivi processeur."""
    admin = bool(user and getattr(user, 'is_admin', False))
    return order.to_dict(include_stripe=admin)


@payments_bp.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    """Détail d'une commande : admin, propriétaire, ou email du JWT."""
    user, error = load_current_user()
    if error:
        body, status = error
        return jsonify(body), status
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({'error': 'Commande non trouvée'}), 404
    # IDOR : un client ne lit que sa commande ; la liste complète est admin-only.
    if not _user_owns_order(user, order):
        return jsonify({'success': False, 'message': 'Accès refusé'}), 403
    return jsonify({'order': _serialize_order(user, order)}), 200


@payments_bp.route('/orders/<int:order_id>', methods=['PATCH'])
def patch_order(order_id):
    """Fleuriste : avancer la préparation, ou marquer le solde d'un acompte comme payé."""
    denied = admin_required_response()
    if denied:
        return denied
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({'error': 'Commande non trouvée'}), 404

    data = request.get_json() or {}
    changed = False

    if 'prep_status' in data:
        if order.status not in PAID_LIKE:
            return jsonify({
                'error': 'La préparation ne s\'applique qu\'aux commandes payées ou avec acompte.',
            }), 400
        prep = data.get('prep_status')
        if prep not in PREP_STATUSES:
            return jsonify({'error': 'Statut de préparation invalide.'}), 400
        order.prep_status = prep
        changed = True

    settle = bool(data.get('settle_payment')) or data.get('status') == 'paid'
    if settle:
        if order.status == 'deposit':
            order.status = 'paid'
            if not order.prep_status:
                order.prep_status = 'a_preparer'
            changed = True
        elif order.status == 'pending':
            order.status = 'paid'
            if not order.prep_status:
                order.prep_status = 'a_preparer'
            changed = True
        elif order.status == 'paid':
            return jsonify({'error': 'Cette commande est déjà soldée.'}), 400
        else:
            return jsonify({'error': 'Impossible d\'encaisser une commande refusée ou annulée.'}), 400

    if not changed:
        return jsonify({'error': 'Aucun champ à mettre à jour.'}), 400

    db.session.commit()
    return jsonify({'order': order.to_dict(include_stripe=True)}), 200


@payments_bp.route('/my-orders', methods=['GET'])
def get_my_orders():
    """Suivi client : uniquement les commandes du compte connecté."""
    user, error = load_current_user()
    if error:
        body, status = error
        return jsonify(body), status
    email = (user.email or '').strip().lower()
    filters = [Order.user_id == user.id]
    if email:
        filters.append(func.lower(Order.email) == email)
    orders = (
        Order.query.filter(or_(*filters))
        .order_by(Order.created_at.desc())
        .all()
    )
    return jsonify({'orders': [_serialize_order(user, order) for order in orders]}), 200


@payments_bp.route('/orders', methods=['GET'])
def get_orders():
    """
    Récupère toutes les commandes (pour admin)
    """
    denied = admin_required_response()
    if denied:
        return denied
    try:
        orders = Order.query.order_by(Order.created_at.desc()).all()
        
        return jsonify({
            'orders': [order.to_dict(include_stripe=True) for order in orders]
        }), 200
        
    except Exception as e:
        logger.exception('Erreur récupération commandes: %s', e)
        return jsonify({'error': 'Erreur interne du serveur'}), 500
