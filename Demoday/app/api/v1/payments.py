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
    'https://localhost:5000',
    'https://127.0.0.1:5000',
])

logger = logging.getLogger(__name__)


def get_stripe_service():
    """Créer une instance du service Stripe avec le contexte de l'app"""
    from app.services.stripe_service import StripeService
    return StripeService()


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
            if not data.get('phone') and user.phone:
                data['phone'] = user.phone
        # Invité : user_id null ; connecté : la commande est liée au compte JWT.
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
    Le montant est le devis serveur (catalogue + livraison + promo + acompte).
    """
    user, error = load_current_user_optional()
    if error:
        body, status = error
        return jsonify(body), status
    if not stripe_configured():
        return jsonify({
            'error': 'Stripe n\'est pas configuré. Utilisez POST /api/v1/payments/checkout en mode test.',
            'mode': 'test',
        }), 503

    try:
        data = request.get_json() or {}
        # user_id / email du JWT uniquement : le JSON ne peut pas rattacher le paiement à un autre compte.
        data['user_id'] = user.id if user else None
        if user:
            data['email'] = user.email
            if not (data.get('name') or data.get('customer_name')):
                data['name'] = user.username
            if not data.get('phone') and user.phone:
                data['phone'] = user.phone

        from app.services.checkout_service import build_checkout_quote
        quote = build_checkout_quote(data, user_id=user.id if user else None)
        stripe_service = get_stripe_service()
        result = stripe_service.create_payment_intent(data, quote=quote)

        return jsonify({
            'message': 'Payment Intent créé avec succès',
            'client_secret': result['client_secret'],
            'payment_intent_id': result['payment_intent_id'],
            'order_id': result['order_id'],
            'total_amount': result['total_amount'],
            'charge_amount': result['charge_amount'],
            'shipping_amount': result['shipping_amount'],
            'discount_amount': result['discount_amount'],
            'stripe_publishable_key': result['stripe_publishable_key'],
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception('Erreur création payment intent: %s', e)
        return jsonify({'error': 'Erreur interne du serveur'}), 500


@payments_bp.route('/confirm-payment', methods=['POST'])
def confirm_payment():
    """
    Confirme un paiement Stripe. Compte JWT, ou invité avec le même email que la commande.
    """
    user, error = load_current_user_optional()
    if error:
        body, status = error
        return jsonify(body), status

    try:
        data = request.get_json() or {}
        payment_intent_id = data.get('payment_intent_id')
        if not payment_intent_id:
            return jsonify({'error': 'payment_intent_id requis'}), 400

        order = Order.query.filter_by(stripe_payment_intent_id=payment_intent_id).first()
        if not order:
            return jsonify({'error': 'Commande non trouvée'}), 404
        if user:
            if not _user_owns_order(user, order):
                return jsonify({'error': 'Commande non trouvée'}), 404
        else:
            email = (data.get('email') or '').strip().lower()
            if not email:
                return jsonify({'error': 'Email requis pour confirmer en invité.'}), 400
            if (order.email or '').strip().lower() != email:
                return jsonify({'error': 'Commande non trouvée'}), 404
        if not stripe_configured():
            return jsonify({'error': 'Stripe n\'est pas configuré'}), 503

        stripe_service = get_stripe_service()
        result = stripe_service.confirm_payment(payment_intent_id)
        order = db.session.get(Order, order.id)
        from app.services.shop_ops import clear_cart, guest_token_from
        clear_cart(
            user_id=user.id if user else None,
            token=guest_token_from(request.headers.get('X-Cart-Token')),
        )
        return jsonify({
            'message': 'Paiement confirmé',
            'status': result['status'],
            'order': _serialize_order(user, order),
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
        payload = request.get_data()  # brut : on ne parse pas le JSON avant la signature Stripe
        sig_header = request.headers.get('Stripe-Signature')
        
        if not sig_header:
            return jsonify({'error': 'Signature manquante'}), 400
        
        stripe_service = get_stripe_service()
        result = stripe_service.handle_webhook(payload, sig_header)
        
        return jsonify(result), 200
        
    except ValueError:
        return jsonify({'error': 'Webhook invalide'}), 400
    except Exception:
        logger.exception('Erreur webhook')
        return jsonify({'error': 'Erreur interne du serveur'}), 500


def _user_owns_order(user, order):
    """Le client ne lit que ses commandes (user_id ou même email)."""
    if user.is_admin:
        return True
    if order.user_id and order.user_id == user.id:
        return True
    # Commande invitée : même email que le JWT (marie@test.com après un checkout guest).
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
    # IDOR : même 404 si la commande existe (pas d’énumération d’ids).
    if not _user_owns_order(user, order):
        return jsonify({'error': 'Commande non trouvée'}), 404
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
        # Solde encaissé → paid ; l'atelier démarre si prep_status était encore vide.
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
    # Réponse fleuriste : id Stripe inclus pour le suivi processeur.
    return jsonify({'order': order.to_dict(include_stripe=True)}), 200


@payments_bp.route('/orders/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    """Fleuriste : enlever une commande (lignes cascade)."""
    denied = admin_required_response()
    if denied:
        return denied
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({'error': 'Commande non trouvée'}), 404
    db.session.delete(order)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Commande supprimée'}), 200


@payments_bp.route('/my-orders', methods=['GET'])
def get_my_orders():
    """Suivi client : uniquement les commandes du compte connecté."""
    user, error = load_current_user()
    if error:
        body, status = error
        return jsonify(body), status
    email = (user.email or '').strip().lower()
    # Liste client : id du compte OU même email (commandes passées en invité).
    filters = [Order.user_id == user.id]
    if email:
        filters.append(func.lower(Order.email) == email)
    orders = (
        Order.query.filter(or_(*filters))
        .order_by(Order.created_at.desc())
        .all()
    )
    return jsonify({'orders': [_serialize_order(user, order) for order in orders]}), 200


@payments_bp.route('/track', methods=['POST'])
def track_guest_order_route():
    """Invité : email + n° de commande, sans compte."""
    data = request.get_json(silent=True) or {}
    from app.services.shop_commerce import track_guest_order
    try:
        order = track_guest_order(data.get('email'), data.get('order_id') or data.get('id'))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except KeyError:
        return jsonify({'error': 'Aucune commande pour cet email et ce numéro.'}), 404
    return jsonify({'order': order.to_dict(include_stripe=False)})


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
            # Admin : toutes les commandes, id Stripe visible.
            'orders': [order.to_dict(include_stripe=True) for order in orders]
        }), 200
        
    except Exception as e:
        logger.exception('Erreur récupération commandes: %s', e)
        return jsonify({'error': 'Erreur interne du serveur'}), 500
