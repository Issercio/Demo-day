"""Comptes de démo créés au démarrage s'ils n'existent pas encore."""

from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models.user import User

# Compte client demandé pour la démo (en plus de Marie et de l'admin).
DEMO_ACCOUNTS = (
    ('admin', 'admin@florashop.com', 'admin123', True),
    ('marie', 'marie@test.com', 'marie123', False),
    ('client', 'client@test.com', 'client123', False),
)

# Shop.html hides the "Abonnements" category, so a fresh SQLite DB needs flowers.
DEMO_CATALOG = (
    ('Fleurs Fraîches', (
        ('Bouquet Pivoine', Decimal('45.00')),
        ('Bouquet Lilas', Decimal('32.50')),
        ('Roses jardin', Decimal('28.90')),
    )),
    ('Compositions', (
        ('Centre de table', Decimal('55.00')),
        ('Couronne champêtre', Decimal('62.00')),
    )),
)


def ensure_demo_accounts():
    created = []
    for username, email, password, is_admin in DEMO_ACCOUNTS:
        user = User.query.filter(func.lower(User.email) == email.lower()).first()
        if user is None:
            user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, email=email, is_admin=is_admin, password='x')
            user.set_password(password)
            db.session.add(user)
            created.append(email)
            continue
        user.email = email
        user.is_admin = is_admin
        # Compte démo déjà là mais hash incompatible (bcrypt, etc.) → on rétablit marie123 / admin123.
        if not user.check_password(password) or not user.has_modern_hash():
            user.set_password(password)
    db.session.commit()
    return created


def ensure_demo_catalog():
    """Seed a small flower catalog so /shop.html is not empty on a fresh database."""
    from app.models import Category, Product

    for category_name, items in DEMO_CATALOG:
        category = Category.query.filter_by(name=category_name).first()
        if category is None:
            category = Category(name=category_name)
            db.session.add(category)
            db.session.flush()
        for product_name, price in items:
            product = Product.query.filter_by(name=product_name).first()
            if product is None:
                db.session.add(Product(
                    name=product_name,
                    price=price,
                    category_id=category.id,
                ))
            else:
                product.price = price
                product.category_id = category.id
    db.session.commit()
