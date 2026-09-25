"""Server-side checkout: catalog prices, test cards, optional Stripe."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import re
import uuid

from flask import current_app
from sqlalchemy import inspect, text

from app.extensions import db
from app.models import Category, Order, OrderItem, Product
from app.models.order import PAID_LIKE


SUBSCRIPTION_PLANS = {
    'monthly': {
        'slug': 'monthly',
        'name': 'Abonnement Éclat Mensuel',
        'price': Decimal('19.99'),
        'duration': '1 mois',
        'cart_id': 'subscription_monthly',
    },
    'semester': {
        'slug': 'semester',
        'name': 'Abonnement Harmonie Semestrielle',
        'price': Decimal('17.99'),
        'duration': '6 mois',
        'cart_id': 'subscription_semester',
    },
    'yearly': {
        'slug': 'yearly',
        'name': 'Abonnement Collection Annuelle',
        'price': Decimal('14.99'),
        'duration': '12 mois',
        'cart_id': 'subscription_yearly',
    },
}

TEST_CARDS = {
    # Seules ces cartes Luhn valides passent en démo. Une autre carte 16 chiffres est refusée.
    '4242424242424242': ('success', None),
    '4000000000000002': ('declined', 'Votre carte a été refusée.'),
    '4000000000009995': ('insufficient_funds', 'Fonds insuffisants sur la carte.'),
}

PLACEHOLDER_SECRETS = {
    '',
    'sk_test_...',
    'sk_test_VOTRE_CLE_SECRETE_STRIPE',
}

PLACEHOLDER_PUBLISHABLE = {
    '',
    'pk_test_...',
    'pk_test_VOTRE_CLE_PUBLIQUE_STRIPE',
}


class PaymentDeclined(Exception):
    def __init__(self, message, order=None):
        super().__init__(message)
        self.order = order  # commande failed à renvoyer en HTTP 402


def stripe_configured():
    # Clés vides ou placeholders du .env.example → processeur de cartes de test.
    secret = (current_app.config.get('STRIPE_SECRET_KEY') or '').strip()
    publishable = (current_app.config.get('STRIPE_PUBLISHABLE_KEY') or '').strip()
    if secret in PLACEHOLDER_SECRETS or len(secret) < 20:
        return False
    if not (secret.startswith('sk_test_') or secret.startswith('sk_live_')):
        return False
    if publishable in PLACEHOLDER_PUBLISHABLE:
        return False
    if not (publishable.startswith('pk_test_') or publishable.startswith('pk_live_')):
        return False
    return True


def payment_config():
    live = stripe_configured()
    return {
        'mode': 'stripe' if live else 'test',
        'publishable_key': current_app.config.get('STRIPE_PUBLISHABLE_KEY') if live else None,
        'currency': 'eur',
        'test_cards': [
            {'number': '4242 4242 4242 4242', 'result': 'Paiement accepté'},
            {'number': '4000 0000 0000 0002', 'result': 'Carte refusée'},
            {'number': '4000 0000 0000 9995', 'result': 'Fonds insuffisants'},
        ],
    }


def ensure_runtime_schema():
    db.create_all()
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if 'orders' not in tables:
        return

    existing = {column['name'] for column in inspector.get_columns('orders')}
    additions = {
        'customer_name': 'VARCHAR(120)',
        'payment_method': 'VARCHAR(50)',
        'card_last4': 'VARCHAR(4)',
        'payment_reference': 'VARCHAR(64)',
        'deposit_amount': 'NUMERIC(10, 2)',
        'prep_status': 'VARCHAR(32)',
        'phone': 'VARCHAR(20)',
        'address': 'VARCHAR(255)',
        'fulfillment_type': 'VARCHAR(16)',
        'fulfillment_date': 'VARCHAR(10)',
        'fulfillment_slot': 'VARCHAR(16)',
        'card_message': 'VARCHAR(280)',
    }
    for name, ddl in additions.items():
        if name not in existing:
            db.session.execute(text(f'ALTER TABLE orders ADD COLUMN {name} {ddl}'))
    # Anciennes commandes payées : elles doivent apparaître « À préparer » à l'atelier.
    db.session.execute(text(
        "UPDATE orders SET prep_status = 'a_preparer' "
        "WHERE prep_status IS NULL AND status IN ('paid', 'deposit')"
    ))
    db.session.commit()
    from app.services.demo_accounts import ensure_product_color_column, ensure_product_image_column
    from app.services.login_lockout import ensure_login_lockout_columns
    from app.services.account_verification import ensure_verification_columns
    from app.services.shop_extras import ensure_shop_extra_columns
    ensure_product_color_column()
    ensure_product_image_column()
    ensure_login_lockout_columns()
    ensure_verification_columns()
    ensure_shop_extra_columns()
    ensure_subscription_catalog()


def ensure_subscription_catalog():
    category = Category.query.filter_by(name='Abonnements').first()
    if category is None:
        category = Category(name='Abonnements')
        db.session.add(category)
        db.session.flush()

    catalog = {}
    for slug, plan in SUBSCRIPTION_PLANS.items():
        product = Product.query.filter_by(name=plan['name']).first()
        if product is None:
            product = Product(name=plan['name'], price=plan['price'], category_id=category.id)
            db.session.add(product)
            db.session.flush()
        else:
            product.price = plan['price']
            product.category_id = category.id
        catalog[slug] = product
    db.session.commit()
    return catalog


def _luhn_ok(number):
    """Algorithme de Luhn : un vrai numéro de carte a un checksum % 10 == 0.
    Ça évite d'accepter '1234' tout en gardant les cartes de test Stripe (4242…)."""
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


def _parse_expiry(value):
    raw = (value or '').strip()
    match = re.fullmatch(r'(\d{1,2})\s*/\s*(\d{2}|\d{4})', raw)
    if not match:
        digits = re.sub(r'\D', '', raw)
        if len(digits) == 4:
            month, year = int(digits[:2]), int(digits[2:])
        else:
            raise ValueError('Date d\'expiration invalide (MM/AA).')
    else:
        month = int(match.group(1))
        year = int(match.group(2))
    if year < 100:
        year += 2000  # AA → 20AA (29 → 2029)
    if month < 1 or month > 12:
        raise ValueError('Mois d\'expiration invalide.')
    now = datetime.now(timezone.utc)
    if year < now.year or (year == now.year and month < now.month):
        raise ValueError('Carte expirée.')
    return month, year


def process_test_card(card_number, expiry, cvc):
    number = re.sub(r'\D', '', card_number or '')
    if len(number) < 13 or len(number) > 19 or not number.isdigit() or not _luhn_ok(number):
        raise ValueError('Numéro de carte invalide.')
    _parse_expiry(expiry)
    cvc_digits = re.sub(r'\D', '', cvc or '')
    if len(cvc_digits) not in (3, 4):
        raise ValueError('Code CVC invalide.')

    result, message = TEST_CARDS.get(
        number,
        ('unknown', 'Carte de test inconnue. Utilisez 4242 4242 4242 4242.'),
    )
    # Hors whitelist démo → refus, même si le numéro passe Luhn.
    if result != 'success':
        raise PaymentDeclined(message)
    return number[-4:]


def _subscription_slug(item):
    """Le panier mélange produits (id numérique) et abonnements (id 'subscription_monthly').
    On renvoie le slug du plan, ou None si c'est une fleur / un cadeau normal."""
    raw_id = item.get('product_id', item.get('id', item.get('plan')))
    item_type = str(item.get('type') or '').lower()
    name = str(item.get('name') or '')

    if item_type == 'subscription' or (
        isinstance(raw_id, str) and str(raw_id).startswith('subscription_')
    ):
        slug = str(raw_id).replace('subscription_', '')
        if slug in SUBSCRIPTION_PLANS:
            return slug
        for plan_slug, plan in SUBSCRIPTION_PLANS.items():
            if plan['name'] == name or plan['cart_id'] == str(raw_id):
                return plan_slug
        raise ValueError(f'Abonnement inconnu: {raw_id}')

    for plan_slug, plan in SUBSCRIPTION_PLANS.items():
        if name == plan['name'] or str(raw_id) == plan['cart_id']:
            return plan_slug
    return None


CENTS = Decimal('0.01')
DEPOSIT_RATE = Decimal('0.30')  # acompte démo : 30 % du total catalogue


def money(value):
    """Arrondit à 2 décimales. Évite 0.1 + 0.2 = 0.30000000000000004."""
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


def parse_money(value):
    """Prix catalogue : Decimal strict, jamais float(data['price'])."""
    try:
        amount = money(value)
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValueError('Prix invalide.') from exc
    if amount < 0:
        raise ValueError('Prix invalide.')
    return amount


def to_cents(amount):
    """Montant Stripe : centimes entiers, sans float binaire."""
    return int((money(amount) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def deposit_of(total):
    return money(Decimal(str(total)) * DEPOSIT_RATE)


def _wants_deposit(data):
    raw = data.get('deposit', data.get('acompte', False))
    if isinstance(raw, str):
        return raw.strip().lower() in ('1', 'true', 'yes', 'on')  # JSON parfois stringy
    return bool(raw)


def build_order_lines(items):
    # Le prix du body JSON est ignoré : on relit Product.price (ou le plan d'abonnement).
    if not items:
        raise ValueError('Au moins un article est requis.')

    catalog = ensure_subscription_catalog()
    lines = []
    total = Decimal('0.00')

    for item in items:
        try:
            quantity = int(item.get('quantity') or 1)
        except (TypeError, ValueError):
            raise ValueError('Quantité invalide.') from None
        if quantity <= 0:
            raise ValueError('La quantité doit être positive.')

        slug = _subscription_slug(item)
        if slug:
            product = catalog[slug]
        else:
            raw_id = item.get('product_id', item.get('id'))
            try:
                product_id = int(raw_id)
            except (TypeError, ValueError):
                raise ValueError(f'Produit invalide: {raw_id}') from None
            product = db.session.get(Product, product_id)
            if product is None:
                raise ValueError(f'Produit {product_id} introuvable.')
            if product.name in {plan['name'] for plan in SUBSCRIPTION_PLANS.values()}:
                pass

        unit_price = money(product.price)  # catalogue, pas item['price'] du panier
        total += unit_price * quantity
        lines.append({
            'product': product,
            'quantity': quantity,
            'price': unit_price,
        })

    return lines, money(total)


def _guest_contact(data, user_id):
    """Invité : email + téléphone et/ou adresse. Compte connecté : contact optionnel."""
    from app.services.account_verification import normalize_phone
    phone = normalize_phone(data.get('phone'))
    if phone is False:
        raise ValueError('Numéro de téléphone invalide.')
    address = (data.get('address') or data.get('shipping_address') or '').strip()
    if len(address) > 255:
        raise ValueError('Adresse trop longue.')
    if not user_id and not phone and not address:
        raise ValueError('En invité, indiquez un téléphone ou une adresse.')
    return phone, (address or None)


def _persist_order(
    email, name, user_id, total, method, status, card_last4, reference, stripe_id, lines,
    prep_status=None, deposit_amount=None, phone=None, address=None,
    fulfillment_type=None, fulfillment_date=None, fulfillment_slot=None, card_message=None,
):
    order = Order(
        user_id=user_id,
        email=email,
        customer_name=name,
        phone=phone,
        address=address,
        total_amount=total,
        deposit_amount=deposit_amount,
        payment_method=method,
        status=status,
        prep_status=prep_status,
        card_last4=card_last4,
        payment_reference=reference,
        stripe_payment_intent_id=stripe_id,
        fulfillment_type=fulfillment_type,
        fulfillment_date=fulfillment_date,
        fulfillment_slot=fulfillment_slot,
        card_message=card_message,
    )
    db.session.add(order)
    db.session.flush()
    for line in lines:
        db.session.add(OrderItem(
            order_id=order.id,
            product_id=line['product'].id,
            quantity=line['quantity'],
            price=line['price'],
        ))
    db.session.commit()
    return order


def checkout(data, user_id=None):
    """Valide le panier côté serveur : les prix viennent de la DB, pas du navigateur."""
    email = (data.get('email') or '').strip()
    name = (data.get('customer_name') or data.get('name') or '').strip()
    method = (data.get('payment_method') or 'card').lower()
    phone, address = _guest_contact(data, user_id)
    from app.services.shop_extras import consume_stock, notify_order_placed, parse_fulfillment
    fulfillment_type, fulfillment_date, fulfillment_slot, card_message = parse_fulfillment(data)

    if not email or '@' not in email:
        raise ValueError('Email invalide.')
    if not name:
        if user_id is None:
            name = 'Invité'
        else:
            raise ValueError('Nom du client requis.')
    if method not in ('card', 'paypal', 'saved'):
        raise ValueError('Méthode de paiement non supportée.')

    lines, total = build_order_lines(data.get('items') or [])
    card_last4 = None
    reference = f'{method.upper()}-{uuid.uuid4().hex[:10].upper()}'
    stripe_id = None
    status = 'paid'
    deposit_amount = None
    # Payée ou acompte → l'atelier doit préparer ; refusée → pas de préparation.
    prep_status = 'a_preparer'
    want_deposit = _wants_deposit(data)

    try:
        if method == 'card':
            if data.get('payment_intent_id'):
                # Pas de PI ici : n'importe qui réécrirait la commande. JWT + owner = /confirm-payment.
                raise ValueError('Paiement Stripe : confirmez via /api/v1/payments/confirm-payment.')
            card_last4 = process_test_card(
                data.get('card_number'),
                data.get('card_expiry') or data.get('expiry'),
                data.get('card_cvc') or data.get('cvc'),
            )
            reference = f'TEST-{uuid.uuid4().hex[:10].upper()}'
        elif method == 'saved':
            card_last4 = '4242'  # sandbox : carte enregistrée = •••• 4242
            reference = f'SAVED-{uuid.uuid4().hex[:10].upper()}'
        else:
            reference = f'PAYPAL-{uuid.uuid4().hex[:10].upper()}'
    except PaymentDeclined as error:
        order = _persist_order(
            email, name, user_id, total, method, 'failed',
            None, f'FAIL-{uuid.uuid4().hex[:10].upper()}', None, lines,
            prep_status=None, deposit_amount=None,  # refus : pas d'atelier
            phone=phone, address=address,
            fulfillment_type=fulfillment_type, fulfillment_date=fulfillment_date,
            fulfillment_slot=fulfillment_slot, card_message=card_message,
        )
        raise PaymentDeclined(str(error), order=order) from error

    # Stripe encaisse le total : on n'enregistre un acompte que sur le processeur de test.
    if want_deposit and not stripe_id:
        status = 'deposit'
        deposit_amount = deposit_of(total)

    consume_stock(lines)
    order = _persist_order(
        email, name, user_id, total, method, status,
        card_last4, reference, stripe_id, lines,
        prep_status=prep_status, deposit_amount=deposit_amount,
        phone=phone, address=address,
        fulfillment_type=fulfillment_type, fulfillment_date=fulfillment_date,
        fulfillment_slot=fulfillment_slot, card_message=card_message,
    )
    order.track_notice = notify_order_placed(order)
    return order
