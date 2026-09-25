"""Vitrine : saisons et thèmes liés aux produits en base, plus un fichier JSON."""

from app.extensions import db


class ShopTheme(db.Model):
    __tablename__ = 'shop_themes'

    id = db.Column(db.String(80), primary_key=True)
    label = db.Column(db.String(80), nullable=False)
    kind = db.Column(db.String(20), nullable=False)  # saison | evenement
    blurb = db.Column(db.String(240), default='')
    accent = db.Column(db.String(7), default='#bc6288')
    months = db.Column(db.String(32), default='')  # "3,4,5" pour une saison
    is_builtin = db.Column(db.Boolean, default=False)  # thème livré vs créé par le fleuriste
    is_active = db.Column(db.Boolean, default=True)  # False = soft-delete (Mariage, Cadeau, …)

    links = db.relationship(
        'ThemeProduct',
        back_populates='theme',
        cascade='all, delete-orphan',
        order_by='ThemeProduct.position',
    )

    @property
    def product_names(self):
        return tuple(link.product.name for link in self.links if link.product)

    @property
    def month_tuple(self):
        months = []
        for part in (self.months or '').split(','):
            part = part.strip()
            if part.isdigit():
                months.append(int(part))
        return tuple(months)


class ThemeProduct(db.Model):
    __tablename__ = 'theme_products'

    theme_id = db.Column(
        db.String(80),
        db.ForeignKey('shop_themes.id', ondelete='CASCADE'),
        primary_key=True,
    )
    product_id = db.Column(
        db.Integer,
        db.ForeignKey('products.id', ondelete='CASCADE'),
        primary_key=True,
    )
    position = db.Column(db.Integer, nullable=False, default=0)

    theme = db.relationship('ShopTheme', back_populates='links')
    product = db.relationship('Product', back_populates='theme_links')


class ShopVitrineTheme(db.Model):
    """Thèmes événement actuellement posés sur la vitrine (0 à N, ordre conservé)."""
    __tablename__ = 'shop_vitrine_themes'

    vitrine_id = db.Column(
        db.Integer,
        db.ForeignKey('shop_vitrine.id', ondelete='CASCADE'),
        primary_key=True,
    )
    theme_id = db.Column(
        db.String(80),
        db.ForeignKey('shop_themes.id', ondelete='CASCADE'),
        primary_key=True,
    )
    position = db.Column(db.Integer, nullable=False, default=0)

    vitrine = db.relationship('ShopVitrine', back_populates='event_links')
    theme = db.relationship('ShopTheme')


class ShopVitrine(db.Model):
    """Une seule ligne : une saison, plus 0 à N thèmes événement."""
    __tablename__ = 'shop_vitrine'

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(
        db.String(80),
        db.ForeignKey('shop_themes.id', ondelete='SET NULL'),
        nullable=True,
    )
    theme_id = db.Column(
        db.String(80),
        db.ForeignKey('shop_themes.id', ondelete='SET NULL'),
        nullable=True,
    )  # premier thème événement, pour rester compatible avec l'ancienne colonne
    auto_mode = db.Column(db.Boolean, default=True)  # calendrier (saison + fêtes) tant que le fleuriste ne force pas

    season = db.relationship('ShopTheme', foreign_keys=[season_id])
    theme = db.relationship('ShopTheme', foreign_keys=[theme_id])
    event_links = db.relationship(
        'ShopVitrineTheme',
        back_populates='vitrine',
        cascade='all, delete-orphan',
        order_by='ShopVitrineTheme.position',
    )
