"""Comptes de démo créés au démarrage s'ils n'existent pas encore."""

import re
import unicodedata
from decimal import Decimal

from sqlalchemy import func, inspect, text

from app.extensions import db
from app.models.user import User


def product_slug(name):
    ascii_name = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', ascii_name.lower()).strip('-')


def product_image_path(name):
    slug = product_slug(name)
    return f'/static/img/products/{slug}.jpg' if slug else None

# Compte client demandé pour la démo (en plus de Marie et de l'admin).
# username = prénom + nom, affiché au checkout et sur les commandes.
DEMO_ACCOUNTS = (
    ('Camille Pivoine', 'admin@florashop.com', 'admin123', True),
    ('Marie Dupont', 'marie@test.com', 'marie123', False),
    ('Léa Martin', 'client@test.com', 'client123', False),
)


def _price(value):
    return Decimal(value)  # prix catalogue en Decimal, jamais float


HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def normalize_hex_color(value, default=None):
    """Accepte seulement #rrggbb : sinon une teinte finirait dans style=background."""
    raw = str(value or '').strip()
    if HEX_COLOR_RE.fullmatch(raw):
        return raw.lower()
    return default


# Same 12 swatches as shop.html colorPalette. Every product color must be one of these.
PINK = '#e8a0bf'
LILAC = '#c8a2c8'
ROSE = '#d94f70'
BLUE = '#9bb7e8'
CORAL = '#e85d4c'
YELLOW = '#f0c419'
GREEN = '#7d9b76'
CREAM = '#f7f1e8'
LAVENDER = '#9b7bb8'
GOLD = '#ffc75f'
PURPLE = '#6b4c9a'
VINTAGE = '#bc6288'

SHOP_COLOR_PALETTE = (
    PINK, LILAC, ROSE, BLUE, CORAL, YELLOW,
    GREEN, CREAM, LAVENDER, GOLD, PURPLE, VINTAGE,
)

# Shop.html hides "Abonnements". Prices stay inside each category band.
DEMO_CATALOG = (
    ('Fleurs Fraîches', (
        ('Bouquet Pivoine', _price('45.00'), PINK),
        ('Bouquet Lilas', _price('32.50'), LILAC),
        ('Roses jardin', _price('28.90'), ROSE),
        ('Bouquet hortensia', _price('39.90'), BLUE),
        ('Botte de tulipes', _price('24.50'), CORAL),
        ('Tournesols du jardin', _price('26.80'), YELLOW),
        ('Pivoines blanches', _price('42.00'), CREAM),
        ('Roses garden antique', _price('36.40'), VINTAGE),
        ('Bouquet printanier', _price('29.70'), PINK),
        ('Gerbera soleil', _price('21.90'), CORAL),
        ('Lis blancs', _price('34.20'), CREAM),
        ('Anémones', _price('27.60'), PURPLE),
        ('Freesias parfumés', _price('23.40'), YELLOW),
        ('Renoncules', _price('31.80'), CORAL),
        ('Dahlias d\'été', _price('33.50'), VINTAGE),
        ('Bouquet champêtre', _price('37.90'), GREEN),
    )),
    ('Compositions', (
        ('Centre de table', _price('55.00'), PINK),
        ('Couronne champêtre', _price('62.00'), GREEN),
        ('Composition pivoine', _price('78.50'), PINK),
        ('Jardinière de saison', _price('68.00'), GREEN),
        ('Bouquet structuré', _price('71.20'), LILAC),
        ('Couronne de porte', _price('59.90'), GREEN),
        ('Composition rose ancienne', _price('84.40'), ROSE),
        ('Centre hortensia', _price('73.10'), BLUE),
        ('Gerbe cérémonie', _price('92.00'), CREAM),
        ('Composition eucalyptus', _price('64.80'), GREEN),
        ('Bouquet cascade', _price('88.70'), LAVENDER),
        ('Coupe fruits et fleurs', _price('57.30'), GOLD),
    )),
    ('Fleurs Séchées', (
        ('Botte de lavande', _price('24.90'), LAVENDER),
        ('Bouquet séché blé', _price('22.50'), GOLD),
        ('Couronne séchée', _price('48.00'), GREEN),
        ('Gypsophile séché', _price('26.40'), CREAM),
        ('Eucalyptus séché', _price('29.80'), GREEN),
        ('Immortelles', _price('32.10'), GOLD),
        ('Bouquet nude séché', _price('41.60'), CREAM),
        ('Herbes de la grange', _price('35.20'), GREEN),
    )),
    ('Plantes d\'intérieur', (
        ('Monstera deliciosa', _price('38.90'), GREEN),
        ('Pilea peperomioides', _price('21.40'), GREEN),
        ('Sansevieria', _price('24.80'), GREEN),
        ('Orchidée blanche', _price('42.00'), CREAM),
        ('Orchidée rose', _price('39.50'), PINK),
        ('Calathea', _price('27.60'), GREEN),
        ('Ficus lyrata', _price('36.20'), GREEN),
        ('Anthurium', _price('29.90'), ROSE),
        ('Succulente soleil', _price('16.50'), GOLD),
        ('Bonsaï', _price('41.80'), GREEN),
    )),
    ('Mariage & Événements', (
        ('Bouquet de mariée', _price('148.00'), CREAM),
        ('Bouquet demoiselle', _price('89.00'), PINK),
        ('Composition cérémonie', _price('132.00'), BLUE),
        ('Centre de table mariage', _price('96.40'), LILAC),
        ('Gerbe d\'honneur', _price('118.00'), ROSE),
        ('Couronne de mariée', _price('82.70'), LAVENDER),
        ('Bouquet cascade mariage', _price('155.00'), PINK),
        ('Déco église', _price('139.50'), CREAM),
        ('Arche florale', _price('165.00'), PINK),
        ('Boutonnières (lot de 6)', _price('78.00'), ROSE),
    )),
    ('Deuil', (
        ('Gerbe de deuil', _price('88.00'), LAVENDER),
        ('Coussin blanc', _price('64.50'), CREAM),
        ('Composition lys', _price('79.20'), CREAM),
        ('Bouquet de sympathie', _price('54.80'), LILAC),
        ('Couronne de deuil', _price('92.00'), PURPLE),
        ('Gerbe rose pâle', _price('71.40'), PINK),
        ('Composition verte', _price('58.90'), GREEN),
        ('Bouquet blanc et lilas', _price('49.30'), LILAC),
    )),
    ('Cadeaux', (
        ('Rose unique', _price('12.90'), ROSE),
        ('Mini bouquet', _price('18.40'), PINK),
        ('Pot-fleur surprise', _price('24.70'), GOLD),
        ('Carte et rose', _price('15.60'), VINTAGE),
        ('Bouquet merci', _price('22.80'), CORAL),
        ('Composition bureau', _price('32.50'), BLUE),
        ('Fleurs en boîte', _price('36.90'), LILAC),
        ('Duo de succulentes', _price('19.20'), GREEN),
    )),
)

CATEGORY_PRICE_BANDS = {
    'Fleurs Fraîches': (_price('18.00'), _price('48.00')),
    'Compositions': (_price('49.00'), _price('98.00')),
    'Fleurs Séchées': (_price('22.00'), _price('54.00')),
    'Plantes d\'intérieur': (_price('16.00'), _price('45.00')),
    'Mariage & Événements': (_price('75.00'), _price('165.00')),
    'Deuil': (_price('45.00'), _price('95.00')),
    'Cadeaux': (_price('12.00'), _price('38.00')),
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
        user.username = username
        user.is_admin = is_admin  # à chaque boot : Camille reste fleuriste, Marie/Léa clientes
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


def ensure_product_image_column():
    inspector = inspect(db.engine)
    if 'products' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('products')}
    if 'image' not in columns:
        db.session.execute(text('ALTER TABLE products ADD COLUMN image VARCHAR(255)'))
        db.session.commit()


def ensure_demo_catalog():
    """Remplit le shop au démarrage : 7 catégories, prix Decimal, photos, couleurs filtre."""
    from app.models import Category, Product

    ensure_product_color_column()
    ensure_product_image_column()
    for category_name, items in DEMO_CATALOG:
        category = Category.query.filter_by(name=category_name).first()
        if category is None:
            category = Category(name=category_name)
            db.session.add(category)
            db.session.flush()
        for product_name, price, color in items:
            image = product_image_path(product_name)
            product = Product.query.filter_by(name=product_name).first()
            if product is None:
                db.session.add(Product(
                    name=product_name,
                    price=price,
                    category_id=category.id,
                    color=color,
                    image=image,
                ))
            else:
                product.price = price
                product.category_id = category.id
                product.color = color
                product.image = image
    db.session.commit()
    from app.services.shop_themes import ensure_shop_themes
    ensure_shop_themes()
