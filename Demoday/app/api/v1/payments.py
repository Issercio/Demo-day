from flask import Blueprint, request, jsonify
from flask_cors import CORS
from app.extensions import db
from app.models import Order
from app.api.v1.auth_utils import admin_required_response, get_token_payload
from app.services.checkout_service import (
    PaymentDeclined,
    checkout,
    payment_config,
    stripe_configured,
)
from app.services.invoice_mail import send_order_invoice
import logging

payments_bp = Blueprint('payments', __name__)
CORS(payments_bp)

logger = logging.getLogger(__name__)


def get_stripe_service():
    """Créer une instance du service Stripe avec le contexte de l'app"""
    from app.services.stripe_service import StripeService
    return StripeService()


def _current_user_id():
    payload, error = get_token_payload()
    if error or not payload:
        return None
    try:
        return int(payload.get('sub'))
    except (TypeError, ValueError):
        return None


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
        order = checkout(data, user_id=_current_user_id())
        invoice = send_order_invoice(order)
        return jsonify({
            'message': 'Paiement confirmé',
            'order': order.to_dict(),
            'invoice': invoice,
        }), 201
    except PaymentDeclined as exc:
        payload = {'error': str(exc)}
        if exc.order is not None:
            payload['order'] = exc.order.to_dict()
        return jsonify(payload), 402
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


@payments_bp.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    """
    Récupère les détails d'une commande
    """
    try:
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Commande non trouvée'}), 404
        
        return jsonify({
            'order': order.to_dict()
        }), 200
        
    except Exception as e:
        logger.exception('Erreur récupération commande: %s', e)
        return jsonify({'error': 'Erreur interne du serveur'}), 500


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
            'orders': [order.to_dict() for order in orders]
        }), 200
        
    except Exception as e:
        logger.exception('Erreur récupération commandes: %s', e)
        return jsonify({'error': 'Erreur interne du serveur'}), 500


@payments_bp.route('/orders/<int:order_id>/invoice', methods=['POST'])
def resend_order_invoice(order_id):
    """Admin: renvoyer la facture au client et à la copie boutique."""
    denied = admin_required_response()
    if denied:
        return denied
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({'error': 'Commande introuvable'}), 404
    invoice = send_order_invoice(order)
    status = 200 if invoice.get('sent') else 503
    return jsonify({'order_id': order.id, 'invoice': invoice}), status
