"""SMTP optionnel : sans MAIL_SERVER, on journalise et on n'échoue pas le paiement."""

import os
import smtplib
import logging
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def mail_configured():
    return bool((os.environ.get('MAIL_SERVER') or '').strip())


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
        port = int(os.environ.get('MAIL_PORT') or '25')
        user = (os.environ.get('MAIL_USER') or '').strip()
        password = os.environ.get('MAIL_PASSWORD') or ''
        with smtplib.SMTP(host, port, timeout=8) as smtp:
            smtp.ehlo()
            if (os.environ.get('MAIL_STARTTLS') or '').lower() in ('1', 'true', 'yes'):
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception('Envoi mail échoué vers %s', dest)
        return False


def florist_inbox():
    return (os.environ.get('MAIL_TO') or '').strip()
