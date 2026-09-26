"""Contact inbox, server cart, stock, fulfillment, atelier dashboard."""

from datetime import date, timedelta
import json
import re

from sqlalchemy import inspect, text

from app.extensions import db
from app.models import Product
from app.models.cart import Cart
from app.models.contact import CONTACT_STATUSES, ContactRequest
from app.models.order import PAID_LIKE, Order
from app.models.base_model import utc_now

GUEST_TOKEN_RE = re.compile(r'^[A-Za-z0-9_-]{8,64}$')
LOW_STOCK = 3


def ensure_ops_schema():
    db.create_all()
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if 'products' in tables:
        columns = {column['name'] for column in inspector.get_columns('products')}
        if 'stock_qty' not in columns:
            db.session.execute(text('ALTER TABLE products ADD COLUMN stock_qty INTEGER DEFAULT 12'))
            db.session.execute(text('UPDATE products SET stock_qty = 12 WHERE stock_qty IS NULL'))
    if 'orders' in tables:
        existing = {column['name'] for column in inspector.get_columns('orders')}
        for name, ddl in {
            'fulfillment_type': 'VARCHAR(20)',
            'fulfillment_date': 'DATE',
            'fulfillment_slot': 'VARCHAR(20)',
        }.items():
            if name not in existing:
                db.session.execute(text(f'ALTER TABLE orders ADD COLUMN {name} {ddl}'))
    db.session.commit()


def stock_status(qty):
    qty = int(qty or 0)
    if qty <= 0:
        return 'out'
    if qty <= LOW_STOCK:
        return 'low'
    return 'available'


def parse_stock_qty(value, default=None):
    if value in (None, ''):
        if default is None:
            return None
        return int(default)
    try:
        qty = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Stock invalide.') from exc
    if qty < 0 or qty > 9999:
        raise ValueError('Stock invalide.')
    return qty


def assert_stock_available(lines):
    """Refuse the quote before Stripe / test-card if a line is already out of stock."""
    for line in lines:
        product = line['product']
        if str(product.name or '').startswith('Abonnement '):
            continue
        qty = int(line['quantity'])
        current = int(product.stock_qty if product.stock_qty is not None else 12)
        if current < qty:
            raise ValueError(f'« {product.name} » n’est plus en stock.')


def restock(lines):
    for line in lines:
        product = line['product']
        if str(product.name or '').startswith('Abonnement '):
            continue
        qty = int(line['quantity'])
        current = int(product.stock_qty if product.stock_qty is not None else 12)
        product.stock_qty = current + qty


def consume_stock(lines):
    assert_stock_available(lines)
    for line in lines:
        product = line['product']
        if str(product.name or '').startswith('Abonnement '):
            continue
        qty = int(line['quantity'])
        current = int(product.stock_qty if product.stock_qty is not None else 12)
        product.stock_qty = current - qty


def parse_fulfillment(data):
    """Date / créneau optionnels. Si présents, la date ne peut pas être passée."""
    raw_type = (data.get('fulfillment_type') or '').strip().lower()
    raw_date = (data.get('fulfillment_date') or '').strip()
    raw_slot = (data.get('fulfillment_slot') or '').strip().lower()
    if not raw_type and not raw_date and not raw_slot:
        return None, None, None
    ftype = raw_type or 'retrait'
    if ftype not in ('retrait', 'livraison'):
        raise ValueError('Choisissez retrait ou livraison.')
    if not raw_date:
        raise ValueError('Indiquez une date de retrait ou de livraison.')
    try:
        day = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError('Date invalide.') from exc
    if day < date.today():
        raise ValueError('La date ne peut pas être dans le passé.')
    slot = raw_slot or 'matin'
    if slot not in ('matin', 'apres-midi'):
        raise ValueError('Créneau invalide (matin ou après-midi).')
    return ftype, day, slot


def _sanitize_items(raw):
    items = []
    if not isinstance(raw, list):
        return items
    for item in raw[:40]:
        if not isinstance(item, dict):
            continue
        qty = max(1, min(99, int(item.get('quantity') or 1)))
        kind = str(item.get('type') or 'product')
        payload = {
            'id': item.get('id') or item.get('product_id'),
            'product_id': item.get('product_id') or item.get('id'),
            'name': str(item.get('name') or '')[:120],
            'quantity': qty,
            'type': kind,
            'image': str(item.get('image') or '')[:255] or None,
            'plan': str(item.get('plan') or '')[:40] or None,
        }
        try:
            price = float(item.get('price'))
        except (TypeError, ValueError):
            price = None
        if price is not None and 0 <= price <= 10000:
            payload['price'] = round(price, 2)
        category = item.get('category')
        if isinstance(category, dict):
            category = category.get('name')
        if category:
            payload['category'] = str(category)[:80]
        if kind == 'subscription' or str(payload['id'] or '').startswith('subscription_'):
            payload['type'] = 'subscription'
        items.append(payload)
    return items


def _cart_payload(cart):
    try:
        items = json.loads(cart.items_json or '[]') if cart else []
    except json.JSONDecodeError:
        items = []
    if not isinstance(items, list):
        items = []
    return items


def guest_token_from(header_value):
    raw = (header_value or '').strip()
    if not raw:
        return None
    if not GUEST_TOKEN_RE.match(raw):
        return None
    return raw[:64]


def _get_or_create_cart(user_id=None, token=None):
    if user_id:
        cart = Cart.query.filter_by(user_id=user_id).first()
        if cart is None:
            cart = Cart(user_id=user_id, items_json='[]')
            db.session.add(cart)
            db.session.flush()
        return cart
    if token:
        cart = Cart.query.filter_by(guest_token=token).first()
        if cart is None:
            cart = Cart(guest_token=token, items_json='[]')
            db.session.add(cart)
            db.session.flush()
        return cart
    return None


def _enrich_items(items):
    """Prix, nom et photo viennent du catalogue pour l’affichage panier."""
    product_ids = []
    for item in items:
        if item.get('type') == 'subscription':
            continue
        try:
            product_ids.append(int(item.get('product_id') or item.get('id')))
        except (TypeError, ValueError):
            continue
    catalog = {}
    if product_ids:
        catalog = {
            product.id: product
            for product in Product.query.filter(Product.id.in_(product_ids)).all()
        }
    for item in items:
        if item.get('type') == 'subscription':
            continue
        try:
            product_id = int(item.get('product_id') or item.get('id'))
        except (TypeError, ValueError):
            continue
        product = catalog.get(product_id)
        if product is None:
            continue
        item['price'] = float(product.price)
        item['name'] = product.name
        if product.image:
            item['image'] = product.image
        if product.category:
            item['category'] = product.category.name
    return items


def load_cart_items(user_id=None, token=None):
    cart = None
    if user_id:
        cart = Cart.query.filter_by(user_id=user_id).first()
    elif token:
        cart = Cart.query.filter_by(guest_token=token).first()
    return _enrich_items(_sanitize_items(_cart_payload(cart) if cart else []))


def save_cart_items(items, user_id=None, token=None):
    if not user_id and not token:
        raise ValueError('Panier introuvable.')
    cart = _get_or_create_cart(user_id=user_id, token=token)
    cart.items_json = json.dumps(_sanitize_items(items), ensure_ascii=False)
    cart.updated_at = utc_now()
    db.session.commit()
    return _enrich_items(_sanitize_items(json.loads(cart.items_json)))


def merge_guest_into_user(user_id, token):
    if not user_id or not token:
        return load_cart_items(user_id=user_id)
    user_cart = _get_or_create_cart(user_id=user_id)
    guest = Cart.query.filter_by(guest_token=token).first()
    merged = _sanitize_items(_cart_payload(user_cart))
    if guest:
        for item in _sanitize_items(_cart_payload(guest)):
            key = _item_key(item)
            existing = next((row for row in merged if _item_key(row) == key), None)
            if existing:
                existing['quantity'] = min(99, int(existing['quantity']) + int(item['quantity']))
            else:
                merged.append(item)
        db.session.delete(guest)
    user_cart.items_json = json.dumps(merged, ensure_ascii=False)
    user_cart.updated_at = utc_now()
    db.session.commit()
    return _enrich_items(merged)


def _item_key(item):
    if item.get('type') == 'subscription' or str(item.get('id') or '').startswith('subscription_'):
        return f"sub:{item.get('id') or item.get('plan') or item.get('name')}"
    return f"p:{item.get('id') or item.get('product_id')}"


def clear_cart(user_id=None, token=None):
    if user_id:
        cart = Cart.query.filter_by(user_id=user_id).first()
        if cart:
            cart.items_json = '[]'
            cart.updated_at = utc_now()
    if token:
        guest = Cart.query.filter_by(guest_token=token).first()
        if guest:
            db.session.delete(guest)
    db.session.commit()


def create_contact(data):
    name = str(data.get('name') or data.get('nom') or '').strip()
    email = str(data.get('email') or '').strip().lower()
    message = str(data.get('message') or '').strip()
    kind = str(data.get('kind') or data.get('type') or 'contact').strip().lower()
    if kind not in ('contact', 'devis'):
        kind = 'contact'
    event_date = str(data.get('event_date') or '').strip()
    event_place = str(data.get('event_place') or data.get('lieu') or '').strip()
    budget = str(data.get('budget') or '').strip()
    extras = []
    if event_date:
        extras.append(f'Date : {event_date}')
    if event_place:
        extras.append(f'Lieu : {event_place}')
    if budget:
        extras.append(f'Budget : {budget}')
    if extras:
        message = message + '\n\n' + '\n'.join(extras)
    if len(name) < 2:
        raise ValueError('Indiquez votre nom.')
    if '@' not in email or len(email) < 5:
        raise ValueError('Email invalide.')
    if len(message) < 8:
        raise ValueError('Le message est trop court.')
    if len(message) > 2000:
        raise ValueError('Le message est trop long.')
    row = ContactRequest(
        name=name[:120],
        email=email[:120],
        message=message,
        kind=kind,
        status='nouveau',
    )
    db.session.add(row)
    db.session.commit()
    try:
        from app.services.shop_commerce import notify_contact
        notify_contact(row)
    except Exception:
        pass
    return row


def list_contacts():
    rows = ContactRequest.query.order_by(ContactRequest.created_at.desc()).limit(100).all()
    return [row.to_dict() for row in rows]


def patch_contact(contact_id, status=None, reply_text=None):
    row = db.session.get(ContactRequest, contact_id)
    if row is None:
        raise KeyError('Demande introuvable')
    if status:
        if status not in CONTACT_STATUSES:
            raise ValueError('Statut invalide.')
        row.status = status
    if reply_text is not None:
        text = str(reply_text).strip()
        if len(text) < 4:
            raise ValueError('La réponse est trop courte.')
        if len(text) > 2000:
            raise ValueError('La réponse est trop longue.')
        row.reply_text = text
        row.status = 'traite'
    if not status and reply_text is None:
        raise ValueError('Statut invalide.')
    db.session.commit()
    if reply_text is not None:
        try:
            from app.services.shop_commerce import notify_contact_reply
            notify_contact_reply(row)
        except Exception:
            pass
    return row


def today_dashboard():
    today = date.today()
    horizon = today + timedelta(days=7)
    orders = Order.query.filter(Order.status.in_(PAID_LIKE)).all()
    to_prep = sum(1 for order in orders if order.prep_status == 'a_preparer')
    in_prep = sum(1 for order in orders if order.prep_status == 'en_preparation')
    ready = sum(1 for order in orders if order.prep_status == 'pret')
    paid_today = 0
    pickups = []
    for order in orders:
        created = order.created_at.date() if order.created_at else None
        if created == today:
            paid_today += 1
        day = order.fulfillment_date or created
        if day and today <= day <= horizon and order.prep_status in ('a_preparer', 'en_preparation', 'pret'):
            pickups.append({
                'id': order.id,
                'name': order.customer_name or order.email,
                'date': day.isoformat(),
                'slot': order.fulfillment_slot or 'matin',
                'type': order.fulfillment_type or 'retrait',
                'prep_status': order.prep_status,
                'prep_label': order.prep_label(),
            })
    pickups.sort(key=lambda row: (row['date'], row['slot'] != 'matin'))
    products = Product.query.all()
    low = []
    out = []
    for product in products:
        qty = int(product.stock_qty if getattr(product, 'stock_qty', None) is not None else 12)
        status = stock_status(qty)
        if status == 'out':
            out.append({'id': product.id, 'name': product.name, 'stock_qty': qty})
        elif status == 'low':
            low.append({'id': product.id, 'name': product.name, 'stock_qty': qty})
    new_contacts = ContactRequest.query.filter_by(status='nouveau').count()
    from app.services.subscription_ops import due_subscriptions
    due = due_subscriptions(today)
    return {
        'date': today.isoformat(),
        'to_prep': to_prep,
        'in_prep': in_prep,
        'ready': ready,
        'paid_today': paid_today,
        'new_contacts': new_contacts,
        'low_stock': low,
        'out_stock': out,
        'upcoming_pickups': pickups[:12],
        'subscriptions_due': due,
    }
