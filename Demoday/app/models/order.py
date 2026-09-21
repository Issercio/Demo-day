from decimal import Decimal, ROUND_HALF_UP

from app.extensions import db
from app.models.base_model import utc_now

PAYMENT_LABELS = {
    'pending': 'Non payée',
    'paid': 'Payée',
    'deposit': 'Acompte versé',
    'failed': 'Paiement refusé',
    'cancelled': 'Annulée',
}

PREP_LABELS = {
    'a_preparer': 'À préparer',
    'en_preparation': 'En préparation',
    'pret': 'Prête',
    'remise': 'Remise',
}

PREP_STATUSES = tuple(PREP_LABELS)
PAID_LIKE = ('paid', 'deposit')


class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # invité = null
    user = db.relationship('User', back_populates='orders')
    email = db.Column(db.String(120), nullable=False)  # Email du client
    customer_name = db.Column(db.String(120), nullable=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    deposit_amount = db.Column(db.Numeric(10, 2), nullable=True)  # acompte 30 % si status=deposit
    stripe_payment_intent_id = db.Column(db.String(255), nullable=True)  # ID du paiement Stripe
    payment_method = db.Column(db.String(50), nullable=True)
    card_last4 = db.Column(db.String(4), nullable=True)  # jamais le PAN complet
    payment_reference = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(50), default='pending')  # pending, deposit, paid, failed, cancelled
    prep_status = db.Column(db.String(32), nullable=True)  # a_preparer → remise
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relations
    order_items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

    def payment_label(self):
        return PAYMENT_LABELS.get(self.status, self.status or 'Inconnu')

    def prep_label(self):
        return PREP_LABELS.get(self.prep_status)

    def remaining_amount(self):
        """Solde encore dû quand seul l'acompte a été encaissé."""
        if self.status != 'deposit' or self.deposit_amount is None:
            return None
        total = Decimal(str(self.total_amount or 0))
        deposit = Decimal(str(self.deposit_amount or 0))
        return (total - deposit).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def to_dict(self):
        deposit = float(self.deposit_amount) if self.deposit_amount is not None else None
        remaining = self.remaining_amount()
        return {
            'id': self.id,
            'user_id': self.user_id,
            'email': self.email,
            'customer_name': self.customer_name,
            'total_amount': float(self.total_amount),  # affichage JSON ; colonne Numeric(10, 2)
            'deposit_amount': deposit,
            'remaining_amount': float(remaining) if remaining is not None else None,
            'stripe_payment_intent_id': self.stripe_payment_intent_id,
            'payment_method': self.payment_method,
            'card_last4': self.card_last4,
            'payment_reference': self.payment_reference,
            'status': self.status,
            'payment_label': self.payment_label(),
            'prep_status': self.prep_status,
            'prep_label': self.prep_label(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'items': [item.to_dict() for item in self.order_items]
        }

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Relations
    product = db.relationship('Product', backref='order_items')
    
    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'quantity': self.quantity,
            'price': float(self.price),  # prix unitaire figé au moment du paiement
            'product': self.product.to_dict() if self.product else None
        }
