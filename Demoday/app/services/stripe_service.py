import uuid

import stripe
from flask import current_app

from app.extensions import db
from app.models import Order, OrderItem
from app.services.checkout_service import build_order_lines, to_cents

PLACEHOLDER_WEBHOOKS = {
    '',
    'whsec_...',
    'whsec_VOTRE_WEBHOOK_SECRET',
}


class StripeService:
    def __init__(self):
        secret = (current_app.config.get('STRIPE_SECRET_KEY') or '').strip()
        if not secret:
            raise ValueError('Clé Stripe secrète manquante')
        stripe.api_key = secret

    def create_payment_intent(self, order_data):
        """
        Crée un Payment Intent Stripe pour une commande.

        Prix catalogue via build_order_lines (Decimal), jamais le JSON client.
        """
        try:
            lines, total = build_order_lines(order_data.get('items') or [])
            order = Order(
                user_id=order_data.get('user_id'),
                email=order_data['email'],
                customer_name=order_data.get('name') or order_data.get('customer_name'),
                total_amount=total,
                status='pending',
                payment_method='card',
                payment_reference=f'STRIPE-{uuid.uuid4().hex[:10].upper()}',
            )
            db.session.add(order)
            db.session.flush()

            for line in lines:
                db.session.add(OrderItem(
                    order_id=order.id,
                    product_id=line['product'].id,
                    quantity=line['quantity'],
                    price=line['price'],
                ))

            intent = stripe.PaymentIntent.create(
                amount=to_cents(total),
                currency='eur',
                metadata={
                    'order_id': order.id,
                    'email': order_data['email'],
                },
                automatic_payment_methods={
                    'enabled': True,
                },
            )

            order.stripe_payment_intent_id = intent.id
            db.session.commit()

            return {
                'client_secret': intent.client_secret,
                'order_id': order.id,
                'total_amount': float(total),
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

            if intent.status == 'succeeded':
                order.status = 'paid'
                if not order.prep_status:
                    order.prep_status = 'a_preparer'
            elif intent.status == 'payment_failed':
                order.status = 'failed'
                order.prep_status = None
            else:
                order.status = 'pending'

            db.session.commit()
            return {
                'status': order.status,
                'order': order.to_dict(),  # include_stripe=False : pas d'id PI
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

        if event['type'] in ('payment_intent.succeeded', 'payment_intent.payment_failed'):
            payment_intent = event['data']['object']
            self.confirm_payment(payment_intent['id'])

        return {'status': 'success'}
