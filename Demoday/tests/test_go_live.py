import os
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['STRIPE_SECRET_KEY'] = ''
os.environ['STRIPE_PUBLISHABLE_KEY'] = ''
os.environ['STRIPE_WEBHOOK_SECRET'] = ''
os.environ['MAIL_SERVER'] = ''

from app import create_app, db
from app.models import User, Category, Product, Order
from app.services.checkout_service import to_cents


FAKE_SK = 'sk_test_' + ('x' * 24)
FAKE_PK = 'pk_test_' + ('x' * 24)
FAKE_WH = 'whsec_' + ('y' * 24)


class FakeIntent:
    def __init__(self, status='succeeded', amount=2999, intent_id='pi_test_abc'):
        self.id = intent_id
        self.client_secret = f'{intent_id}_secret_xxx'
        self.status = status
        self.amount = amount
        self.charges = {
            'data': [{'payment_method_details': {'card': {'last4': '4242'}}}]
        }

    def to_dict(self):
        return {
            'id': self.id,
            'status': self.status,
            'charges': self.charges,
        }

    def __getitem__(self, key):
        return getattr(self, key)


class GoLiveOpsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['STRIPE_SECRET_KEY'] = ''
        self.app.config['STRIPE_PUBLISHABLE_KEY'] = ''
        self.app.config['STRIPE_WEBHOOK_SECRET'] = ''
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        admin = User(username='admin', email='admin@florashop.com', password='x', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
        category = Category(name='Fleurs Fraîches')
        db.session.add(category)
        db.session.flush()
        self.product = Product(
            name='Bouquet Test',
            price=Decimal('29.99'),
            category_id=category.id,
            stock_qty=12,
        )
        db.session.add(self.product)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login_admin(self):
        response = self.client.post(
            '/api/v1/auth/login',
            json={'email': 'admin@florashop.com', 'password': 'admin123'},
        )
        return response.get_json()['data']['token']

    def enable_stripe(self):
        self.app.config['STRIPE_SECRET_KEY'] = FAKE_SK
        self.app.config['STRIPE_PUBLISHABLE_KEY'] = FAKE_PK
        self.app.config['STRIPE_WEBHOOK_SECRET'] = FAKE_WH

    def guest_payload(self, extra=None):
        payload = {
            'email': 'invite@test.com',
            'name': 'Invité',
            'phone': '+33612345678',
            'payment_method': 'card',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        }
        if extra:
            payload.update(extra)
        return payload

    def test_config_stays_test_without_keys(self):
        response = self.client.get('/api/v1/payments/config')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['mode'], 'test')
        self.assertFalse(payload.get('webhook_configured'))
        self.assertIsNone(payload['publishable_key'])

    def test_create_intent_without_stripe_is_503(self):
        response = self.client.post(
            '/api/v1/payments/create-payment-intent',
            json=self.guest_payload(),
        )
        self.assertEqual(response.status_code, 503)

    def test_checkout_rejected_when_stripe_is_configured(self):
        self.enable_stripe()
        response = self.client.post('/api/v1/payments/checkout', json=self.guest_payload({
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
        }))
        self.assertEqual(response.status_code, 400)
        self.assertIn('Stripe.js', response.get_json()['error'])
        self.assertEqual(Order.query.count(), 0)

    @patch('app.services.stripe_service.stripe.PaymentIntent.create')
    def test_payment_intent_includes_shipping_and_holds_stock(self, create_intent):
        self.enable_stripe()
        create_intent.return_value = FakeIntent(amount=to_cents(Decimal('38.89')))
        response = self.client.post(
            '/api/v1/payments/create-payment-intent',
            json=self.guest_payload({
                'address': '1 quai 13001 Marseille',
                'fulfillment_type': 'livraison',
                'fulfillment_date': '2035-06-12',
                'fulfillment_slot': 'matin',
            }),
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        body = response.get_json()
        self.assertEqual(body['shipping_amount'], 8.9)
        self.assertEqual(body['total_amount'], 38.89)
        self.assertEqual(body['charge_amount'], 38.89)
        self.assertTrue(body['client_secret'])
        create_intent.assert_called_once()
        self.assertEqual(create_intent.call_args.kwargs['amount'], to_cents(Decimal('38.89')))
        order = Order.query.first()
        self.assertEqual(order.status, 'pending')
        self.assertIsNone(order.prep_status)
        db.session.refresh(self.product)
        self.assertEqual(int(self.product.stock_qty), 12)

    @patch('app.services.stripe_service.stripe.PaymentIntent.retrieve')
    @patch('app.services.stripe_service.stripe.PaymentIntent.create')
    def test_confirm_and_webhook_consume_stock_once(self, create_intent, retrieve):
        self.enable_stripe()
        fake = FakeIntent()
        create_intent.return_value = fake
        retrieve.return_value = fake
        created = self.client.post(
            '/api/v1/payments/create-payment-intent',
            json=self.guest_payload(),
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        pi_id = created.get_json()['payment_intent_id']
        first = self.client.post(
            '/api/v1/payments/confirm-payment',
            json={'payment_intent_id': pi_id, 'email': 'invite@test.com'},
        )
        self.assertEqual(first.status_code, 200, first.get_json())
        self.assertEqual(first.get_json()['order']['status'], 'paid')
        self.assertEqual(first.get_json()['order']['prep_status'], 'a_preparer')
        self.assertNotIn('stripe_payment_intent_id', first.get_json()['order'])
        db.session.refresh(self.product)
        self.assertEqual(int(self.product.stock_qty), 11)

        with patch('app.services.stripe_service.stripe.Webhook.construct_event') as construct:
            construct.return_value = {
                'type': 'payment_intent.succeeded',
                'data': {'object': {'id': pi_id, 'status': 'succeeded'}},
            }
            hook = self.client.post(
                '/api/v1/payments/webhook',
                data=b'{}',
                headers={'Stripe-Signature': 't=1,v1=fake'},
            )
        self.assertEqual(hook.status_code, 200, hook.get_data(as_text=True))
        db.session.refresh(self.product)
        self.assertEqual(int(self.product.stock_qty), 11)
        self.assertEqual(Order.query.filter_by(status='paid').count(), 1)

    def test_webhook_without_signature_is_400(self):
        self.enable_stripe()
        response = self.client.post('/api/v1/payments/webhook', data=b'{}')
        self.assertEqual(response.status_code, 400)

    def test_siren_empty_by_default_and_rejects_invalid(self):
        public = self.client.get('/api/v1/settings').get_json()
        self.assertEqual(public.get('siren') or '', '')
        self.assertEqual(public.get('address') or '', '')
        token = self.login_admin()
        headers = {'Authorization': f'Bearer {token}'}
        bad = self.client.put('/api/v1/settings', json={'siren': '123456789'}, headers=headers)
        self.assertEqual(bad.status_code, 400)
        siret = self.client.put(
            '/api/v1/settings',
            json={'siren': '12345678200012'},
            headers=headers,
        )
        self.assertEqual(siret.status_code, 400)
        ok = self.client.put(
            '/api/v1/settings',
            json={
                'siren': '123456782',
                'address': '12 rue des Lilas, 75011 Paris',
                'legal_form': 'EI',
                'delivery_carrier': 'Colissimo',
                'delivery_fee_overseas': '19.90',
                'delivery_eta_metro': '48 h',
            },
            headers=headers,
        )
        self.assertEqual(ok.status_code, 200, ok.get_json())
        body = ok.get_json()
        self.assertEqual(body['siren'], '123456782')
        self.assertEqual(body['address'], '12 rue des Lilas, 75011 Paris')
        self.assertEqual(body['legal_form'], 'EI')
        self.assertEqual(body['delivery_carrier'], 'Colissimo')
        self.assertEqual(body['delivery_fee_overseas'], 19.9)
        self.assertEqual(body['delivery_eta_metro'], '48 h')
        cleared = self.client.put('/api/v1/settings', json={'siren': ''}, headers=headers)
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.get_json().get('siren') or '', '')

    def test_overseas_quote_uses_dom_fee(self):
        token = self.login_admin()
        self.client.put(
            '/api/v1/settings',
            json={'delivery_carrier': 'Chronopost', 'delivery_fee_overseas': '21.50'},
            headers={'Authorization': f'Bearer {token}'},
        )
        reunion = self.client.get(
            '/api/v1/shipping?type=livraison&address=12 rue 97400 Saint-Denis'
        )
        self.assertEqual(reunion.status_code, 200)
        payload = reunion.get_json()
        self.assertEqual(payload['shipping'], 21.5)
        self.assertEqual(payload['zone'], 'overseas')
        self.assertEqual(payload['carrier'], 'Chronopost')
        paris = self.client.get(
            '/api/v1/shipping?type=livraison&address=12 rue 75001 Paris'
        )
        self.assertEqual(paris.get_json()['shipping'], 8.9)
        self.assertEqual(paris.get_json()['zone'], 'metro')

    def test_mailer_ssl_uses_smtp_ssl(self):
        from app.services import mailer
        os.environ['MAIL_SERVER'] = 'smtp.example.test'
        os.environ['MAIL_PORT'] = '465'
        os.environ['MAIL_SSL'] = '1'
        os.environ['MAIL_STARTTLS'] = '0'
        os.environ['MAIL_FROM'] = 'atelier@example.test'
        os.environ['MAIL_USER'] = 'atelier@example.test'
        os.environ['MAIL_PASSWORD'] = 'secret'
        try:
            smtp = MagicMock()
            smtp.__enter__.return_value = smtp
            with patch('app.services.mailer.smtplib.SMTP_SSL', return_value=smtp) as ssl_ctor:
                with patch('app.services.mailer.smtplib.SMTP') as starttls_ctor:
                    sent = mailer.send_mail('client@test.com', 'Commande', 'Merci')
            self.assertTrue(sent)
            ssl_ctor.assert_called_once()
            starttls_ctor.assert_not_called()
            smtp.login.assert_called_once()
            smtp.send_message.assert_called_once()
        finally:
            for key in (
                'MAIL_SERVER', 'MAIL_PORT', 'MAIL_SSL', 'MAIL_STARTTLS',
                'MAIL_FROM', 'MAIL_USER', 'MAIL_PASSWORD',
            ):
                os.environ[key] = '' if key != 'MAIL_PORT' else ''
            os.environ['MAIL_SERVER'] = ''

    def test_hosting_files_generate_secrets_not_urls(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        setup = (root / 'setup.sh').read_text()
        self.assertIn('openssl rand -hex 32', setup)
        self.assertIn('SECRET_KEY', setup)
        render = (root / 'render.yaml').read_text()
        self.assertIn('generateValue: true', render)
        self.assertIn('FORCE_HTTPS', render)
        self.assertIn('STRIPE_WEBHOOK_SECRET', render)
        env_example = (root / '.env.example').read_text()
        self.assertIn('MAIL_SSL', env_example)
        self.assertIn('VOTRE_DOMAINE', env_example)
        self.assertNotIn('sk_live_', env_example.split('STRIPE_SECRET_KEY=')[1][:20])


if __name__ == '__main__':
    unittest.main()
