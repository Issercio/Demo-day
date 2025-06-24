# app/models/price.py

from app.extensions import db
from .base_model import BaseModel

class Price(BaseModel):
    __tablename__ = 'prices'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    # Ajoute d'autres champs si besoin

    def __repr__(self):
        return f"<Price {self.id} - {self.amount}>"
