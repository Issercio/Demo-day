from .category import Category
from .user import User
from app.extensions import db
from datetime import datetime

# Définition du modèle Product directement dans __init__.py
class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=True)
    is_on_sale = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        category = Category.query.get(self.category_id) if self.category_id else None
        return {
            'id': int(self.id),
            'name': str(self.name),
            'price': float(self.price),
            'category_id': int(self.category_id) if self.category_id else None,
            'is_on_sale': bool(self.is_on_sale) if hasattr(self, 'is_on_sale') else False,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'category': {
                'id': int(category.id),
                'name': str(category.name)
            } if category else None
        }