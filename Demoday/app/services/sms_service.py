"""SMS optionnel (Twilio). Sans identifiants : on journalise, comme MAIL_*."""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


def sms_configured():
    sid = (os.environ.get('TWILIO_ACCOUNT_SID') or '').strip()
    token = (os.environ.get('TWILIO_AUTH_TOKEN') or '').strip()
    sender = (os.environ.get('TWILIO_FROM') or '').strip()
    if not sid.startswith('AC') or len(sid) < 20:
        return False
    if len(token) < 16:
        return False
    if len(sender) < 8:
        return False
    return True


def send_sms(to, body):
    dest = (to or '').strip()
    text = (body or '').strip()
    if not dest or not text:
        return False
    if not sms_configured():
        logger.info('SMS (démo, pas de Twilio) → %s | %s', dest, text[:80])
        return False
    sid = os.environ.get('TWILIO_ACCOUNT_SID').strip()
    token = os.environ.get('TWILIO_AUTH_TOKEN').strip()
    sender = os.environ.get('TWILIO_FROM').strip()
    url = f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'
    payload = urllib.parse.urlencode({
        'To': dest,
        'From': sender,
        'Body': text[:1600],
    }).encode('utf-8')
    request = urllib.request.Request(url, data=payload, method='POST')
    credentials = urllib.parse.quote(sid, safe='') + ':' + urllib.parse.quote(token, safe='')
    import base64
    request.add_header(
        'Authorization',
        'Basic ' + base64.b64encode(credentials.encode('utf-8')).decode('ascii'),
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            json.loads(response.read().decode('utf-8') or '{}')
        return True
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        logger.exception('Envoi SMS échoué vers %s', dest)
        return False
