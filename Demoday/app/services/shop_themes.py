"""Season and event themes that map the shop catalog to a moment."""

from datetime import date
from pathlib import Path

from flask import current_app

SHOP_THEMES = (
    {
        'id': 'printemps',
        'label': 'Printemps',
        'kind': 'saison',
        'blurb': 'Tulipes, pivoines et anémones : le jardin qui se réveille.',
        'accent': '#e8a0bf',
        'months': (3, 4, 5),
        'products': (
            'Bouquet printanier',
            'Botte de tulipes',
            'Anémones',
            'Freesias parfumés',
            'Renoncules',
            'Bouquet Pivoine',
            'Pivoines blanches',
            'Bouquet Lilas',
        ),
    },
    {
        'id': 'ete',
        'label': 'Été',
        'kind': 'saison',
        'blurb': 'Tournesols, dahlias et gerberas pour une table ensoleillée.',
        'accent': '#f0c419',
        'months': (6, 7, 8),
        'products': (
            'Tournesols du jardin',
            'Dahlias d\'été',
            'Gerbera soleil',
            'Bouquet champêtre',
            'Roses jardin',
            'Bouquet hortensia',
            'Centre hortensia',
            'Composition pivoine',
        ),
    },
    {
        'id': 'automne',
        'label': 'Automne',
        'kind': 'saison',
        'blurb': 'Couronnes, blé et eucalyptus : des tons chauds de saison.',
        'accent': '#e85d4c',
        'months': (9, 10, 11),
        'products': (
            'Couronne champêtre',
            'Immortelles',
            'Bouquet séché blé',
            'Herbes de la grange',
            'Eucalyptus séché',
            'Composition eucalyptus',
            'Couronne de porte',
            'Jardinière de saison',
        ),
    },
    {
        'id': 'hiver',
        'label': 'Hiver',
        'kind': 'saison',
        'blurb': 'Blancs, roses pâles et couronnes pour éclairer la saison froide.',
        'accent': '#9bb7e8',
        'months': (12, 1, 2),
        'products': (
            'Pivoines blanches',
            'Centre de table',
            'Composition pivoine',
            'Botte de lavande',
            'Bouquet nude séché',
            'Couronne séchée',
            'Couronne de porte',
            'Roses garden antique',
        ),
    },
    {
        'id': 'mariage',
        'label': 'Mariage',
        'kind': 'evenement',
        'blurb': 'Bouquet de mariée, arche et centres de table cérémonie.',
        'accent': '#f7f1e8',
        'months': (),
        'products': (
            'Bouquet de mariée',
            'Bouquet demoiselle',
            'Composition cérémonie',
            'Centre de table mariage',
            'Couronne de mariée',
            'Bouquet cascade mariage',
            'Arche florale',
            'Boutonnières (lot de 6)',
        ),
    },
    {
        'id': 'saint-valentin',
        'label': 'Saint-Valentin',
        'kind': 'evenement',
        'blurb': 'Roses, mini bouquets et gestes à offrir à deux.',
        'accent': '#d94f70',
        'months': (),
        'products': (
            'Rose unique',
            'Roses jardin',
            'Carte et rose',
            'Roses garden antique',
            'Mini bouquet',
            'Fleurs en boîte',
            'Anthurium',
            'Bouquet merci',
        ),
    },
    {
        'id': 'fete-des-meres',
        'label': 'Fête des mères',
        'kind': 'evenement',
        'blurb': 'Pivoines, lilas et orchidées : un bouquet pour dire merci.',
        'accent': '#bc6288',
        'months': (),
        'products': (
            'Bouquet Pivoine',
            'Composition pivoine',
            'Bouquet Lilas',
            'Pivoines blanches',
            'Orchidée rose',
            'Mini bouquet',
            'Bouquet merci',
            'Rose unique',
        ),
    },
    {
        'id': 'noel',
        'label': 'Noël',
        'kind': 'evenement',
        'blurb': 'Couronnes de porte, centres de table et compositions d’hiver.',
        'accent': '#7d9b76',
        'months': (),
        'products': (
            'Couronne de porte',
            'Couronne champêtre',
            'Bouquet séché blé',
            'Coupe fruits et fleurs',
            'Immortelles',
            'Jardinière de saison',
            'Centre de table',
            'Couronne séchée',
        ),
    },
    {
        'id': 'hommage',
        'label': 'Hommage',
        'kind': 'evenement',
        'blurb': 'Gerbes, coussins et compositions en tons doux.',
        'accent': '#9b7bb8',
        'months': (),
        'products': (
            'Gerbe de deuil',
            'Coussin blanc',
            'Composition lys',
            'Bouquet de sympathie',
            'Couronne de deuil',
            'Gerbe rose pâle',
            'Composition verte',
            'Bouquet blanc et lilas',
        ),
    },
    {
        'id': 'cadeau',
        'label': 'Cadeau',
        'kind': 'evenement',
        'blurb': 'Petits gestes prêts à offrir : rose, mini bouquet, plante.',
        'accent': '#ffc75f',
        'months': (),
        'products': (
            'Rose unique',
            'Mini bouquet',
            'Pot-fleur surprise',
            'Carte et rose',
            'Bouquet merci',
            'Composition bureau',
            'Fleurs en boîte',
            'Duo de succulentes',
        ),
    },
)

_THEME_BY_ID = {theme['id']: theme for theme in SHOP_THEMES}


def current_theme_id(today=None):
    month = (today or date.today()).month
    for theme in SHOP_THEMES:
        if theme['kind'] == 'saison' and month in theme['months']:
            return theme['id']
    return 'automne'


def get_theme(theme_id):
    return _THEME_BY_ID.get((theme_id or '').strip().lower())


def product_names_for_theme(theme_id):
    theme = get_theme(theme_id)
    if theme is None:
        raise KeyError(theme_id)
    return theme['products']


def filter_products_by_theme(products, theme_id):
    names = product_names_for_theme(theme_id)
    by_name = {product.name: product for product in products}
    return [by_name[name] for name in names if name in by_name]


def applied_theme_file():
    override = current_app.config.get('SHOP_THEME_PATH')
    if override:
        return Path(override)
    folder = Path(current_app.instance_path)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'shop_theme'


def get_applied_theme_id():
    path = applied_theme_file()
    try:
        stored = path.read_text(encoding='utf-8').strip().lower()
    except OSError:
        return None
    if not stored or stored in ('none', 'all', 'catalogue'):
        return None
    if get_theme(stored) is None:
        return None
    return stored


def set_applied_theme_id(theme_id):
    path = applied_theme_file()
    if theme_id in (None, '', 'none', 'all', 'catalogue'):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return None
    theme = get_theme(theme_id)
    if theme is None:
        raise KeyError(theme_id)
    path.write_text(theme['id'] + '\n', encoding='utf-8')
    return theme['id']


def themes_payload(today=None):
    season = current_theme_id(today)
    applied = get_applied_theme_id()
    return {
        'current': season,
        'season': season,
        'applied': applied,
        'themes': [
            {
                'id': theme['id'],
                'label': theme['label'],
                'kind': theme['kind'],
                'blurb': theme['blurb'],
                'accent': theme['accent'],
                'product_names': list(theme['products']),
                'is_current_season': theme['id'] == season,
                'is_applied': theme['id'] == applied,
            }
            for theme in SHOP_THEMES
        ],
    }
