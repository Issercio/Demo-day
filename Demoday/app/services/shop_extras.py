"""Extras boutique : calendrier, packs, liaisons, stock, suivi invité, SMS démo."""

from __future__ import annotations

import os
import smtplib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from email.message import EmailMessage

from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

LOW_STOCK_MAX = 3
DEFAULT_STOCK = 12
TRACK_CODE_MINUTES = 15
SLOTS = ('matin', 'apres-midi')
FULFILLMENTS = ('retrait', 'livraison')
CARD_MESSAGE_MAX = 280

# Gestes à proposer sous une fiche, par nom catalogue.
RELATED_NAMES = {
    'Bouquet Pivoine': ('Mini bouquet', 'Rose unique', 'Carte et rose'),
    'Bouquet Lilas': ('Mini bouquet', 'Bouquet merci'),
    'Rose unique': ('Carte et rose', 'Mini bouquet'),
    'Carte et rose': ('Rose unique', 'Mini bouquet'),
    'Mini bouquet': ('Rose unique', 'Pot-fleur surprise'),
    'Bouquet de mariée': ('Boutonnières (lot de 6)', 'Centre de table mariage'),
    'Centre de table mariage': ('Bouquet de mariée', 'Bouquet demoiselle'),
    'Boutonnières (lot de 6)': ('Bouquet de mariée', 'Bouquet demoiselle'),
    'Tournesols du jardin': ('Gerbera soleil', 'Bouquet champêtre'),
    'Pot-fleur surprise': ('Duo de succulentes', 'Mini bouquet'),
}

WEDDING_PACK = {
    'id': 'pack-mariage',
    'label': 'Pack mariage',
    'blurb': 'Bouquet de mariée, boutonnières et centres de table : un clic pour les trois.',
    'product_names': (
        'Bouquet de mariée',
        'Boutonnières (lot de 6)',
        'Centre de table mariage',
    ),
}

# Quantités initiales (création seulement). Le checkout décrémente ensuite.
DEMO_STOCK = {
    'Rose unique': 3,
    'Mini bouquet': 4,
    'Anthurium': 0,
}

PREP_SMS = {
    'a_preparer': 'Votre commande #{id} est enregistrée : l\'atelier va la préparer.',
    'en_preparation': 'Votre commande #{id} est en préparation.',
    'pret': 'Votre commande #{id} est prête à retirer.',
    'remise': 'Votre commande #{id} a été remise. Merci !',
}


def stock_status(qty):
    if qty is None:
        qty = DEFAULT_STOCK
    try:
        qty = int(qty)
    except (TypeError, ValueError):
        qty = DEFAULT_STOCK
    if qty <= 0:
        return 'out'
    if qty <= LOW_STOCK_MAX:
        return 'low'
    return 'available'


def parse_stock_qty(value, default=DEFAULT_STOCK):
    if value in (None, ''):
        return default
    try:
        qty = int(value)
    except (TypeError, ValueError):
        raise ValueError('Quantité de stock invalide.') from None
    if qty < 0:
        raise ValueError('Le stock ne peut pas être négatif.')
    return qty


def calendar_event_ids(today=None):
    day = today or date.today()
    events = []
    if day.month == 2 and day.day <= 14:
        events.append('saint-valentin')
    if day.month == 5 and day.day >= 15:
        events.append('fete-des-meres')
    if day.month == 12:
        events.append('noel')
    return events


def related_names_for(product_name):
    return list(RELATED_NAMES.get(product_name) or ())


def wedding_pack_payload():
    from app.models import Product
    from app.services.checkout_service import money

    names = list(WEDDING_PACK['product_names'])
    products = []
    total = Decimal('0.00')
    for name in names:
        row = Product.query.filter_by(name=name).first()
        if row is None:
            continue
        products.append(row.to_dict())
        total += money(row.price)
    return {
        'id': WEDDING_PACK['id'],
        'label': WEDDING_PACK['label'],
        'blurb': WEDDING_PACK['blurb'],
        'product_names': names,
        'products': products,
        'total': float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
    }


def consume_stock(lines):
    """Décrémente le stock serveur. Les abonnements ne sont pas du stock rayon."""
    for line in lines:
        product = line['product']
        category_name = product.category.name if product.category else ''
        if category_name == 'Abonnements':
            continue
        available = DEFAULT_STOCK if product.stock_qty is None else int(product.stock_qty)
        wanted = int(line['quantity'])
        if available < wanted:
            raise ValueError(f'Rupture de stock : {product.name}.')
        product.stock_qty = available - wanted


def parse_fulfillment(data):
    raw_type = (data.get('fulfillment_type') or data.get('delivery_type') or '').strip().lower()
    if raw_type in ('pickup', 'retrait', 'click-collect'):
        kind = 'retrait'
    elif raw_type in ('livraison', 'delivery', 'ship'):
        kind = 'livraison'
    elif raw_type in ('', 'none'):
        kind = 'livraison' if (data.get('address') or '').strip() else 'retrait'
    else:
        raise ValueError('Choisissez retrait ou livraison.')

    slot = (data.get('fulfillment_slot') or data.get('slot') or '').strip().lower().replace('é', 'e')
    if slot in ('aprem', 'après-midi', 'apres midi', 'afternoon'):
        slot = 'apres-midi'
    if slot in ('morning',):
        slot = 'matin'
    if not slot:
        slot = 'matin'
    if slot not in SLOTS:
        raise ValueError('Créneau invalide (matin ou après-midi).')

    raw_date = (data.get('fulfillment_date') or data.get('pickup_date') or data.get('delivery_date') or '').strip()
    if not raw_date:
        wanted = date.today() + timedelta(days=1)
    else:
        try:
            wanted = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ValueError('Date invalide (AAAA-MM-JJ).') from exc
        if wanted < date.today():
            raise ValueError('La date de retrait / livraison est déjà passée.')

    message = (data.get('card_message') or data.get('message') or '').strip()
    if len(message) > CARD_MESSAGE_MAX:
        raise ValueError(f'La carte de vœux fait au plus {CARD_MESSAGE_MAX} caractères.')
    return kind, wanted.isoformat(), slot, (message or None)


def ensure_shop_extra_columns():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if 'products' in tables:
        existing = {column['name'] for column in inspector.get_columns('products')}
        if 'stock_qty' not in existing:
            db.session.execute(text('ALTER TABLE products ADD COLUMN stock_qty INTEGER DEFAULT 12'))
    if 'orders' in tables:
        existing = {column['name'] for column in inspector.get_columns('orders')}
        additions = {
            'fulfillment_type': 'VARCHAR(16)',
            'fulfillment_date': 'VARCHAR(10)',
            'fulfillment_slot': 'VARCHAR(16)',
            'card_message': 'VARCHAR(280)',
        }
        for name, ddl in additions.items():
            if name not in existing:
                db.session.execute(text(f'ALTER TABLE orders ADD COLUMN {name} {ddl}'))
    if 'shop_vitrine' in tables:
        existing = {column['name'] for column in inspector.get_columns('shop_vitrine')}
        if 'auto_mode' not in existing:
            db.session.execute(text('ALTER TABLE shop_vitrine ADD COLUMN auto_mode BOOLEAN DEFAULT 1'))
    db.session.commit()


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def issue_track_code(email):
    from app.models.order import OrderTrackCode
    import secrets

    email = (email or '').strip().lower()
    if not email or '@' not in email:
        raise ValueError('Email invalide.')
    OrderTrackCode.query.filter_by(email=email).delete()
    code = f'{secrets.randbelow(1_000_000):06d}'
    row = OrderTrackCode(
        email=email,
        code_hash=generate_password_hash(code),
        expires_at=_now() + timedelta(minutes=TRACK_CODE_MINUTES),
    )
    db.session.add(row)
    db.session.commit()
    _deliver_text(
        email,
        None,
        'email',
        f'Votre code de suivi Pivoine & Lilas est {code}. Il expire dans {TRACK_CODE_MINUTES} minutes.',
        'Pivoine & Lilas — suivi de commande',
    )
    return code


def check_track_code(email, code):
    from app.models.order import OrderTrackCode

    email = (email or '').strip().lower()
    raw = (code or '').strip()
    if len(raw) != 6 or not raw.isdigit():
        return False
    row = (
        OrderTrackCode.query.filter_by(email=email)
        .order_by(OrderTrackCode.id.desc())
        .first()
    )
    if row is None:
        return False
    expires = _aware(row.expires_at)
    if expires is None or expires <= _now():
        return False
    return check_password_hash(row.code_hash, raw)


def notify_prep_change(order):
    """SMS / email démo quand l'atelier avance. Sans Twilio le texte est loggé."""
    prep = order.prep_status or ''
    template = PREP_SMS.get(prep)
    if not template:
        return None
    text_body = template.format(id=order.id)
    dest_sms = order.phone
    dest_email = order.email
    if dest_sms:
        _deliver_text(dest_email, dest_sms, 'sms', text_body, 'Pivoine & Lilas — suivi')
        channel = 'sms'
        dest = dest_sms
    elif dest_email:
        _deliver_text(dest_email, None, 'email', text_body, 'Pivoine & Lilas — suivi de commande')
        channel = 'email'
        dest = dest_email
    else:
        return None
    return {
        'channel': channel,
        'to': dest,
        'text': text_body,
        'demo': True,
    }


def notify_order_placed(order):
    email = order.email
    if not email:
        return None
    body = (
        f'Votre commande #{order.id} est confirmée.\n'
        f'Suivi sur le site : commandes.html?email={email}&order={order.id}\n'
        'Vous pouvez aussi demander un code par email pour voir toutes vos commandes.'
    )
    _deliver_text(email, order.phone, 'email', body, 'Pivoine & Lilas — votre commande')
    return {
        'channel': 'email',
        'to': email,
        'text': body,
        'demo': True,
    }


def _deliver_text(email, phone, channel, body, subject):
    from flask import current_app

    dest = phone if channel == 'sms' else email
    current_app.logger.info('Notice %s pour %s : %s', channel, dest, body.replace('\n', ' / '))
    host = (os.environ.get('MAIL_SERVER') or '').strip()
    if channel == 'email' and host and email:
        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = os.environ.get('MAIL_FROM', 'noreply@localhost')
            msg['To'] = email
            msg.set_content(body)
            port = int(os.environ.get('MAIL_PORT') or '25')
            with smtplib.SMTP(host, port, timeout=5) as smtp:
                smtp.send_message(msg)
        except Exception:
            current_app.logger.exception('Envoi email suivi impossible — le mode démo reste valable')
