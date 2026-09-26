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


def _pdf_escape(value):
    return _pdf_text(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _invoice_lines(payload):
    rows = [
        (16, True, payload['shop_name']),
        (12, False, f"Facture {payload['number']}"),
    ]
    if payload['shop_address']:
        rows.append((9, False, payload['shop_address']))
    if payload['siren']:
        rows.append((9, False, f"SIREN {payload['siren']}"))
    if payload['tva_intra']:
        rows.append((9, False, f"TVA {payload['tva_intra']}"))
    rows.append((11, False, f"Client : {payload['customer_name'] or payload['customer_email']}"))
    if payload['customer_address']:
        rows.append((9, False, payload['customer_address']))
    rows.append((9, False, payload['customer_email']))
    rows.append((11, False, 'Articles (prix TTC)'))
    for item in payload['lines']:
        rows.append((9, False, f"{item['quantity']} x {item['name']}  {item['line_ttc']:.2f} EUR"))
    if payload['shipping_ttc']:
        rows.append((10, False, f"Livraison : {payload['shipping_ttc']:.2f} EUR"))
    if payload['discount_ttc']:
        rows.append((10, False, f"Remise : -{payload['discount_ttc']:.2f} EUR"))
    rows.append((10, False, f"Total HT : {payload['total_ht']:.2f} EUR"))
    rows.append((10, False, f"TVA {payload['tva_rate']:.2f} % : {payload['total_tva']:.2f} EUR"))
    rows.append((12, True, f"Total TTC : {payload['total_ttc']:.2f} EUR"))
    rows.append((10, False, f"Paiement : {payload['payment_label']}"))
    if payload['deposit_amount'] is not None:
        rows.append((10, False, f"Acompte : {payload['deposit_amount']:.2f} EUR"))
        if payload['remaining_amount'] is not None:
            rows.append((10, False, f"Reste du : {payload['remaining_amount']:.2f} EUR"))
    if payload['tracking_number']:
        rows.append((10, False, f"Suivi colis : {payload['tracking_number']}"))
    return rows


def _build_reportlab_pdf(payload):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 20 * mm

    def line(text, size=11, gap=6, bold=False):
        nonlocal y
        page.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
        page.drawString(18 * mm, y, _pdf_text(text)[:110])
        y -= gap * mm

    for size, bold, text in _invoice_lines(payload):
        line(text, size, 6 if size >= 12 else 5, bold=bold)
    page.showPage()
    page.save()
    buffer.seek(0)
    return buffer


def _build_stdlib_pdf(payload):
    """PDF minimal (Helvetica) si reportlab n'est pas installé sur le serveur."""
    ops = ['BT']
    y = 800
    first = True
    for size, bold, text in _invoice_lines(payload):
        font = 'F2' if bold else 'F1'
        ops.append(f'/{font} {int(size)} Tf')
        if first:
            ops.append(f'50 {y} Td')
            first = False
        else:
            gap = 16 if size >= 12 else 14
            ops.append(f'0 -{gap} Td')
        ops.append(f'({_pdf_escape(text)[:110]}) Tj')
    ops.append('ET')
    stream = '\n'.join(ops).encode('latin-1', 'replace')

    buffer = BytesIO()
    buffer.write(b'%PDF-1.4\n')
    offsets = [0]

    def write_obj(body):
        offsets.append(buffer.tell())
        num = len(offsets) - 1
        buffer.write(f'{num} 0 obj\n'.encode('ascii'))
        buffer.write(body)
        if not body.endswith(b'\n'):
            buffer.write(b'\n')
        buffer.write(b'endobj\n')
        return num

    write_obj(b'<< /Type /Catalog /Pages 2 0 R >>')
    write_obj(b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    write_obj(
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] '
        b'/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>'
    )
    write_obj(
        f'<< /Length {len(stream)} >>\nstream\n'.encode('ascii') + stream + b'\nendstream'
    )
    write_obj(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    write_obj(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>')
    xref_pos = buffer.tell()
    buffer.write(f'xref\n0 {len(offsets)}\n'.encode('ascii'))
    buffer.write(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        buffer.write(f'{offset:010d} 00000 n \n'.encode('ascii'))
    buffer.write(
        f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n'.encode('ascii')
    )
    buffer.seek(0)
    return buffer


def build_invoice_pdf(order, settings=None):
    payload = invoice_payload(order, settings)
    try:
        buffer = _build_reportlab_pdf(payload)
    except ImportError:
        buffer = _build_stdlib_pdf(payload)
    return buffer, payload
