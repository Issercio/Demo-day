from app.extensions import db
from app.models.base_model import utc_now


SUBSCRIPTION_STATUSES = ('active', 'paused', 'cancelled')


class ShopSubscription(db.Model):
    """Abonnement floral : un paiement démarre le contrat, l’atelier livre chaque période."""

    __tablename__ = 'shop_subscriptions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    customer_name = db.Column(db.String(120), nullable=True)
    plan_slug = db.Column(db.String(40), nullable=False)
    plan_name = db.Column(db.String(120), nullable=False)
    period_months = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')
    deliveries_count = db.Column(db.Integer, nullable=False, default=0)
    next_delivery = db.Column(db.Date, nullable=True)
    address = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'email': self.email,
            'customer_name': self.customer_name,
            'plan_slug': self.plan_slug,
            'plan_name': self.plan_name,
            'period_months': int(self.period_months or 1),
            'price': float(self.price),
            'status': self.status,
            'deliveries_count': int(self.deliveries_count or 0),
            'next_delivery': self.next_delivery.isoformat() if self.next_delivery else None,
            'address': self.address,
            'phone': self.phone,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
