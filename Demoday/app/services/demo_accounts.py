"""Comptes de démo créés au démarrage s'ils n'existent pas encore."""

from decimal import Decimal

from sqlalchemy import func, inspect, text

from app.extensions import db
from app.models.user import User

# Compte client demandé pour la démo (en plus de Marie et de l'admin).
DEMO_ACCOUNTS = (
    ('admin', 'admin@florashop.com', 'admin123', True),
    ('marie', 'marie@test.com', 'marie123', False),
    ('client', 'client@test.com', 'client123', False),
)


def _price(value):
    return Decimal(value)


# Shop.html hides the "Abonnements" category. Prices stay inside each
# category band: cut flowers 18–48 €, compositions 49–98 €, dried 22–54 €.
DEMO_CATALOG = (
    ('Fleurs Fraîches', (
        ('Bouquet Pivoine', _price('45.00'), '#e8a0bf'),
        ('Bouquet Lilas', _price('32.50'), '#c8a2c8'),
        ('Roses jardin', _price('28.90'), '#d94f70'),
        ('Bouquet hortensia', _price('39.90'), '#9bb7e8'),
        ('Botte de tulipes', _price('24.50'), '#e85d4c'),
        ('Tournesols du jardin', _price('26.80'), '#f0c419'),
        ('Pivoines blanches', _price('42.00'), '#f7f1e8'),
        ('Roses garden antique', _price('36.40'), '#c45c6a'),
        ('Bouquet printanier', _price('29.70'), '#f4c2c2'),
        ('Gerbera soleil', _price('21.90'), '#ff9aa2'),
        ('Lis blancs', _price('34.20'), '#f5f0e6'),
        ('Anémones', _price('27.60'), '#6b4c9a'),
        ('Freesias parfumés', _price('23.40'), '#ffe08a'),
        ('Renoncules', _price('31.80'), '#e8917a'),
        ('Dahlias d\'été', _price('33.50'), '#bc6288'),
        ('Bouquet champêtre', _price('37.90'), '#b5e48c'),
    )),
    ('Compositions', (
        ('Centre de table', _price('55.00'), '#d2a0b5'),
        ('Couronne champêtre', _price('62.00'), '#7d9b76'),
        ('Composition pivoine', _price('78.50'), '#e8a0bf'),
        ('Jardinière de saison', _price('68.00'), '#84a59d'),
        ('Bouquet structuré', _price('71.20'), '#c8a2c8'),
        ('Couronne de porte', _price('59.90'), '#9fe2bf'),
        ('Composition rose ancienne', _price('84.40'), '#c45c6a'),
        ('Centre hortensia', _price('73.10'), '#8fb9ff'),
        ('Gerbe cérémonie', _price('92.00'), '#f7f1e8'),
        ('Composition eucalyptus', _price('64.80'), '#7d9b76'),
        ('Bouquet cascade', _price('88.70'), '#d8b4f8'),
        ('Coupe fruits et fleurs', _price('57.30'), '#ffc75f'),
    )),
    ('Fleurs Séchées', (
        ('Botte de lavande', _price('24.90'), '#9b7bb8'),
        ('Bouquet séché blé', _price('22.50'), '#e8d5a3'),
        ('Couronne séchée', _price('48.00'), '#c4a574'),
        ('Gypsophile séché', _price('26.40'), '#eee6ea'),
        ('Eucalyptus séché', _price('29.80'), '#7d9b76'),
        ('Immortelles', _price('32.10'), '#e8b86d'),
        ('Bouquet nude séché', _price('41.60'), '#dcc6b0'),
        ('Herbes de la grange', _price('35.20'), '#c5b48a'),
    )),
)

CATEGORY_PRICE_BANDS = {
    'Fleurs Fraîches': (_price('18.00'), _price('48.00')),
    'Compositions': (_price('49.00'), _price('98.00')),
    'Fleurs Séchées': (_price('22.00'), _price('54.00')),
}


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


def ensure_product_color_column():
    inspector = inspect(db.engine)
    if 'products' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('products')}
    if 'color' not in columns:
        db.session.execute(text('ALTER TABLE products ADD COLUMN color VARCHAR(7)'))
        db.session.commit()


def ensure_demo_catalog():
    """Seed a flower catalog so /shop.html is not empty on a fresh database."""
    from app.models import Category, Product

    ensure_product_color_column()
    for category_name, items in DEMO_CATALOG:
        category = Category.query.filter_by(name=category_name).first()
        if category is None:
            category = Category(name=category_name)
            db.session.add(category)
            db.session.flush()
        for product_name, price, color in items:
            product = Product.query.filter_by(name=product_name).first()
            if product is None:
                db.session.add(Product(
                    name=product_name,
                    price=price,
                    category_id=category.id,
                    color=color,
                ))
            else:
                product.price = price
                product.category_id = category.id
                product.color = color
    db.session.commit()
