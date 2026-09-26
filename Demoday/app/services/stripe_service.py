import uuid

import stripe
from flask import current_app

from app.extensions import db
from app.models import Order, OrderItem
from app.services.checkout_service import (
    build_checkout_quote,
    mark_order_failed,
    mark_order_succeeded,
    to_cents,
)

PLACEHOLDER_WEBHOOKS = {
    '',
    'whsec_...',
    'whsec_VOTRE_WEBHOOK_SECRET',
}


def _intent_status(intent):
    if intent is None:
        return ''
    if isinstance(intent, dict):
        return str(intent.get('status') or '')
    return str(getattr(intent, 'status', '') or '')


def _intent_id(intent):
    if isinstance(intent, dict):
        return intent.get('id')
    return getattr(intent, 'id', None)


def _stripe_last4(intent):
    try:
        data = intent.to_dict() if hasattr(intent, 'to_dict') else intent
        if not isinstance(data, dict):
            data = dict(data)
        charges = (data.get('charges') or {}).get('data') or []
        if charges:
            card = ((charges[0].get('payment_method_details') or {}).get('card') or {})
            last4 = card.get('last4')
            if last4:
                return str(last4)[:4]
        details = data.get('payment_method_details') or {}
        last4 = (details.get('card') or {}).get('last4')
        if last4:
            return str(last4)[:4]
    except Exception:
        return None
    return None


class StripeService:
    def __init__(self):
        secret = (current_app.config.get('STRIPE_SECRET_KEY') or '').strip()
        if not secret:
            raise ValueError('Clé Stripe secrète manquante')
        stripe.api_key = secret

    def create_payment_intent(self, order_data, quote=None):
        """
        Payment Intent : montant = charge serveur (livraison, promo, acompte).
        Stock non consommé tant que le paiement n'est pas succeeded.
        """
        try:
            if quote is None:
                quote = build_checkout_quote(order_data, user_id=order_data.get('user_id'))
            settle_id = order_data.get('settle_order_id')
            if settle_id:
                order = db.session.get(Order, int(settle_id))
                if order is None or order.status != 'deposit':
                    raise ValueError('Commande d\'acompte introuvable.')
                remaining = order.remaining_amount()
                if remaining is None or remaining <= 0:
                    raise ValueError('Aucun solde à encaisser.')
                intent = stripe.PaymentIntent.create(
                    amount=to_cents(remaining),
                    currency='eur',
                    metadata={
                        'order_id': str(order.id),
                        'email': order.email,
                        'settle': '1',
                    },
                    automatic_payment_methods={'enabled': True},
                )
                order.stripe_payment_intent_id = _intent_id(intent)
                db.session.commit()
                return {
                    'client_secret': getattr(intent, 'client_secret', None) or intent['client_secret'],
                    'payment_intent_id': order.stripe_payment_intent_id,
                    'order_id': order.id,
                    'total_amount': float(order.total_amount),
                    'charge_amount': float(remaining),
                    'shipping_amount': float(order.shipping_amount or 0),
                    'discount_amount': float(order.discount_amount or 0),
                    'carrier': '',
                    'eta': '',
                    'stripe_publishable_key': current_app.config['STRIPE_PUBLISHABLE_KEY'],
                }
            charge = quote['charge']
            order = Order(
                user_id=quote['user_id'],
                email=quote['email'],
                customer_name=quote['name'],
                phone=quote['phone'],
                address=quote['address'],
                total_amount=quote['payable'],
                deposit_amount=quote['deposit_amount'],
                status='pending',
                payment_method='card',
                payment_reference=f'STRIPE-{uuid.uuid4().hex[:10].upper()}',
                fulfillment_type=quote['ftype'],
                fulfillment_date=quote['fdate'],
                fulfillment_slot=quote['fslot'],
                shipping_amount=quote['shipping'],
                discount_amount=quote['discount'],
                promo_code=quote['promo_row'].code if quote['promo_row'] else None,
            )
            db.session.add(order)
            db.session.flush()

            for line in quote['lines']:
                db.session.add(OrderItem(
                    order_id=order.id,
                    product_id=line['product'].id,
                    quantity=line['quantity'],
                    price=line['price'],
                ))

            intent = stripe.PaymentIntent.create(
                amount=to_cents(charge),
                currency='eur',
                metadata={
                    'order_id': str(order.id),
                    'email': quote['email'],
                    'deposit': '1' if quote['want_deposit'] else '0',
                },
                automatic_payment_methods={
                    'enabled': True,
                },
            )

            order.stripe_payment_intent_id = _intent_id(intent)
            db.session.commit()

            shipping_info = quote['shipping_info']
            return {
                'client_secret': getattr(intent, 'client_secret', None) or intent['client_secret'],
                'payment_intent_id': order.stripe_payment_intent_id,
                'order_id': order.id,
                'total_amount': float(quote['payable']),
                'charge_amount': float(charge),
                'shipping_amount': float(quote['shipping']),
                'discount_amount': float(quote['discount']),
                'carrier': shipping_info.get('carrier') or '',
                'eta': shipping_info.get('eta') or '',
                'stripe_publishable_key': current_app.config['STRIPE_PUBLISHABLE_KEY'],
            }

        except Exception:
            db.session.rollback()
            raise

    def confirm_payment(self, payment_intent_id):
        """Met à jour le statut d'une commande déjà liée à ce Payment Intent."""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            order = Order.query.filter_by(stripe_payment_intent_id=payment_intent_id).first()
            if not order:
                raise ValueError("Commande non trouvée")

            status = _intent_status(intent)
            meta = {}
            try:
                raw = intent.to_dict() if hasattr(intent, 'to_dict') else intent
                meta = (raw.get('metadata') or {}) if isinstance(raw, dict) else {}
            except Exception:
                meta = {}
            settle = str(meta.get('settle') or '') == '1'
            if status == 'succeeded':
                order = mark_order_succeeded(order, card_last4=_stripe_last4(intent), settle=settle)
            elif status in ('canceled', 'payment_failed', 'requires_payment_method'):
                if order.status == 'pending':
                    order = mark_order_failed(order)
            return {
                'status': order.status,
                'order': order.to_dict(),
            }
        except Exception:
            db.session.rollback()
            raise

    def handle_webhook(self, payload, sig_header):
        webhook_secret = (current_app.config.get('STRIPE_WEBHOOK_SECRET') or '').strip()
        if webhook_secret in PLACEHOLDER_WEBHOOKS:
            raise ValueError('Webhook Stripe non configuré')
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception:
            raise ValueError('Webhook invalide') from None

        event_type = event['type'] if isinstance(event, dict) else getattr(event, 'type', '')
        data = event['data'] if isinstance(event, dict) else event.data
        payment_intent = data['object'] if isinstance(data, dict) else data.object
        intent_id = _intent_id(payment_intent)
        if event_type in (
            'payment_intent.succeeded',
            'payment_intent.payment_failed',
            'payment_intent.canceled',
        ) and intent_id:
            self.confirm_payment(intent_id)

        return {'status': 'success'}
