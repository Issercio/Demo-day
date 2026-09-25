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


def parse_description(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > 800:
        raise ValueError('Description trop longue (800 caractères max).')
    return text


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
            delivery_prefixes='75,77,78,91,92,93,94,95',
            closed_weekdays='6',
        )
        db.session.add(row)
        db.session.commit()
    return row


def public_settings():
    payload = get_settings().to_public_dict()
    payload['mail_configured'] = mail_configured()
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
        row.siren = str(data.get('siren') or '').strip()[:20] or None
    if 'pickup_note' in data:
        row.pickup_note = str(data.get('pickup_note') or '').strip()[:255] or None
    if 'delivery_fee' in data:
        try:
            fee = Decimal(str(data.get('delivery_fee'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception as exc:
            raise ValueError('Tarif de livraison invalide.') from exc
        if fee < 0 or fee > 200:
            raise ValueError('Tarif de livraison invalide.')
        row.delivery_fee = fee
    if 'delivery_prefixes' in data:
        raw = str(data.get('delivery_prefixes') or '')
        prefixes = []
        for part in raw.replace(';', ',').split(','):
            token = part.strip()
            if token.isdigit() and 2 <= len(token) <= 3:
                prefixes.append(token)
        if not prefixes:
            raise ValueError('Indiquez au moins un département (ex. 75,92,93).')
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


def prefix_list():
    raw = get_settings().delivery_prefixes or ''
    return [part.strip() for part in raw.split(',') if part.strip()]


def quote_shipping(fulfillment_type, address):
    """0 € au retrait. Livraison : tarif boutique si le CP est dans la zone."""
    if fulfillment_type != 'livraison':
        return Decimal('0.00')
    postal = extract_postal(address or '')
    if not postal:
        raise ValueError('Pour une livraison, indiquez une adresse avec le code postal à 5 chiffres.')
    prefixes = prefix_list()
    if not any(postal.startswith(prefix) for prefix in prefixes):
        raise ValueError(
            f'Livraison indisponible pour le {postal}. '
            f'Zone desservie : {", ".join(prefixes)} (retrait à l’atelier possible).'
        )
    fee = Decimal(str(get_settings().delivery_fee or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return fee


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
    body = (
        f'Bonjour {order.customer_name or ""},\n\n'
        f'Votre commande #{order.id} chez {shop} est enregistrée '
        f'({order.payment_label()}, {order.total_amount} €).\n'
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
