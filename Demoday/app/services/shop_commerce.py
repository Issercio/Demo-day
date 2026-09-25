"""Livraison, codes promo, identité boutique, suivi invité."""

from decimal import Decimal, ROUND_HALF_UP
import re

from sqlalchemy import inspect, text, func

from app.extensions import db
from app.models import Order
from app.models.settings import ShopSettings, PromoCode
from app.services.mailer import mail_configured, send_mail, florist_inbox

POSTAL_RE = re.compile(r'\b(\d{5})\b')
WEEKDAY_LABELS = ('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche')
NATIONWIDE_TOKENS = {'', 'FR', '*', 'FRANCE', 'ALL', 'TOUTELAFRANCE'}
OLD_IDF_PREFIXES = '75,77,78,91,92,93,94,95'
OVERSEAS_PREFIXES = ('971', '972', '973', '974', '975', '976')
DEFAULT_ETA_METRO = '24–48 h'
DEFAULT_ETA_OVERSEAS = '3–5 jours ouvrés'
DEFAULT_OVERSEAS_FEE = Decimal('16.90')


def parse_description(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > 800:
        raise ValueError('Description trop longue (800 caractères max).')
    return text


def _luhn_ok(number):
    digits = [int(char) for char in number]
    checksum = 0
    odd = True
    for digit in reversed(digits):
        if not odd:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
        odd = not odd
    return checksum % 10 == 0


def normalize_siren(value):
    """SIREN réel saisi en admin : 9 chiffres + Luhn. Jamais de numéro inventé par défaut."""
    raw = str(value or '').strip()
    if not raw:
        return None
    digits = re.sub(r'\D', '', raw)
    if len(digits) == 14:
        raise ValueError('Indiquez le SIREN (9 chiffres), pas le SIRET.')
    if len(digits) != 9 or not digits.isdigit():
        raise ValueError('SIREN invalide : 9 chiffres.')
    if digits == '000000000' or not _luhn_ok(digits):
        raise ValueError('SIREN invalide (clé de Luhn).')
    return digits


def _optional_text(value, length):
    text = str(value or '').strip()[:length]
    return text or None


def _money_field(value, label, allow_empty=False):
    if allow_empty and value in (None, ''):
        return None
    try:
        fee = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception as exc:
        raise ValueError(f'{label} invalide.') from exc
    if fee < 0 or fee > 200:
        raise ValueError(f'{label} invalide.')
    return fee


def ensure_commerce_schema():
    db.create_all()
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if 'products' in tables:
        columns = {column['name'] for column in inspector.get_columns('products')}
        if 'description' not in columns:
            db.session.execute(text('ALTER TABLE products ADD COLUMN description TEXT'))
    if 'orders' in tables:
        existing = {column['name'] for column in inspector.get_columns('orders')}
        for name, ddl in {
            'shipping_amount': 'NUMERIC(10, 2)',
            'discount_amount': 'NUMERIC(10, 2)',
            'promo_code': 'VARCHAR(40)',
        }.items():
            if name not in existing:
                db.session.execute(text(f'ALTER TABLE orders ADD COLUMN {name} {ddl}'))
    if 'contact_requests' in tables:
        existing = {column['name'] for column in inspector.get_columns('contact_requests')}
        if 'reply_text' not in existing:
            db.session.execute(text('ALTER TABLE contact_requests ADD COLUMN reply_text TEXT'))
    if 'shop_settings' in tables:
        existing = {column['name'] for column in inspector.get_columns('shop_settings')}
        for name, ddl in {
            'legal_form': 'VARCHAR(40)',
            'capital': 'VARCHAR(40)',
            'rcs_city': 'VARCHAR(80)',
            'tva_intra': 'VARCHAR(20)',
            'delivery_carrier': 'VARCHAR(80)',
            'delivery_eta_metro': 'VARCHAR(80)',
            'delivery_eta_overseas': 'VARCHAR(80)',
            'delivery_fee_overseas': 'NUMERIC(10, 2)',
        }.items():
            if name not in existing:
                db.session.execute(text(f'ALTER TABLE shop_settings ADD COLUMN {name} {ddl}'))
    db.session.commit()
    get_settings()


def get_settings():
    row = db.session.get(ShopSettings, 1)
    if row is None:
        row = ShopSettings(
            id=1,
            legal_name='FloraShop',
            email='atelier@florashop.demo',
            pickup_note='Retrait à l’atelier, 10h–18h (fermé le dimanche).',
            delivery_fee=Decimal('8.90'),
            delivery_fee_overseas=DEFAULT_OVERSEAS_FEE,
            delivery_prefixes='FR',
            delivery_eta_metro=DEFAULT_ETA_METRO,
            delivery_eta_overseas=DEFAULT_ETA_OVERSEAS,
            closed_weekdays='6',
        )
        db.session.add(row)
        db.session.commit()
        return row
    changed = False
    if (row.delivery_prefixes or '') == OLD_IDF_PREFIXES:
        row.delivery_prefixes = 'FR'
        changed = True
    if not (row.delivery_eta_metro or '').strip():
        row.delivery_eta_metro = DEFAULT_ETA_METRO
        changed = True
    if not (row.delivery_eta_overseas or '').strip():
        row.delivery_eta_overseas = DEFAULT_ETA_OVERSEAS
        changed = True
    if row.delivery_fee_overseas is None:
        row.delivery_fee_overseas = DEFAULT_OVERSEAS_FEE
        changed = True
    if changed:
        db.session.commit()
    return row


def public_settings():
    payload = get_settings().to_public_dict()
    payload['mail_configured'] = mail_configured()
    payload['delivery_nationwide'] = delivery_is_nationwide()
    payload['delivery_label'] = (
        'France entière' if payload['delivery_nationwide']
        else (payload['delivery_prefixes'] or '')
    )
    return payload


def update_settings(data):
    row = get_settings()
    if 'legal_name' in data:
        name = str(data.get('legal_name') or '').strip()[:120]
        if len(name) < 2:
            raise ValueError('Indiquez le nom de la boutique.')
        row.legal_name = name
    if 'address' in data:
        row.address = str(data.get('address') or '').strip()[:255] or None
    if 'email' in data:
        row.email = str(data.get('email') or '').strip()[:120] or None
    if 'phone' in data:
        row.phone = str(data.get('phone') or '').strip()[:40] or None
    if 'siren' in data:
        row.siren = normalize_siren(data.get('siren'))
    if 'legal_form' in data:
        row.legal_form = _optional_text(data.get('legal_form'), 40)
    if 'capital' in data:
        row.capital = _optional_text(data.get('capital'), 40)
    if 'rcs_city' in data:
        row.rcs_city = _optional_text(data.get('rcs_city'), 80)
    if 'tva_intra' in data:
        tva = str(data.get('tva_intra') or '').strip().upper().replace(' ', '')[:20]
        row.tva_intra = tva or None
    if 'pickup_note' in data:
        row.pickup_note = str(data.get('pickup_note') or '').strip()[:255] or None
    if 'delivery_fee' in data:
        row.delivery_fee = _money_field(data.get('delivery_fee'), 'Tarif de livraison')
    if 'delivery_fee_overseas' in data:
        row.delivery_fee_overseas = _money_field(
            data.get('delivery_fee_overseas'),
            'Tarif DOM',
            allow_empty=True,
        )
    if 'delivery_carrier' in data:
        row.delivery_carrier = _optional_text(data.get('delivery_carrier'), 80)
    if 'delivery_eta_metro' in data:
        row.delivery_eta_metro = _optional_text(data.get('delivery_eta_metro'), 80) or DEFAULT_ETA_METRO
    if 'delivery_eta_overseas' in data:
        row.delivery_eta_overseas = (
            _optional_text(data.get('delivery_eta_overseas'), 80) or DEFAULT_ETA_OVERSEAS
        )
    if 'delivery_prefixes' in data:
        raw = str(data.get('delivery_prefixes') or '').strip()
        compact = raw.upper().replace(' ', '').replace('-', '')
        if compact in NATIONWIDE_TOKENS:
            row.delivery_prefixes = 'FR'
        else:
            prefixes = []
            for part in raw.replace(';', ',').split(','):
                token = part.strip()
                if token.isdigit() and 2 <= len(token) <= 3:
                    prefixes.append(token)
            if not prefixes:
                raise ValueError('Indiquez FR (toute la France) ou des départements (ex. 75,13,33).')
            row.delivery_prefixes = ','.join(prefixes)
    if 'closed_weekdays' in data:
        raw = str(data.get('closed_weekdays') or '')
        days = []
        for part in raw.replace(';', ',').split(','):
            token = part.strip()
            if token.isdigit() and 0 <= int(token) <= 6:
                days.append(str(int(token)))
        row.closed_weekdays = ','.join(dict.fromkeys(days))
    db.session.commit()
    return row


def closed_weekday_set():
    raw = (get_settings().closed_weekdays or '6')
    days = set()
    for part in raw.split(','):
        part = part.strip()
        if part.isdigit():
            days.add(int(part))
    return days


def assert_open_day(day):
    if day is None:
        return
    if day.weekday() in closed_weekday_set():
        label = WEEKDAY_LABELS[day.weekday()]
        raise ValueError(f'L’atelier est fermé le {label}. Choisissez un autre jour.')


def extract_postal(address):
    match = POSTAL_RE.search(address or '')
    return match.group(1) if match else None


def delivery_is_nationwide(raw=None):
    text = (raw if raw is not None else (get_settings().delivery_prefixes or 'FR'))
    compact = str(text).strip().upper().replace(' ', '').replace('-', '')
    return compact in NATIONWIDE_TOKENS


def is_french_postal(postal):
    """Métropole (01–95, Corse 20) et DOM 971–976."""
    if not postal or not postal.isdigit() or len(postal) != 5:
        return False
    dept = int(postal[:2])
    if 1 <= dept <= 95:
        return True
    return postal[:3] in OVERSEAS_PREFIXES


def is_overseas_postal(postal):
    return bool(postal) and postal[:3] in OVERSEAS_PREFIXES


def prefix_list():
    raw = get_settings().delivery_prefixes or 'FR'
    if delivery_is_nationwide(raw):
        return []
    return [part.strip() for part in raw.split(',') if part.strip()]


def _assert_delivery_zone(postal):
    if delivery_is_nationwide():
        if not is_french_postal(postal):
            raise ValueError(
                f'Livraison uniquement en France (code postal à 5 chiffres). '
                f'Le {postal} n’est pas desservi (retrait à l’atelier possible).'
            )
        return
    prefixes = prefix_list()
    if not prefixes or not any(postal.startswith(prefix) for prefix in prefixes):
        raise ValueError(
            f'Livraison indisponible pour le {postal}. '
            f'Zone desservie : {", ".join(prefixes)} (retrait à l’atelier possible).'
        )


def quote_shipping_details(fulfillment_type, address):
    """Retrait = 0 €. Livraison : tarif + délai selon métropole / DOM."""
    settings = get_settings()
    empty = {
        'shipping': Decimal('0.00'),
        'zone': None,
        'overseas': False,
        'carrier': settings.delivery_carrier or '',
        'eta': '',
    }
    if fulfillment_type != 'livraison':
        return empty
    postal = extract_postal(address or '')
    if not postal:
        raise ValueError('Pour une livraison, indiquez une adresse avec le code postal à 5 chiffres.')
    _assert_delivery_zone(postal)
    overseas = is_overseas_postal(postal)
    if overseas:
        if settings.delivery_fee_overseas is not None:
            fee = Decimal(str(settings.delivery_fee_overseas))
        else:
            fee = Decimal(str(settings.delivery_fee or 0))
        eta = settings.delivery_eta_overseas or DEFAULT_ETA_OVERSEAS
        zone = 'overseas'
    else:
        fee = Decimal(str(settings.delivery_fee or 0))
        eta = settings.delivery_eta_metro or DEFAULT_ETA_METRO
        zone = 'metro'
    return {
        'shipping': fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'zone': zone,
        'overseas': overseas,
        'carrier': settings.delivery_carrier or '',
        'eta': eta,
    }


def quote_shipping(fulfillment_type, address):
    """0 € au retrait. Livraison : tarif boutique si le CP est français (ou dans la zone)."""
    return quote_shipping_details(fulfillment_type, address)['shipping']


def apply_promo(code, subtotal):
    raw = (code or '').strip().upper()
    if not raw:
        return None, Decimal('0.00')
    row = PromoCode.query.filter(func.upper(PromoCode.code) == raw).first()
    if row is None or not row.active:
        raise ValueError('Code promo invalide.')
    subtotal = Decimal(str(subtotal)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if row.percent:
        percent = int(row.percent)
        if percent < 1 or percent > 90:
            raise ValueError('Code promo invalide.')
        discount = (subtotal * Decimal(percent) / Decimal(100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    elif row.amount is not None:
        discount = min(subtotal, Decimal(str(row.amount))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        raise ValueError('Code promo invalide.')
    return row, discount


def bump_promo(row):
    if row is None:
        return
    row.uses_count = int(row.uses_count or 0) + 1


def list_promos():
    return [row.to_dict() for row in PromoCode.query.order_by(PromoCode.created_at.desc()).all()]


def create_promo(data):
    code = str(data.get('code') or '').strip().upper()
    if not re.match(r'^[A-Z0-9_-]{3,20}$', code):
        raise ValueError('Code promo : 3 à 20 lettres ou chiffres.')
    if PromoCode.query.filter(func.upper(PromoCode.code) == code).first():
        raise ValueError('Ce code existe déjà.')
    percent = data.get('percent')
    amount = data.get('amount')
    row = PromoCode(code=code, active=True, uses_count=0)
    if percent not in (None, ''):
        try:
            value = int(percent)
        except (TypeError, ValueError) as exc:
            raise ValueError('Pourcentage invalide.') from exc
        if value < 1 or value > 90:
            raise ValueError('Pourcentage entre 1 et 90.')
        row.percent = value
    elif amount not in (None, ''):
        try:
            money = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception as exc:
            raise ValueError('Montant invalide.') from exc
        if money <= 0 or money > 500:
            raise ValueError('Montant promo invalide.')
        row.amount = money
    else:
        raise ValueError('Indiquez un pourcentage ou un montant.')
    db.session.add(row)
    db.session.commit()
    return row


def set_promo_active(promo_id, active):
    row = db.session.get(PromoCode, promo_id)
    if row is None:
        raise KeyError('Code introuvable')
    row.active = bool(active)
    db.session.commit()
    return row


def track_guest_order(email, order_id):
    mail = str(email or '').strip().lower()
    try:
        oid = int(order_id)
    except (TypeError, ValueError) as exc:
        raise ValueError('Numéro de commande invalide.') from exc
    if '@' not in mail or len(mail) < 5:
        raise ValueError('Email invalide.')
    order = db.session.get(Order, oid)
    if order is None or (order.email or '').strip().lower() != mail:
        raise KeyError('Commande introuvable')
    return order


def notify_order(order):
    settings = get_settings()
    shop = settings.legal_name or 'FloraShop'
    ship_line = ''
    if order.fulfillment_type == 'livraison':
        carrier = settings.delivery_carrier or 'transporteur de la boutique'
        eta = (
            settings.delivery_eta_overseas
            if is_overseas_postal(extract_postal(order.address or '') or '')
            else settings.delivery_eta_metro
        ) or ''
        ship_line = (
            f'Livraison {order.shipping_amount or 0} €'
            f'{f" via {carrier}" if carrier else ""}'
            f'{f" ({eta})" if eta else ""}.\n'
        )
    body = (
        f'Bonjour {order.customer_name or ""},\n\n'
        f'Votre commande #{order.id} chez {shop} est enregistrée '
        f'({order.payment_label()}, {order.total_amount} €).\n'
        f'{ship_line}'
        f'Suivi : page Commandes, ou en invité avec cet email et le n° {order.id}.\n\n'
        f'{shop}\n'
    )
    send_mail(order.email, f'{shop} — commande #{order.id}', body)
    dest = florist_inbox() or settings.email
    if dest and dest.lower() != (order.email or '').lower():
        send_mail(dest, f'Nouvelle commande #{order.id}', body)


def notify_contact(row):
    settings = get_settings()
    dest = florist_inbox() or settings.email
    send_mail(
        dest,
        f'Nouveau message contact — {row.name}',
        f'{row.name} <{row.email}>\n\n{row.message}',
    )


def notify_contact_reply(row):
    settings = get_settings()
    shop = settings.legal_name or 'FloraShop'
    send_mail(
        row.email,
        f'{shop} — réponse à votre message',
        f'Bonjour {row.name},\n\n{row.reply_text}\n\n{shop}\n',
    )
