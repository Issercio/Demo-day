"""Contrats d’abonnement : pas de Stripe Billing, l’atelier livre chaque période."""

from calendar import monthrange
from datetime import date

from sqlalchemy import func, or_

from app.extensions import db
from app.models.subscription import SUBSCRIPTION_STATUSES, ShopSubscription
from app.services.checkout_service import SUBSCRIPTION_PLANS, money


def add_months(day, months):
    month_index = day.month - 1 + int(months)
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last = monthrange(year, month)[1]
    return date(year, month, min(day.day, last))


def activate_from_order(order):
    """Après un paiement : un contrat par ligne d’abonnement."""
    created = []
    for item in order.order_items:
        product = item.product
        if product is None:
            continue
        slug = None
        for plan_slug, plan in SUBSCRIPTION_PLANS.items():
            if product.name == plan['name']:
                slug = plan_slug
                break
        if slug is None:
            continue
        plan = SUBSCRIPTION_PLANS[slug]
        start = order.fulfillment_date or date.today()
        row = ShopSubscription(
            user_id=order.user_id,
            email=order.email,
            customer_name=order.customer_name,
            plan_slug=slug,
            plan_name=plan['name'],
            period_months=plan['period_months'],
            price=money(item.price),
            status='active',
            deliveries_count=1,
            next_delivery=add_months(start, plan['period_months']),
            address=order.address,
            phone=order.phone,
        )
        db.session.add(row)
        created.append(row)
    if created:
        db.session.commit()
    return created


def list_for_user(user, include_all=False):
    query = ShopSubscription.query.order_by(ShopSubscription.created_at.desc())
    if include_all:
        return [row.to_dict() for row in query.limit(100).all()]
    email = (user.email or '').strip().lower()
    rows = query.filter(
        or_(
            ShopSubscription.user_id == user.id,
            func.lower(ShopSubscription.email) == email,
        )
    ).limit(50).all()
    return [row.to_dict() for row in rows]


def due_subscriptions(today=None):
    today = today or date.today()
    rows = ShopSubscription.query.filter(
        ShopSubscription.status == 'active',
        ShopSubscription.next_delivery != None,  # noqa: E711
        ShopSubscription.next_delivery <= today,
    ).order_by(ShopSubscription.next_delivery.asc()).all()
    return [row.to_dict() for row in rows]


def mark_delivered(subscription_id):
    row = db.session.get(ShopSubscription, subscription_id)
    if row is None:
        raise KeyError('Abonnement introuvable')
    if row.status != 'active':
        raise ValueError('Cet abonnement n\'est plus actif.')
    base = row.next_delivery or date.today()
    row.deliveries_count = int(row.deliveries_count or 0) + 1
    row.next_delivery = add_months(base, row.period_months or 1)
    db.session.commit()
    return row


def set_status(subscription_id, status, user=None, admin=False):
    row = db.session.get(ShopSubscription, subscription_id)
    if row is None:
        raise KeyError('Abonnement introuvable')
    if status not in SUBSCRIPTION_STATUSES:
        raise ValueError('Statut d\'abonnement invalide.')
    if not admin:
        email = (user.email or '').strip().lower() if user else ''
        owns = bool(user) and (
            row.user_id == user.id or (row.email or '').strip().lower() == email
        )
        if not owns:
            raise KeyError('Abonnement introuvable')
        if status not in ('cancelled', 'paused', 'active'):
            raise ValueError('Statut d\'abonnement invalide.')
    row.status = status
    if status == 'cancelled':
        from datetime import datetime, timezone
        row.cancelled_at = datetime.now(timezone.utc)
    db.session.commit()
    return row
