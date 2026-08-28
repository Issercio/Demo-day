from flask import Blueprint, request, jsonify, current_app
from flask_cors import CORS
from app.services.stripe_service import StripeService
from app.models import Order
import logging

payments_bp = Blueprint('payments', __name__)
CORS(payments_bp)

def get_stripe_service():
    """Créer une instance du service Stripe avec le contexte de l'app"""
    return StripeService()

@payments_bp.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """
    Crée un Payment Intent pour initier un paiement
    
    Body: {
        "items": [{"product_id": 1, "quantity": 2}],
        "email": "client@example.com",
        "user_id": 1 (optionnel)
    }
    """
    try:
        data = request.get_json()
        
        # Validation des données
        if not data or 'items' not in data or 'email' not in data:
            return jsonify({'error': 'Items et email requis'}), 400
        
        if not data['items']:
            return jsonify({'error': 'Au moins un item requis'}), 400
        
        # Validation de chaque item
        for item in data['items']:
            if 'product_id' not in item or 'quantity' not in item:
                return jsonify({'error': 'Chaque item doit avoir product_id et quantity'}), 400
            if item['quantity'] <= 0:
                return jsonify({'error': 'La quantité doit être positive'}), 400
        
        print(f"=== CRÉATION PAYMENT INTENT ===")
        print(f"Données reçues: {data}")
        
        # Créer le Payment Intent
        stripe_service = get_stripe_service()
        result = stripe_service.create_payment_intent(data)
        
        print(f"Payment Intent créé: {result['order_id']}")
        
        return jsonify({
            'message': 'Payment Intent créé avec succès',
            'client_secret': result['client_secret'],
            'order_id': result['order_id'],
            'total_amount': result['total_amount'],
            'stripe_publishable_key': result['stripe_publishable_key']
        }), 201
        
    except ValueError as e:
        print(f"Erreur validation: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Erreur création payment intent: {str(e)}")
        return jsonify({'error': 'Erreur interne du serveur'}), 500

@payments_bp.route('/confirm-payment', methods=['POST'])
def confirm_payment():
    """
    Confirme un paiement après validation côté client
    
    Body: {
        "payment_intent_id": "pi_..."
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'payment_intent_id' not in data:
            return jsonify({'error': 'payment_intent_id requis'}), 400
        
        print(f"=== CONFIRMATION PAIEMENT ===")
        print(f"Payment Intent ID: {data['payment_intent_id']}")
        
        # Confirmer le paiement
        stripe_service = get_stripe_service()
        result = stripe_service.confirm_payment(data['payment_intent_id'])
        
        print(f"Paiement confirmé: {result['status']}")
        
        return jsonify({
            'message': 'Paiement confirmé',
            'status': result['status'],
            'order': result['order']
        }), 200
        
    except ValueError as e:
        print(f"Erreur validation: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Erreur confirmation paiement: {str(e)}")
        return jsonify({'error': 'Erreur interne du serveur'}), 500

@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """
    Endpoint pour recevoir les webhooks Stripe
    """
    try:
        payload = request.get_data()
        sig_header = request.headers.get('Stripe-Signature')
        
        if not sig_header:
            return jsonify({'error': 'Signature manquante'}), 400
        
        print(f"=== WEBHOOK STRIPE ===")
        
        # Traiter le webhook
        stripe_service = get_stripe_service()
        result = stripe_service.handle_webhook(payload, sig_header)
        
        print(f"Webhook traité avec succès")
        
        return jsonify(result), 200
        
    except ValueError as e:
        print(f"Erreur signature webhook: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Erreur webhook: {str(e)}")
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
        print(f"Erreur récupération commande: {str(e)}")
        return jsonify({'error': 'Erreur interne du serveur'}), 500

@payments_bp.route('/orders', methods=['GET'])
def get_orders():
    """
    Récupère toutes les commandes (pour admin)
    """
    try:
        orders = Order.query.order_by(Order.created_at.desc()).all()
        
        return jsonify({
            'orders': [order.to_dict() for order in orders]
        }), 200
        
    except Exception as e:
        print(f"Erreur récupération commandes: {str(e)}")
        return jsonify({'error': 'Erreur interne du serveur'}), 500
