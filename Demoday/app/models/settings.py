from app.extensions import db
from app.models.base_model import utc_now


class ShopSettings(db.Model):
    __tablename__ = 'shop_settings'

    id = db.Column(db.Integer, primary_key=True)
    legal_name = db.Column(db.String(120), nullable=False, default='FloraShop')
    address = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    siren = db.Column(db.String(20), nullable=True)
    pickup_note = db.Column(db.String(255), nullable=True)
    delivery_fee = db.Column(db.Numeric(10, 2), nullable=False, default=8.90)
    delivery_prefixes = db.Column(db.String(120), nullable=False, default='75,77,78,91,92,93,94,95')
    closed_weekdays = db.Column(db.String(20), nullable=False, default='6')
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def to_public_dict(self):
        return {
            'legal_name': self.legal_name or 'FloraShop',
            'address': self.address or '',
            'email': self.email or '',
            'phone': self.phone or '',
            'siren': self.siren or '',
            'pickup_note': self.pickup_note or 'Retrait à l’atelier aux horaires indiqués.',
            'delivery_fee': float(self.delivery_fee or 0),
            'delivery_prefixes': self.delivery_prefixes or '',
            'closed_weekdays': self.closed_weekdays or '6',
        }


class PromoCode(db.Model):
    __tablename__ = 'promo_codes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(40), nullable=False, unique=True)
    percent = db.Column(db.Integer, nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    uses_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'percent': self.percent,
            'amount': float(self.amount) if self.amount is not None else None,
            'active': bool(self.active),
            'uses_count': int(self.uses_count or 0),
        }
