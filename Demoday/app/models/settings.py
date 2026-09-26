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
    legal_form = db.Column(db.String(40), nullable=True)
    capital = db.Column(db.String(40), nullable=True)
    rcs_city = db.Column(db.String(80), nullable=True)
    tva_intra = db.Column(db.String(20), nullable=True)
    tva_rate = db.Column(db.Numeric(5, 2), nullable=True)  # % TTC → HT, défaut 10 (fleurs)
    pickup_note = db.Column(db.String(255), nullable=True)
    delivery_fee = db.Column(db.Numeric(10, 2), nullable=False, default=8.90)
    delivery_fee_overseas = db.Column(db.Numeric(10, 2), nullable=True)
    delivery_prefixes = db.Column(db.String(120), nullable=False, default='FR')
    delivery_carrier = db.Column(db.String(80), nullable=True)
    delivery_eta_metro = db.Column(db.String(80), nullable=True)
    delivery_eta_overseas = db.Column(db.String(80), nullable=True)
    closed_weekdays = db.Column(db.String(20), nullable=False, default='6')
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def to_public_dict(self):
        return {
            'legal_name': self.legal_name or 'FloraShop',
            'address': self.address or '',
            'email': self.email or '',
            'phone': self.phone or '',
            'siren': self.siren or '',
            'legal_form': self.legal_form or '',
            'capital': self.capital or '',
            'rcs_city': self.rcs_city or '',
            'tva_intra': self.tva_intra or '',
            'tva_rate': float(self.tva_rate) if self.tva_rate is not None else 10.0,
            'pickup_note': self.pickup_note or 'Retrait à l’atelier aux horaires indiqués.',
            'delivery_fee': float(self.delivery_fee or 0),
            'delivery_fee_overseas': float(self.delivery_fee_overseas)
            if self.delivery_fee_overseas is not None else None,
            'delivery_prefixes': self.delivery_prefixes or 'FR',
            'delivery_carrier': self.delivery_carrier or '',
            'delivery_eta_metro': self.delivery_eta_metro or '24–48 h',
            'delivery_eta_overseas': self.delivery_eta_overseas or '3–5 jours ouvrés',
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
