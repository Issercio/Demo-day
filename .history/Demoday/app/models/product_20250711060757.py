from app.extensions import db

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    is_on_sale = db.Column(db.Boolean, default=False)
    category = db.relationship('Category', back_populates='products')
    
    def to_dict(self):
        """Convertit l'objet Product en dictionnaire pour l'API"""
        try:
            result = {
                'id': int(self.id) if self.id is not None else None,
                'name': str(self.name) if self.name else '',
                'price': float(self.price) if self.price is not None else 0.0,
                'category_id': int(self.category_id) if self.category_id is not None else None,
                'is_on_sale': bool(self.is_on_sale) if hasattr(self, 'is_on_sale') else False
            }
            
            # Ajouter les infos de catégorie si disponibles
            if hasattr(self, 'category') and self.category:
                result['category'] = {
                    'id': int(self.category.id),
                    'name': str(self.category.name)
                }
            elif self.category_id:
                # Fallback : charger la catégorie si nécessaire
                from app.models.category import Category
                category = Category.query.get(self.category_id)
                if category:
                    result['category'] = {
                        'id': int(category.id),
                        'name': str(category.name)
                    }
            
            return result
        except Exception as e:
            print(f"Erreur dans Product.to_dict(): {str(e)}")
            # Retourner un minimum en cas d'erreur
            return {
                'id': getattr(self, 'id', None),
                'name': getattr(self, 'name', ''),
                'price': getattr(self, 'price', 0.0),
                'category_id': getattr(self, 'category_id', None),
                'is_on_sale': False
            }