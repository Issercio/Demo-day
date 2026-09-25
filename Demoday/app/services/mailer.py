"""SMTP optionnel : sans MAIL_SERVER, on journalise et on n'échoue pas le paiement."""

import os
import smtplib
import logging
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def mail_configured():
    return bool((os.environ.get('MAIL_SERVER') or '').strip())


def _truthy(name):
    return (os.environ.get(name) or '').strip().lower() in ('1', 'true', 'yes', 'on')


def send_mail(to, subject, body):
    dest = (to or '').strip()
    if not dest or '@' not in dest:
        return False
    if not mail_configured():
        logger.info('Mail (démo, pas de SMTP) → %s | %s', dest, subject)
        return False
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = os.environ.get('MAIL_FROM') or 'noreply@localhost'
        msg['To'] = dest
        msg.set_content(body)
        host = os.environ.get('MAIL_SERVER').strip()
        port = int(os.environ.get('MAIL_PORT') or '587')
        user = (os.environ.get('MAIL_USER') or '').strip()
        password = os.environ.get('MAIL_PASSWORD') or ''
        # Port 465 = SMTPS. 587 = STARTTLS. MAIL_SSL / MAIL_STARTTLS forcent le mode.
        use_ssl = _truthy('MAIL_SSL') or _truthy('MAIL_USE_SSL') or port == 465
        use_starttls = _truthy('MAIL_STARTTLS')
        if use_ssl:
            smtp_cm = smtplib.SMTP_SSL(host, port, timeout=12)
        else:
            smtp_cm = smtplib.SMTP(host, port, timeout=12)
        with smtp_cm as smtp:
            smtp.ehlo()
            if use_starttls and not use_ssl:
                smtp.starttls()
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception('Envoi mail échoué vers %s', dest)
        return False


def florist_inbox():
    return (os.environ.get('MAIL_TO') or '').strip()
