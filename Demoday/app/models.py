from . import db
from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': int(self.id),
            'username': str(self.username),
            'email': str(self.email),
            'is_admin': bool(self.is_admin)
        }

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': int(self.id),
            'name': str(self.name),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Product(db.Model):
    __tablename__ = 'products'
    
    # COLONNES EXACTEMENT COMME DANS LA BASE
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)  # Pas DECIMAL, mais Float pour correspondre
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=True)
    stock = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # AUCUNE autre colonne comme is_on_sale !
    
    def to_dict(self):
        category = Category.query.get(self.category_id) if self.category_id else None
        return {
            'id': int(self.id),
            'name': str(self.name),
            'price': float(self.price),
            'stock': int(self.stock),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'category': {
                'id': int(category.id),
                'name': str(category.name)
            } if category else None
        }