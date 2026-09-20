from .category import Category
from .user import User
from .order import Order, OrderItem
from .shop_theme import ShopTheme, ShopVitrine, ThemeProduct
from app.extensions import db

# Définition du modèle Product directement dans __init__.py
class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)  # euros, jamais un float binaire
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=True)
    is_on_sale = db.Column(db.Boolean, default=False)
    color = db.Column(db.String(7), nullable=True)  # hex #rrggbb pour le filtre boutique
    image = db.Column(db.String(255), nullable=True)  # chemin /static/img/products/...

    category = db.relationship('Category', back_populates='products')
    theme_links = db.relationship('ThemeProduct', back_populates='product', cascade='all, delete-orphan')

    def to_dict(self):
        category = self.category
        color = str(self.color).lower() if self.color else None
        return {
            'id': int(self.id),
            'name': str(self.name),
            # JSON n'a pas de Decimal : on envoie un number, le stockage reste Numeric.
            'price': float(self.price),
            'category_id': int(self.category_id) if self.category_id else None,
            'is_on_sale': bool(self.is_on_sale) if hasattr(self, 'is_on_sale') else False,
            'color': color,
            'hex_color': color,
            'image': str(self.image) if self.image else None,
            'category': {
                'id': int(category.id),
                'name': str(category.name)
            } if category else None
        }