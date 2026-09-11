"""Idempotent catalog seed for local/dev environments.

Populates a handful of categories and products through the SQLAlchemy models
so the shop has something to display. Safe to run repeatedly: existing rows are
left untouched and only missing products are inserted.
"""

from app import create_app, db
from app.models import Category, Product

CATALOG = {
    'Fleurs Fraîches': [
        ('Bouquet Roses Rouges', 29.99),
        ('Bouquet Printanier', 34.99),
        ('Lys Blancs', 39.99),
    ],
    'Vases': [
        ('Vase Cristal', 49.99),
        ('Vase Moderne', 39.99),
    ],
    'Parfums': [
        ('Bougie Jasmin', 19.99),
    ],
    "Plantes d'Intérieur": [
        ('Orchidée', 45.99),
    ],
    'Accessoires': [
        ('Kit Jardinage', 24.99),
    ],
    'Compositions': [
        ('Centre de Table', 59.99),
    ],
    'Cadeaux': [
        ('Coffret Floral', 69.99),
    ],
}


def seed():
    app = create_app()
    with app.app_context():
        created = 0
        for category_name, products in CATALOG.items():
            category = Category.query.filter_by(name=category_name).first()
            if category is None:
                category = Category(name=category_name)
                db.session.add(category)
                db.session.flush()
            for name, price in products:
                if Product.query.filter_by(name=name).first() is None:
                    db.session.add(Product(name=name, price=price, category_id=category.id))
                    created += 1
        db.session.commit()
        total = Product.query.count()
        print(f"Seed terminé: {created} produit(s) ajouté(s), {total} au total.")


if __name__ == '__main__':
    seed()
