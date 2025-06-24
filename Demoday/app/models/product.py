from .base_model import BaseModel
from sqlalchemy.orm import relationship
from app.extensions import db

class Product(BaseModel, db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    is_on_sale = db.Column(db.Boolean, default=False)
    sale_price = db.Column(db.Float, nullable=True)

    # Si tu veux la relation avec Category :
    # category = db.relationship('Category', back_populates='products')

    def __repr__(self):
        return f"<Product {self.id} - {self.name}>"
