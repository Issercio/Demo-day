"""Facture PDF : totaux TTC du catalogue, HT/TVA dérivés du taux boutique."""

from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from app.services.checkout_service import money

CENTS = Decimal('0.01')
DEFAULT_TVA_RATE = Decimal('10.00')  # fleurs coupées, taux réduit FR


def invoice_number(order):
    year = order.created_at.year if order.created_at else None
    if year is None:
        from datetime import datetime, timezone
        year = datetime.now(timezone.utc).year
    return f'FAC-{year}-{int(order.id):04d}'


def tva_rate_value(settings=None):
    if settings is not None and settings.tva_rate is not None:
        return money(settings.tva_rate)
    return DEFAULT_TVA_RATE


def split_ttc(ttc, rate):
    """Les prix shop sont TTC. HT = TTC / (1 + taux), TVA = TTC − HT."""
    total = money(ttc)
    percent = money(rate)
    if percent <= 0:
        return total, Decimal('0.00')
    divisor = Decimal('1') + (percent / Decimal('100'))
    ht = (total / divisor).quantize(CENTS, rounding=ROUND_HALF_UP)
    tva = (total - ht).quantize(CENTS, rounding=ROUND_HALF_UP)
    return ht, tva


def invoice_payload(order, settings=None):
    from app.services.shop_commerce import get_settings

    shop = settings or get_settings()
    rate = tva_rate_value(shop)
    ttc = money(order.total_amount)
    ht, tva = split_ttc(ttc, rate)
    shipping = money(order.shipping_amount or 0)
    discount = money(order.discount_amount or 0)
    lines = []
    for item in order.order_items:
        qty = int(item.quantity or 1)
        unit = money(item.price)
        line_ttc = money(unit * qty)
        line_ht, line_tva = split_ttc(line_ttc, rate)
        name = item.product.name if item.product else f'Produit #{item.product_id}'
        lines.append({
            'name': name,
            'quantity': qty,
            'unit_ttc': float(unit),
            'line_ttc': float(line_ttc),
            'line_ht': float(line_ht),
            'line_tva': float(line_tva),
        })
    remaining = order.remaining_amount()
    return {
        'number': invoice_number(order),
        'order_id': order.id,
        'created_at': order.created_at.isoformat() if order.created_at else None,
        'shop_name': shop.legal_name or 'FloraShop',
        'shop_address': shop.address or '',
        'shop_email': shop.email or '',
        'shop_phone': shop.phone or '',
        'siren': shop.siren or '',
        'legal_form': shop.legal_form or '',
        'tva_intra': shop.tva_intra or '',
        'tva_rate': float(rate),
        'customer_name': order.customer_name or '',
        'customer_email': order.email or '',
        'customer_phone': order.phone or '',
        'customer_address': order.address or '',
        'status': order.status,
        'payment_label': order.payment_label(),
        'lines': lines,
        'shipping_ttc': float(shipping),
        'discount_ttc': float(discount),
        'total_ht': float(ht),
        'total_tva': float(tva),
        'total_ttc': float(ttc),
        'deposit_amount': float(order.deposit_amount) if order.deposit_amount is not None else None,
        'remaining_amount': float(remaining) if remaining is not None else None,
        'tracking_number': getattr(order, 'tracking_number', None) or '',
        'refunded_amount': float(order.refunded_amount) if getattr(order, 'refunded_amount', None) else None,
    }


def _pdf_text(value):
    raw = str(value or '')
    table = str.maketrans({
        'à': 'a', 'â': 'a', 'ä': 'a', 'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'î': 'i', 'ï': 'i', 'ô': 'o', 'ö': 'o', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c', 'À': 'A', 'Â': 'A', 'É': 'E', 'È': 'E', 'Ê': 'E', 'Î': 'I',
        'Ô': 'O', 'Ù': 'U', 'Û': 'U', 'Ç': 'C', 'œ': 'oe', 'Œ': 'OE',
        '’': "'", '‘': "'", '–': '-', '—': '-',
    })
    return raw.translate(table)


def build_invoice_pdf(order, settings=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    payload = invoice_payload(order, settings)
    buffer = BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 20 * mm

    def line(text, size=11, gap=6):
        nonlocal y
        page.setFont('Helvetica', size)
        page.drawString(18 * mm, y, _pdf_text(text)[:110])
        y -= gap * mm

    page.setFont('Helvetica-Bold', 16)
    page.drawString(18 * mm, y, _pdf_text(payload['shop_name']))
    y -= 8 * mm
    line(f"Facture {payload['number']}", 12, 6)
    if payload['shop_address']:
        line(payload['shop_address'], 9, 5)
    if payload['siren']:
        line(f"SIREN {payload['siren']}", 9, 5)
    if payload['tva_intra']:
        line(f"TVA {payload['tva_intra']}", 9, 5)
    y -= 3 * mm
    line(f"Client : {payload['customer_name'] or payload['customer_email']}", 11, 5)
    if payload['customer_address']:
        line(payload['customer_address'], 9, 5)
    line(payload['customer_email'], 9, 6)
    y -= 2 * mm
    line('Articles (prix TTC)', 11, 6)
    for item in payload['lines']:
        line(
            f"{item['quantity']} x {item['name']}  {item['line_ttc']:.2f} EUR",
            9,
            5,
        )
    y -= 2 * mm
    if payload['shipping_ttc']:
        line(f"Livraison : {payload['shipping_ttc']:.2f} EUR", 10, 5)
    if payload['discount_ttc']:
        line(f"Remise : -{payload['discount_ttc']:.2f} EUR", 10, 5)
    line(f"Total HT : {payload['total_ht']:.2f} EUR", 10, 5)
    line(f"TVA {payload['tva_rate']:.2f} % : {payload['total_tva']:.2f} EUR", 10, 5)
    page.setFont('Helvetica-Bold', 12)
    page.drawString(18 * mm, y, _pdf_text(f"Total TTC : {payload['total_ttc']:.2f} EUR"))
    y -= 8 * mm
    line(f"Paiement : {payload['payment_label']}", 10, 5)
    if payload['deposit_amount'] is not None:
        line(f"Acompte : {payload['deposit_amount']:.2f} EUR", 10, 5)
        if payload['remaining_amount'] is not None:
            line(f"Reste du : {payload['remaining_amount']:.2f} EUR", 10, 5)
    if payload['tracking_number']:
        line(f"Suivi colis : {payload['tracking_number']}", 10, 5)
    page.showPage()
    page.save()
    buffer.seek(0)
    return buffer, payload
