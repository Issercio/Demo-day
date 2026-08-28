from app import db
from datetime import datetime

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relation avec Product
    products = db.relationship('Product', backref='category_ref', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, name):
        self.name = name
    
    def to_dict(self):
        # VALIDATION STRICTE
        if self.id is None:
            raise ValueError(f"Category '{self.name}' has no ID!")
        
        return {
            'id': int(self.id),
            'name': str(self.name),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Category {self.id}: {self.name}>'
