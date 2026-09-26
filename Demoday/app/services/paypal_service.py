"""PayPal REST optionnel. Sans CLIENT_ID/SECRET : le checkout sandbox local reste actif."""

import json
import logging
import os
import urllib.error
import urllib.request
from base64 import b64encode

logger = logging.getLogger(__name__)

PLACEHOLDER_CLIENTS = {
    '',
    'AYxxxxxxxx',
    'change-me-paypal-client-id',
}


def paypal_configured():
    client = (os.environ.get('PAYPAL_CLIENT_ID') or '').strip()
    secret = (os.environ.get('PAYPAL_SECRET') or '').strip()
    if client in PLACEHOLDER_CLIENTS or len(client) < 20:
        return False
    if len(secret) < 20:
        return False
    return True


def paypal_client_id():
    if not paypal_configured():
        return None
    return (os.environ.get('PAYPAL_CLIENT_ID') or '').strip()


def paypal_api_base():
    live = (os.environ.get('PAYPAL_MODE') or '').strip().lower() in ('live', 'production')
    if live:
        return 'https://api-m.paypal.com'
    return 'https://api-m.sandbox.paypal.com'


def _token():
    client = os.environ.get('PAYPAL_CLIENT_ID').strip()
    secret = os.environ.get('PAYPAL_SECRET').strip()
    raw = b64encode(f'{client}:{secret}'.encode('utf-8')).decode('ascii')
    request = urllib.request.Request(
        paypal_api_base() + '/v1/oauth2/token',
        data=b'grant_type=client_credentials',
        method='POST',
        headers={
            'Authorization': f'Basic {raw}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode('utf-8'))
    token = payload.get('access_token')
    if not token:
        raise ValueError('PayPal n\'a pas renvoyé de jeton.')
    return token


def create_paypal_order(amount_ttc, currency='EUR'):
    if not paypal_configured():
        raise ValueError('PayPal n\'est pas configuré.')
    token = _token()
    body = json.dumps({
        'intent': 'CAPTURE',
        'purchase_units': [{
            'amount': {
                'currency_code': currency,
                'value': f'{amount_ttc:.2f}',
            }
        }],
    }).encode('utf-8')
    request = urllib.request.Request(
        paypal_api_base() + '/v2/checkout/orders',
        data=body,
        method='POST',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        logger.exception('PayPal create order %s', exc.code)
        raise ValueError('Impossible de créer le paiement PayPal.') from exc


def capture_paypal_order(paypal_order_id):
    if not paypal_configured():
        raise ValueError('PayPal n\'est pas configuré.')
    token = _token()
    request = urllib.request.Request(
        paypal_api_base() + f'/v2/checkout/orders/{paypal_order_id}/capture',
        data=b'{}',
        method='POST',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        logger.exception('PayPal capture %s', exc.code)
        raise ValueError('Capture PayPal refusée.') from exc
