import os
import unittest
from unittest.mock import patch

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['STRIPE_SECRET_KEY'] = ''
os.environ['STRIPE_PUBLISHABLE_KEY'] = ''

from app import create_app, db
from app.models import User, Category, Product, Order


class CheckoutTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['STRIPE_SECRET_KEY'] = ''
        self.app.config['STRIPE_PUBLISHABLE_KEY'] = ''
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        admin = User(username='admin', email='admin@florashop.com', password='admin123', is_admin=True)
        client = User(username='marie', email='marie@test.com', password='marie123', is_admin=False)
        db.session.add_all([admin, client])
        category = Category(name='Fleurs Fraîches')
        db.session.add(category)
        db.session.flush()
        self.product = Product(name='Bouquet Test', price=29.99, category_id=category.id)
        db.session.add(self.product)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self, email, password):
        response = self.client.post('/api/v1/auth/login', json={'email': email, 'password': password})
        payload = response.get_json()
        self.assertTrue(payload.get('success'), payload)
        return payload['data']['token']

    def test_payment_config_is_test_mode(self):
        response = self.client.get('/api/v1/payments/config')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['mode'], 'test')
        self.assertIsNone(payload['publishable_key'])

    def test_card_success_creates_paid_order(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 2}],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        payload = response.get_json()
        order = payload['order']
        self.assertEqual(order['status'], 'paid')
        self.assertEqual(order['total_amount'], 59.98)
        self.assertEqual(order['card_last4'], '4242')
        self.assertEqual(order['payment_method'], 'card')
        self.assertEqual(len(order['items']), 1)
        self.assertEqual(order['items'][0]['quantity'], 2)
        self.assertEqual(Order.query.filter_by(status='paid').count(), 1)

    def test_prices_come_from_database_not_client(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'card',
            'card_number': '4242 4242 4242 4242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1, 'price': 0.01}],
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['order']['total_amount'], 29.99)

    def test_declined_card_records_failed_order(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'card',
            'card_number': '4000000000000002',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 402)
        payload = response.get_json()
        self.assertIn('refus', payload['error'].lower())
        self.assertEqual(payload['order']['status'], 'failed')
        self.assertEqual(Order.query.filter_by(status='paid').count(), 0)

    def test_insufficient_funds_card(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'card',
            'card_number': '4000000000009995',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 402)
        self.assertIn('fonds', response.get_json()['error'].lower())

    def test_invalid_card_number_rejected(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'card',
            'card_number': '1234',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 400)

    def test_subscription_line_item(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{
                'product_id': 'subscription_semester',
                'quantity': 1,
                'type': 'subscription',
            }],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        order = response.get_json()['order']
        self.assertEqual(order['total_amount'], 17.99)
        self.assertEqual(order['items'][0]['product']['name'], 'Abonnement Harmonie Semestrielle')

    def test_paypal_creates_paid_order(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'paypal',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 201)
        order = response.get_json()['order']
        self.assertEqual(order['status'], 'paid')
        self.assertEqual(order['payment_method'], 'paypal')
        self.assertTrue(order['payment_reference'].startswith('PAYPAL-'))

    def test_client_cannot_list_orders(self):
        token = self.login('marie@test.com', 'marie123')
        response = self.client.get('/api/v1/payments/orders', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(response.status_code, 403)

    def test_admin_can_list_paid_orders(self):
        self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        token = self.login('admin@florashop.com', 'admin123')
        response = self.client.get('/api/v1/payments/orders', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(response.status_code, 200)
        orders = response.get_json()['orders']
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['email'], 'marie@test.com')

    def test_checkout_total_uses_decimal_cents(self):
        """10.10 x 3 must be 30.30, not a binary-float approximation."""
        self.product.price = '10.10'
        db.session.commit()
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 3}],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()['order']['total_amount'], 30.30)

    def test_paid_checkout_targets_holberton_invoice_mailbox(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        invoice = response.get_json()['invoice']
        self.assertIn('marie@test.com', invoice['to'])
        self.assertIn('9893@holbertonstudents.com', invoice['to'])
        self.assertEqual(invoice['reason'], 'mail_not_configured')
        self.assertFalse(invoice['sent'])

    @patch('app.services.invoice_mail.smtplib.SMTP')
    def test_paid_checkout_sends_invoice_when_smtp_is_configured(self, smtp_cls):
        self.app.config['MAIL_SERVER'] = 'smtp.example.com'
        self.app.config['MAIL_PORT'] = 587
        self.app.config['MAIL_USE_TLS'] = True
        self.app.config['MAIL_USE_SSL'] = False
        self.app.config['MAIL_USERNAME'] = 'shop@example.com'
        self.app.config['MAIL_PASSWORD'] = 'secret'
        self.app.config['MAIL_FROM'] = 'Pivoine & Lilas <shop@example.com>'
        self.app.config['INVOICE_COPY_EMAIL'] = '9893@holbertonstudents.com'
        smtp = smtp_cls.return_value
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertTrue(response.get_json()['invoice']['sent'])
        smtp.starttls.assert_called()
        smtp.login.assert_called_once_with('shop@example.com', 'secret')
        _from, to_addrs, raw = smtp.sendmail.call_args[0]
        self.assertIn('marie@test.com', to_addrs)
        self.assertIn('9893@holbertonstudents.com', to_addrs)
        self.assertIn('9893@holbertonstudents.com', raw)
        self.assertIn('Pivoine', raw)

    def test_client_cannot_resend_invoice(self):
        paid = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        order_id = paid.get_json()['order']['id']
        token = self.login('marie@test.com', 'marie123')
        response = self.client.post(
            f'/api/v1/payments/orders/{order_id}/invoice',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 403)

    @patch('app.services.invoice_mail.smtplib.SMTP')
    def test_admin_can_resend_invoice(self, smtp_cls):
        self.app.config['MAIL_SERVER'] = 'smtp.example.com'
        self.app.config['MAIL_USERNAME'] = 'shop@example.com'
        self.app.config['MAIL_PASSWORD'] = 'secret'
        self.app.config['MAIL_USE_TLS'] = False
        smtp_cls.return_value.sendmail.return_value = {}
        paid = self.client.post('/api/v1/payments/checkout', json={
            'email': 'admin@florashop.com',
            'name': 'Admin Florist',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        order_id = paid.get_json()['order']['id']
        token = self.login('admin@florashop.com', 'admin123')
        response = self.client.post(
            f'/api/v1/payments/orders/{order_id}/invoice',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        invoice = response.get_json()['invoice']
        self.assertTrue(invoice['sent'])
        self.assertIn('9893@holbertonstudents.com', invoice['to'])
        self.assertIn('admin@florashop.com', invoice['to'])


if __name__ == '__main__':
    unittest.main()
