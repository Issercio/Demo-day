"""Facture PDF : totaux TTC du catalogue, HT/TVA dérivés du taux boutique."""

from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path

from app.services.checkout_service import money

LOGO_PATH = Path(__file__).resolve().parents[1] / 'static' / 'img' / 'logo.png'
ROSE = '#bc6288'
INK = '#3a2a30'
MUTED = '#7a5a66'

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
        'capital': getattr(shop, 'capital', None) or '',
        'rcs_city': getattr(shop, 'rcs_city', None) or '',
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


def _euro(value):
    return f'{float(value):.2f} EUR'


def _shop_lines(payload):
    lines = [payload['shop_address'], payload['shop_email'], payload['shop_phone']]
    return [part for part in lines if part]


def _legal_lines(payload):
    bits = [
        payload.get('legal_form') or '',
        f"SIREN {payload['siren']}" if payload.get('siren') else '',
        f"TVA {payload['tva_intra']}" if payload.get('tva_intra') else '',
        f"RCS {payload['rcs_city']}" if payload.get('rcs_city') else '',
        f"Capital {payload['capital']}" if payload.get('capital') else '',
    ]
    return [part for part in bits if part]


def _register_invoice_fonts():
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        base = Path('/usr/share/fonts/truetype/liberation')
        regular = base / 'LiberationSans-Regular.ttf'
        if not regular.is_file():
            return False
        pdfmetrics.registerFont(TTFont('Inv', str(regular)))
        pdfmetrics.registerFont(TTFont('Inv-Bold', str(base / 'LiberationSans-Bold.ttf')))
        pdfmetrics.registerFont(TTFont('Inv-Italic', str(base / 'LiberationSans-Italic.ttf')))
        return True
    except Exception:
        return False


def _build_reportlab_pdf(payload):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
    )

    unicode_fonts = _register_invoice_fonts()
    regular = 'Inv' if unicode_fonts else 'Helvetica'
    bold = 'Inv-Bold' if unicode_fonts else 'Helvetica-Bold'
    italic = 'Inv-Italic' if unicode_fonts else 'Helvetica-Oblique'
    txt = (lambda value: str(value or '')) if unicode_fonts else _pdf_text

    rose = colors.HexColor(ROSE)
    ink = colors.HexColor(INK)
    muted = colors.HexColor(MUTED)
    cream = colors.HexColor('#f8f0f4')
    paper = colors.HexColor('#fffdfb')

    shop_style = ParagraphStyle(
        'ShopName', fontName=bold, fontSize=16, textColor=rose, leading=20, spaceAfter=2,
    )
    muted_style = ParagraphStyle(
        'Muted', fontName=regular, fontSize=8.5, textColor=muted, leading=12,
    )
    label_style = ParagraphStyle(
        'Label', fontName=bold, fontSize=8, textColor=rose, leading=11, spaceAfter=2,
    )
    body_style = ParagraphStyle(
        'Body', fontName=regular, fontSize=9.5, textColor=ink, leading=13,
    )
    facture_kicker = ParagraphStyle(
        'Kicker', fontName=regular, fontSize=8, textColor=rose, leading=10,
        alignment=TA_RIGHT, spaceAfter=2,
    )
    facture_num = ParagraphStyle(
        'FacNum', fontName=bold, fontSize=16, textColor=ink, leading=20, alignment=TA_RIGHT,
    )
    facture_meta = ParagraphStyle(
        'FacMeta', fontName=regular, fontSize=8.5, textColor=muted, leading=12, alignment=TA_RIGHT,
    )
    cell_style = ParagraphStyle(
        'Cell', fontName=regular, fontSize=9, textColor=ink, leading=12,
    )
    thanks_style = ParagraphStyle(
        'Thanks', fontName=italic, fontSize=10, textColor=rose, alignment=TA_CENTER, leading=14,
    )
    legal_style = ParagraphStyle(
        'Legal', fontName=regular, fontSize=7.5, textColor=muted, leading=10, alignment=TA_CENTER,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=txt(f"Facture {payload['number']}"),
        author=txt(payload['shop_name']),
    )

    shop_block = [Paragraph(txt(payload['shop_name']), shop_style)]
    for line in _shop_lines(payload):
        shop_block.append(Paragraph(txt(line), muted_style))

    logo = None
    if LOGO_PATH.is_file():
        try:
            logo = Image(str(LOGO_PATH), width=22 * mm, height=18 * mm)
        except Exception:
            logo = None
    brand = [logo, shop_block] if logo else [shop_block]
    brand_table = Table(
        [brand],
        colWidths=[26 * mm, 85 * mm] if logo else [111 * mm],
    )
    brand_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    created = (payload.get('created_at') or '')[:10]
    right = [
        Paragraph('FACTURE', facture_kicker),
        Paragraph(txt(payload['number']), facture_num),
        Paragraph(txt(f"Commande #{payload['order_id']}" + (f'  ·  {created}' if created else '')), facture_meta),
        Paragraph(txt(payload['payment_label'] or ''), facture_meta),
    ]
    header = Table([[brand_table, right]], colWidths=[112 * mm, 66 * mm])
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BACKGROUND', (0, 0), (-1, -1), paper),
    ]))

    client_bits = [
        payload.get('customer_name') or payload.get('customer_email') or 'Client',
        payload.get('customer_address') or '',
        payload.get('customer_email') or '',
        payload.get('customer_phone') or '',
    ]
    client_html = '<br/>'.join(txt(part) for part in client_bits if part)
    parties = Table(
        [[
            [Paragraph('CLIENT', label_style), Paragraph(client_html, body_style)],
            [Paragraph('PAIEMENT', label_style), Paragraph(txt(payload['payment_label'] or ''), body_style)],
        ]],
        colWidths=[89 * mm, 89 * mm],
    )
    parties.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), cream),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#eadfe2')),
        ('LINEAFTER', (0, 0), (0, 0), 0.4, colors.HexColor('#eadfe2')),
    ]))

    rows = [['Désignation', 'Qté', 'PU TTC', 'Total TTC']]
    for item in payload['lines']:
        rows.append([
            Paragraph(txt(item['name']), cell_style),
            str(item['quantity']),
            _euro(item['unit_ttc']),
            _euro(item['line_ttc']),
        ])
    items = Table(rows, colWidths=[98 * mm, 18 * mm, 31 * mm, 31 * mm])
    items.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), bold),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 0), (-1, 0), rose),
        ('FONTNAME', (0, 1), (-1, -1), regular),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TEXTCOLOR', (0, 1), (-1, -1), ink),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, cream]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#eadfe2')),
        ('BOX', (0, 0), (-1, -1), 0.6, rose),
    ]))

    total_rows = []
    if payload['shipping_ttc']:
        total_rows.append(['Livraison', _euro(payload['shipping_ttc'])])
    if payload['discount_ttc']:
        total_rows.append(['Remise', f"- {_euro(payload['discount_ttc'])}"])
    total_rows.append(['Total HT', _euro(payload['total_ht'])])
    total_rows.append([f"TVA {payload['tva_rate']:.2f} %", _euro(payload['total_tva'])])
    if payload.get('deposit_amount') is not None:
        total_rows.append(['Acompte versé', _euro(payload['deposit_amount'])])
        if payload.get('remaining_amount') is not None:
            total_rows.append(['Reste dû', _euro(payload['remaining_amount'])])
    total_rows.append(['Total TTC', _euro(payload['total_ttc'])])
    totals = Table(total_rows, colWidths=[42 * mm, 32 * mm])
    totals.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -2), regular),
        ('FONTNAME', (0, -1), (-1, -1), bold),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -2), muted),
        ('TEXTCOLOR', (0, -1), (-1, -1), rose),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('LINEABOVE', (0, -1), (-1, -1), 1.2, rose),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
    ]))
    totals_wrap = Table([['', totals]], colWidths=[104 * mm, 74 * mm])
    totals_wrap.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    legal = ' · '.join(_legal_lines(payload))
    footer_bits = [
        f"Facture {payload['number']} émise par {payload['shop_name']}. Prix TTC, TVA {payload['tva_rate']:.2f} %.",
    ]
    if legal:
        footer_bits.append(legal)
    if payload.get('tracking_number'):
        footer_bits.append(f"Suivi colis : {payload['tracking_number']}")

    story = [
        header,
        Spacer(1, 4 * mm),
        HRFlowable(width='100%', thickness=2, color=rose, spaceBefore=0, spaceAfter=8),
        parties,
        Spacer(1, 8 * mm),
        items,
        Spacer(1, 6 * mm),
        totals_wrap,
        Spacer(1, 10 * mm),
        Paragraph('Merci de votre confiance.', thanks_style),
        Spacer(1, 4 * mm),
        Paragraph(txt(' '.join(footer_bits)), legal_style),
    ]
    doc.build(story)
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
