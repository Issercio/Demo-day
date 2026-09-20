"""Saisons et thèmes événement : listes liées aux produits en base."""

import json
from datetime import date
from pathlib import Path

from flask import current_app

from app.extensions import db

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


def _theme_dict(row):
    return {
        'id': row.id,
        'label': row.label,
        'kind': row.kind,
        'blurb': row.blurb or '',
        'accent': row.accent or '#bc6288',
        'months': row.month_tuple,
        'products': row.product_names,
        'custom': not row.is_builtin,
    }


def _set_theme_products(row, names, by_name):
    from app.models.shop_theme import ThemeProduct

    row.links.clear()
    position = 0
    seen = set()
    for name in names:
        product = by_name.get(name)
        if product is None or product.id in seen:
            continue
        seen.add(product.id)
        row.links.append(ThemeProduct(product_id=product.id, position=position))
        position += 1


def _legacy_custom_path():
    override = current_app.config.get('SHOP_CUSTOM_THEMES_PATH')
    if override:
        return Path(override)
    return Path(current_app.instance_path) / 'custom_themes.json'


def _legacy_vitrine_path():
    override = current_app.config.get('SHOP_THEME_PATH')
    if override:
        return Path(override)
    return Path(current_app.instance_path) / 'shop_theme'


def _import_legacy_json(by_name):
    """Une fois : anciens fichiers instance/ → lignes SQL, puis on n’y écrit plus."""
    from app.models.shop_theme import ShopTheme

    path = _legacy_custom_path()
    try:
        stored = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(stored, list):
        themes, removed = stored, []
    elif isinstance(stored, dict):
        themes, removed = stored.get('themes') or [], stored.get('removed') or []
    else:
        return
    for theme_id in removed:
        row = db.session.get(ShopTheme, str(theme_id).strip().lower())
        if row is not None and row.is_builtin:
            row.is_active = False
    for raw in themes:
        if not isinstance(raw, dict):
            continue
        theme_id = str(raw.get('id') or '').strip().lower()
        label = str(raw.get('label') or '').strip()
        if not theme_id or not label or db.session.get(ShopTheme, theme_id):
            continue
        accent = str(raw.get('accent') or '#bc6288').strip().lower()
        if len(accent) != 7 or not accent.startswith('#'):
            accent = '#bc6288'
        row = ShopTheme(
            id=theme_id,
            label=label[:80],
            kind='evenement',
            blurb=str(raw.get('blurb') or '').strip()[:240],
            accent=accent,
            months='',
            is_builtin=False,
            is_active=True,
        )
        db.session.add(row)
        _set_theme_products(row, raw.get('products') or (), by_name)


def ensure_shop_themes():
    """Crée les tables vitrine et relie chaque thème aux Product.id du catalogue."""
    from app.models import Product
    from app.models.shop_theme import ShopTheme, ShopVitrine

    db.create_all()
    by_name = {product.name: product for product in Product.query.all()}
    for spec in SHOP_THEMES:
        row = db.session.get(ShopTheme, spec['id'])
        if row is None:
            row = ShopTheme(
                id=spec['id'],
                label=spec['label'],
                kind=spec['kind'],
                blurb=spec['blurb'],
                accent=spec['accent'],
                months=','.join(str(month) for month in spec.get('months') or ()),
                is_builtin=True,
                is_active=True,
            )
            db.session.add(row)
            _set_theme_products(row, spec['products'], by_name)
        elif row.is_builtin and row.is_active:
            row.label = spec['label']
            row.kind = spec['kind']
            row.blurb = spec['blurb']
            row.accent = spec['accent']
            row.months = ','.join(str(month) for month in spec.get('months') or ())
            _set_theme_products(row, spec['products'], by_name)
    _import_legacy_json(by_name)
    if db.session.get(ShopVitrine, 1) is None:
        db.session.add(ShopVitrine(id=1, season_id=None, theme_id=None))
    db.session.commit()
    _import_legacy_vitrine_file()


def _import_legacy_vitrine_file():
    path = _legacy_vitrine_path()
    try:
        stored = path.read_text(encoding='utf-8').strip()
    except OSError:
        return
    if not stored or stored.lower() in ('none', 'all', 'catalogue'):
        return
    from app.models.shop_theme import ShopVitrine

    row = db.session.get(ShopVitrine, 1)
    if row is None or row.season_id or row.theme_id:
        return
    season = theme = None
    if stored.startswith('{'):
        try:
            data = json.loads(stored)
        except json.JSONDecodeError:
            return
        season, theme = data.get('season'), data.get('theme')
    else:
        try:
            ids = parse_theme_ids(stored)
        except KeyError:
            return
        for theme_id in ids:
            item = get_theme(theme_id)
            if item['kind'] == 'saison':
                season = item['id']
            else:
                theme = item['id']
    try:
        set_applied_vitrine(season, theme)
    except KeyError:
        pass


def _theme_slug(label):
    from app.services.demo_accounts import product_slug
    from app.models.shop_theme import ShopTheme

    slug = product_slug(label) or 'theme'
    theme_id = f'custom-{slug}'
    if db.session.get(ShopTheme, theme_id) is None:
        return theme_id
    suffix = 2
    while db.session.get(ShopTheme, f'{theme_id}-{suffix}') is not None:
        suffix += 1
    return f'{theme_id}-{suffix}'


def all_themes():
    from app.models.shop_theme import ShopTheme

    rows = (
        ShopTheme.query.filter_by(is_active=True)
        .order_by(ShopTheme.kind.desc(), ShopTheme.id)
        .all()
    )
    return [_theme_dict(row) for row in rows]


def create_custom_theme(data):
    from app.models import Product
    from app.models.shop_theme import ShopTheme

    label = str((data or {}).get('label') or '').strip()
    if len(label) < 2:
        raise ValueError('Le nom du thème est requis.')
    raw_products = (data or {}).get('products') or []
    if isinstance(raw_products, str):
        raw_products = [part.strip() for part in raw_products.split(',')]
    wanted = [str(name).strip() for name in raw_products if str(name).strip()]
    if not wanted:
        raise ValueError('Choisissez au moins un bouquet pour ce thème.')
    by_name = {product.name: product for product in Product.query.all()}
    names = [name for name in wanted if name in by_name]
    if not names:
        raise ValueError('Aucun produit du catalogue ne correspond à ce thème.')
    accent = str((data or {}).get('accent') or '#bc6288').strip().lower()
    if len(accent) != 7 or not accent.startswith('#'):
        accent = '#bc6288'
    row = ShopTheme(
        id=_theme_slug(label),
        label=label[:80],
        kind='evenement',
        blurb=str((data or {}).get('blurb') or '').strip()[:240],
        accent=accent,
        months='',
        is_builtin=False,
        is_active=True,
    )
    db.session.add(row)
    _set_theme_products(row, names, by_name)
    db.session.commit()
    return _theme_dict(row)


def delete_custom_theme(theme_id):
    from app.models.shop_theme import ShopTheme

    theme_id = (theme_id or '').strip().lower()
    row = db.session.get(ShopTheme, theme_id)
    if row is None or not row.is_active:
        raise KeyError(theme_id)
    if row.kind != 'evenement':
        raise ValueError('Thème introuvable.')
    applied = get_applied_vitrine()
    if row.is_builtin:
        row.is_active = False
        row.links.clear()
    else:
        db.session.delete(row)
    db.session.commit()
    season = None if applied.get('season') == theme_id else applied.get('season')
    event = None if applied.get('theme') == theme_id else applied.get('theme')
    if season != applied.get('season') or event != applied.get('theme'):
        set_applied_vitrine(season, event)
    return theme_id


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


def _vitrine_row():
    from app.models.shop_theme import ShopVitrine

    row = db.session.get(ShopVitrine, 1)
    if row is None:
        row = ShopVitrine(id=1)
        db.session.add(row)
        db.session.commit()
    return row


def get_applied_vitrine():
    row = _vitrine_row()
    try:
        return {
            'season': _normalize_slot(row.season_id, 'saison'),
            'theme': _normalize_slot(row.theme_id, 'evenement'),
        }
    except KeyError:
        return _empty_applied()


def get_applied_theme_id():
    ids = applied_ids()
    if not ids:
        return None
    return ','.join(ids)


def set_applied_vitrine(season_id=None, theme_id=None):
    applied = {
        'season': _normalize_slot(season_id, 'saison'),
        'theme': _normalize_slot(theme_id, 'evenement'),
    }
    row = _vitrine_row()
    row.season_id = applied['season']
    row.theme_id = applied['theme']
    db.session.commit()
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
                'can_delete': theme['kind'] == 'evenement',
            }
            for theme in all_themes()
        ],
    }
