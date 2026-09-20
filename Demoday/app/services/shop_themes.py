"""Saisons et thèmes événement : listes de noms produits, pas une table SQL."""

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

def current_theme_id(today=None):
    month = (today or date.today()).month
    for theme in all_themes():
        if theme['kind'] == 'saison' and month in theme.get('months', ()):
            return theme['id']
    return 'automne'


def get_theme(theme_id):
    wanted = (theme_id or '').strip().lower()
    for theme in all_themes():
        if theme['id'] == wanted:
            return theme
    return None


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
    # Virgules, pas de '+' : printemps,mariage reste sûr dans une query string.
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        parts = value
    else:
        parts = str(value).replace('+', ',').replace(' ', ',').split(',')
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
    # Combo = union des listes (Printemps + Mariage), sans doublon.
    names = []
    seen = set()
    for theme_id in theme_ids:
        for name in product_names_for_theme(theme_id):
            if name in seen:
                continue
            seen.add(name)
            names.append(name)
    return names


def _builtin_ids():
    return {theme['id'] for theme in SHOP_THEMES}


def custom_themes_file():
    override = current_app.config.get('SHOP_CUSTOM_THEMES_PATH')
    if override:
        return Path(override)
    folder = Path(current_app.instance_path)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'custom_themes.json'


def _theme_slug(label):
    from app.services.demo_accounts import product_slug
    slug = product_slug(label) or 'theme'
    theme_id = f'custom-{slug}'
    existing = {theme['id'] for theme in all_themes()}
    if theme_id not in existing:
        return theme_id
    suffix = 2
    while f'{theme_id}-{suffix}' in existing:
        suffix += 1
    return f'{theme_id}-{suffix}'


def _normalize_custom_theme(raw):
    if not isinstance(raw, dict):
        return None
    theme_id = str(raw.get('id') or '').strip().lower()
    label = str(raw.get('label') or '').strip()
    kind = str(raw.get('kind') or 'evenement').strip().lower()
    if kind not in ('saison', 'evenement'):
        kind = 'evenement'
    if not theme_id or not label:
        return None
    products = raw.get('products') or ()
    names = tuple(str(name).strip() for name in products if str(name).strip())
    months = tuple(int(month) for month in (raw.get('months') or ()) if str(month).isdigit() and 1 <= int(month) <= 12)
    accent = str(raw.get('accent') or '#bc6288').strip().lower()
    if len(accent) != 7 or not accent.startswith('#'):
        accent = '#bc6288'
    return {
        'id': theme_id,
        'label': label[:80],
        'kind': kind,
        'blurb': str(raw.get('blurb') or '').strip()[:240],
        'accent': accent,
        'months': months,
        'products': names,
        'custom': True,
    }


def load_custom_themes():
    path = custom_themes_file()
    try:
        stored = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(stored, list):
        return []
    themes = []
    seen = set(_builtin_ids())
    for raw in stored:
        theme = _normalize_custom_theme(raw)
        if theme is None or theme['id'] in seen:
            continue
        seen.add(theme['id'])
        themes.append(theme)
    return themes


def save_custom_themes(themes):
    path = custom_themes_file()
    payload = []
    for theme in themes:
        payload.append({
            'id': theme['id'],
            'label': theme['label'],
            'kind': theme['kind'],
            'blurb': theme.get('blurb') or '',
            'accent': theme.get('accent') or '#bc6288',
            'months': list(theme.get('months') or ()),
            'products': list(theme.get('products') or ()),
        })
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def all_themes():
    return list(SHOP_THEMES) + load_custom_themes()


def create_custom_theme(data):
    from app.models import Product

    label = str((data or {}).get('label') or '').strip()
    if len(label) < 2:
        raise ValueError('Le nom du thème est requis.')
    kind = str((data or {}).get('kind') or 'evenement').strip().lower()
    if kind not in ('saison', 'evenement'):
        raise ValueError('Le type doit être saison ou thème.')
    raw_products = (data or {}).get('products') or []
    if isinstance(raw_products, str):
        raw_products = [part.strip() for part in raw_products.split(',')]
    wanted = [str(name).strip() for name in raw_products if str(name).strip()]
    if not wanted:
        raise ValueError('Choisissez au moins un bouquet pour ce thème.')
    catalog = {product.name for product in Product.query.all()}
    names = tuple(name for name in wanted if name in catalog)
    if not names:
        raise ValueError('Aucun produit du catalogue ne correspond à ce thème.')
    accent = str((data or {}).get('accent') or '#bc6288').strip().lower()
    if len(accent) != 7 or not accent.startswith('#'):
        accent = '#bc6288'
    months = []
    for month in (data or {}).get('months') or ():
        try:
            value = int(month)
        except (TypeError, ValueError):
            continue
        if 1 <= value <= 12:
            months.append(value)
    theme = {
        'id': _theme_slug(label),
        'label': label[:80],
        'kind': kind,
        'blurb': str((data or {}).get('blurb') or '').strip()[:240],
        'accent': accent,
        'months': tuple(months),
        'products': names,
        'custom': True,
    }
    custom = load_custom_themes()
    custom.append(theme)
    save_custom_themes(custom)
    return theme


def delete_custom_theme(theme_id):
    theme_id = (theme_id or '').strip().lower()
    if theme_id in _builtin_ids():
        raise ValueError('Les saisons et thèmes du catalogue ne peuvent pas être supprimés.')
    custom = load_custom_themes()
    remaining = [theme for theme in custom if theme['id'] != theme_id]
    if len(remaining) == len(custom):
        raise KeyError(theme_id)
    save_custom_themes(remaining)
    applied = get_applied_vitrine()
    season = None if applied.get('season') == theme_id else applied.get('season')
    event = None if applied.get('theme') == theme_id else applied.get('theme')
    if season != applied.get('season') or event != applied.get('theme'):
        set_applied_vitrine(season, event)
    return theme_id


def applied_theme_file():
    override = current_app.config.get('SHOP_THEME_PATH')
    if override:
        return Path(override)
    folder = Path(current_app.instance_path)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'shop_theme'  # JSON {season, theme} partagé par tous les visiteurs


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
    return ','.join(ids)


def set_applied_vitrine(season_id=None, theme_id=None):
    # Un slot saison + un slot événement. Les deux vides = catalogue complet.
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
                'is_custom': bool(theme.get('custom')),
            }
            for theme in all_themes()
        ],
    }
