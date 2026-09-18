"""Season and event themes that map the shop catalog to a moment."""

import json
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
    ids = parse_theme_ids(theme_id)
    names = product_names_for_ids(ids)
    by_name = {product.name: product for product in products}
    return [by_name[name] for name in names if name in by_name]


def parse_theme_ids(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        parts = value
    else:
        parts = str(value).replace('+', ',').split(',')
    ids = []
    seen = set()
    for part in parts:
        theme_id = str(part or '').strip().lower()
        if not theme_id or theme_id in seen:
            continue
        if get_theme(theme_id) is None:
            raise KeyError(theme_id)
        seen.add(theme_id)
        ids.append(theme_id)
    return ids


def product_names_for_ids(theme_ids):
    names = []
    seen = set()
    for theme_id in theme_ids:
        for name in product_names_for_theme(theme_id):
            if name in seen:
                continue
            seen.add(name)
            names.append(name)
    return names


def applied_theme_file():
    override = current_app.config.get('SHOP_THEME_PATH')
    if override:
        return Path(override)
    folder = Path(current_app.instance_path)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'shop_theme'


def _empty_applied():
    return {'season': None, 'theme': None}


def _normalize_slot(theme_id, expected_kind):
    if theme_id in (None, '', 'none', 'all', 'catalogue'):
        return None
    theme = get_theme(theme_id)
    if theme is None or theme['kind'] != expected_kind:
        raise KeyError(theme_id)
    return theme['id']


def applied_ids(applied=None):
    applied = applied if applied is not None else get_applied_vitrine()
    return [theme_id for theme_id in (applied.get('season'), applied.get('theme')) if theme_id]


def get_applied_vitrine():
    path = applied_theme_file()
    try:
        stored = path.read_text(encoding='utf-8').strip()
    except OSError:
        return _empty_applied()
    if not stored or stored.lower() in ('none', 'all', 'catalogue'):
        return _empty_applied()
    if stored.startswith('{'):
        try:
            data = json.loads(stored)
        except json.JSONDecodeError:
            return _empty_applied()
        try:
            return {
                'season': _normalize_slot(data.get('season'), 'saison'),
                'theme': _normalize_slot(data.get('theme'), 'evenement'),
            }
        except KeyError:
            return _empty_applied()
    try:
        ids = parse_theme_ids(stored)
    except KeyError:
        return _empty_applied()
    season = None
    theme = None
    for theme_id in ids:
        item = get_theme(theme_id)
        if item['kind'] == 'saison':
            season = item['id']
        else:
            theme = item['id']
    return {'season': season, 'theme': theme}


def get_applied_theme_id():
    ids = applied_ids()
    if not ids:
        return None
    return '+'.join(ids)


def set_applied_vitrine(season_id=None, theme_id=None):
    applied = {
        'season': _normalize_slot(season_id, 'saison'),
        'theme': _normalize_slot(theme_id, 'evenement'),
    }
    path = applied_theme_file()
    if applied['season'] is None and applied['theme'] is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return applied
    path.write_text(json.dumps(applied, ensure_ascii=False) + '\n', encoding='utf-8')
    return applied


def set_applied_theme_id(theme_id):
    if theme_id in (None, '', 'none', 'all', 'catalogue'):
        return set_applied_vitrine(None, None)
    ids = parse_theme_ids(theme_id)
    current = get_applied_vitrine()
    season = current['season']
    theme = current['theme']
    for item_id in ids:
        item = get_theme(item_id)
        if item['kind'] == 'saison':
            season = None if season == item['id'] and len(ids) == 1 else item['id']
        else:
            theme = None if theme == item['id'] and len(ids) == 1 else item['id']
    return set_applied_vitrine(season, theme)


def vitrine_label(applied):
    labels = [get_theme(theme_id)['label'] for theme_id in applied_ids(applied)]
    return ' + '.join(labels) if labels else None


def vitrine_blurb(applied):
    blurbs = [get_theme(theme_id)['blurb'] for theme_id in applied_ids(applied)]
    return ' '.join(blurbs) if blurbs else None


def themes_payload(today=None):
    calendar_season = current_theme_id(today)
    applied = get_applied_vitrine()
    ids = applied_ids(applied)
    return {
        'current': calendar_season,
        'season': calendar_season,
        'applied': get_applied_theme_id(),
        'applied_season': applied['season'],
        'applied_theme': applied['theme'],
        'applied_ids': ids,
        'label': vitrine_label(applied),
        'blurb': vitrine_blurb(applied),
        'product_names': product_names_for_ids(ids),
        'themes': [
            {
                'id': theme['id'],
                'label': theme['label'],
                'kind': theme['kind'],
                'blurb': theme['blurb'],
                'accent': theme['accent'],
                'product_names': list(theme['products']),
                'is_current_season': theme['id'] == calendar_season,
                'is_applied': theme['id'] in ids,
            }
            for theme in SHOP_THEMES
        ],
    }
