from app.extensions import db
from app.models.base_model import utc_now


class Cart(db.Model):
    __tablename__ = 'carts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, unique=True)
    guest_token = db.Column(db.String(64), nullable=True, unique=True)
    items_json = db.Column(db.Text, nullable=False, default='[]')
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
