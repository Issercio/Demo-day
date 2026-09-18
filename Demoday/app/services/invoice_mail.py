"""HTML invoices emailed after a paid order (customer + shop copy)."""

from html import escape
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr

from flask import current_app

logger = logging.getLogger(__name__)

DEFAULT_COPY_EMAIL = '9893@holbertonstudents.com'


def invoice_copy_email():
    return (current_app.config.get('INVOICE_COPY_EMAIL') or DEFAULT_COPY_EMAIL).strip()


def mail_configured():
    server = (current_app.config.get('MAIL_SERVER') or '').strip()
    username = (current_app.config.get('MAIL_USERNAME') or '').strip()
    password = (current_app.config.get('MAIL_PASSWORD') or '').strip()
    return bool(server and username and password)


def invoice_recipients(customer_email):
    """Buyer plus the Holberton copy mailbox (client and admin purchases)."""
    recipients = []
    for raw in (customer_email, invoice_copy_email()):
        address = (raw or '').strip().lower()
        if address and '@' in address and address not in recipients:
            recipients.append(address)
    return recipients


def _money(value):
    try:
        return f'{float(value):.2f}'
    except (TypeError, ValueError):
        return '0.00'


def render_invoice_html(order):
    items_html = []
    for item in order.order_items:
        name = (item.product.name if item.product else f'Produit #{item.product_id}')
        unit = _money(item.price)
        qty = int(item.quantity or 1)
        line = _money(float(item.price) * qty)
        items_html.append(
            f'<tr>'
            f'<td style="padding:8px 10px;border-bottom:1px solid #f0e4ea;">{escape(name)}</td>'
            f'<td style="padding:8px 10px;border-bottom:1px solid #f0e4ea;text-align:center;">{qty}</td>'
            f'<td style="padding:8px 10px;border-bottom:1px solid #f0e4ea;text-align:right;">{unit} €</td>'
            f'<td style="padding:8px 10px;border-bottom:1px solid #f0e4ea;text-align:right;">{line} €</td>'
            f'</tr>'
        )
    created = order.created_at.strftime('%d/%m/%Y %H:%M') if order.created_at else ''
    last4 = f'•••• {escape(order.card_last4)}' if order.card_last4 else ''
    return f"""
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><title>Facture #{order.id}</title></head>
<body style="font-family:Georgia,serif;background:#fff6f2;color:#231111;margin:0;padding:24px;">
  <div style="max-width:640px;margin:0 auto;background:#fff;border:1px solid #e7d6d6;border-radius:12px;overflow:hidden;">
    <div style="background:#bc6288;color:#fff;padding:20px 24px;">
      <h1 style="margin:0;font-size:22px;">Pivoine &amp; Lilas</h1>
      <p style="margin:6px 0 0;font-size:14px;">Artisan fleuriste — Sciez / Léman</p>
    </div>
    <div style="padding:24px;">
      <h2 style="margin:0 0 12px;color:#ab597c;">Facture n°{order.id}</h2>
      <p style="margin:0 0 4px;"><strong>Date :</strong> {escape(created)}</p>
      <p style="margin:0 0 4px;"><strong>Client :</strong> {escape(order.customer_name or '')}</p>
      <p style="margin:0 0 4px;"><strong>Email :</strong> {escape(order.email or '')}</p>
      <p style="margin:0 0 16px;"><strong>Référence :</strong> {escape(order.payment_reference or '')}
         — {escape(order.payment_method or '')} {last4}</p>
      <table style="width:100%;border-collapse:collapse;font-size:15px;">
        <thead>
          <tr style="background:#fff6f2;">
            <th style="padding:8px 10px;text-align:left;">Article</th>
            <th style="padding:8px 10px;text-align:center;">Qté</th>
            <th style="padding:8px 10px;text-align:right;">Prix</th>
            <th style="padding:8px 10px;text-align:right;">Total</th>
          </tr>
        </thead>
        <tbody>
          {''.join(items_html) or '<tr><td colspan="4">Aucun article</td></tr>'}
        </tbody>
      </table>
      <p style="text-align:right;font-size:18px;margin:16px 0 0;">
        <strong>Total payé : {_money(order.total_amount)} €</strong>
      </p>
      <p style="margin:18px 0 0;font-size:13px;color:#6c4a58;">
        Statut : {escape(order.status or '')}. Chemin de la Rouette, 74140 Sciez / Léman.
        SIREN 522 234 871.
      </p>
    </div>
  </div>
</body>
</html>
"""


def _from_address():
    raw = (current_app.config.get('MAIL_FROM') or '').strip()
    username = (current_app.config.get('MAIL_USERNAME') or '').strip()
    if raw:
        name, addr = parseaddr(raw)
        if addr:
            return formataddr((name or 'Pivoine & Lilas', addr))
    if username and '@' in username:
        return formataddr(('Pivoine & Lilas', username))
    return 'Pivoine & Lilas <noreply@localhost>'


def send_mail(subject, html, recipients):
    if not recipients:
        return {'sent': False, 'reason': 'no_recipients', 'to': []}
    if not mail_configured():
        logger.warning('Invoice mail skipped: MAIL_SERVER / MAIL_USERNAME / MAIL_PASSWORD missing.')
        return {'sent': False, 'reason': 'mail_not_configured', 'to': recipients}

    message = MIMEMultipart('alternative')
    message['Subject'] = subject
    message['From'] = _from_address()
    message['To'] = ', '.join(recipients)
    message.attach(MIMEText(html, 'html', 'utf-8'))

    host = current_app.config['MAIL_SERVER']
    port = int(current_app.config.get('MAIL_PORT') or 587)
    username = current_app.config['MAIL_USERNAME']
    password = current_app.config['MAIL_PASSWORD']
    use_ssl = bool(current_app.config.get('MAIL_USE_SSL'))
    use_tls = bool(current_app.config.get('MAIL_USE_TLS'))
    if use_ssl:
        use_tls = False

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    server = smtp_cls(host, port, timeout=20)
    try:
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        server.login(username, password)
        from_addr = parseaddr(message['From'])[1] or username
        server.sendmail(from_addr, recipients, message.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass
    return {'sent': True, 'reason': None, 'to': recipients}


def send_order_invoice(order):
    """Email a paid-order invoice to the buyer and the shop copy address."""
    if order is None or (order.status or '') != 'paid':
        return {'sent': False, 'reason': 'not_paid', 'to': []}
    recipients = invoice_recipients(order.email)
    html = render_invoice_html(order)
    subject = f'Facture #{order.id} — Pivoine & Lilas'
    try:
        result = send_mail(subject, html, recipients)
    except Exception as exc:
        logger.exception('Invoice email failed for order %s: %s', getattr(order, 'id', None), exc)
        return {'sent': False, 'reason': str(exc), 'to': recipients}
    return result
