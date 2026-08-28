import stripe
from flask import current_app
from app.models import Order, OrderItem, Product
from app.extensions import db

class StripeService:
    def __init__(self):
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    
    def create_payment_intent(self, order_data):
        """
        Crée un Payment Intent Stripe pour une commande
        
        Args:
            order_data: {
                'items': [{'product_id': int, 'quantity': int}],
                'email': str,
                'user_id': int (optionnel)
            }
        
        Returns:
            dict: {
                'client_secret': str,
                'order_id': int,
                'total_amount': float
            }
        """
        try:
            # Calculer le montant total
            total_amount = 0
            order_items = []
            
            for item in order_data['items']:
                product = Product.query.get(item['product_id'])
                if not product:
                    raise ValueError(f"Produit {item['product_id']} non trouvé")
                
                quantity = item['quantity']
                item_total = product.price * quantity
                total_amount += item_total
                
                order_items.append({
                    'product_id': product.id,
                    'quantity': quantity,
                    'price': product.price
                })
            
            # Créer la commande en base
            order = Order(
                user_id=order_data.get('user_id'),
                email=order_data['email'],
                total_amount=total_amount,
                status='pending'
            )
            db.session.add(order)
            db.session.flush()  # Pour obtenir l'ID
            
            # Ajouter les items
            for item_data in order_items:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=item_data['product_id'],
                    quantity=item_data['quantity'],
                    price=item_data['price']
                )
                db.session.add(order_item)
            
            # Créer le Payment Intent chez Stripe
            intent = stripe.PaymentIntent.create(
                amount=int(total_amount * 100),  # Stripe utilise les centimes
                currency='eur',
                metadata={
                    'order_id': order.id,
                    'email': order_data['email']
                },
                automatic_payment_methods={
                    'enabled': True,
                }
            )
            
            # Sauvegarder l'ID Stripe
            order.stripe_payment_intent_id = intent.id
            db.session.commit()
            
            return {
                'client_secret': intent.client_secret,
                'order_id': order.id,
                'total_amount': total_amount,
                'stripe_publishable_key': current_app.config['STRIPE_PUBLISHABLE_KEY']
            }
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    def confirm_payment(self, payment_intent_id):
        """
        Confirme un paiement et met à jour le statut de la commande
        """
        try:
            # Récupérer le Payment Intent depuis Stripe
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            # Trouver la commande correspondante
            order = Order.query.filter_by(stripe_payment_intent_id=payment_intent_id).first()
            if not order:
                raise ValueError("Commande non trouvée")
            
            # Mettre à jour le statut selon le résultat
            if intent.status == 'succeeded':
                order.status = 'paid'
            elif intent.status == 'payment_failed':
                order.status = 'failed'
            else:
                order.status = 'pending'
            
            db.session.commit()
            
            return {
                'status': order.status,
                'order': order.to_dict()
            }
            
        except Exception as e:
            db.session.rollback()
            raise e
    
    def handle_webhook(self, payload, sig_header):
        """
        Gère les webhooks Stripe pour les événements de paiement
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
            )
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                self.confirm_payment(payment_intent['id'])
                
            elif event['type'] == 'payment_intent.payment_failed':
                payment_intent = event['data']['object']
                self.confirm_payment(payment_intent['id'])
            
            return {'status': 'success'}
            
        except ValueError as e:
            raise ValueError(f"Signature invalide: {str(e)}")
        except Exception as e:
            raise e
