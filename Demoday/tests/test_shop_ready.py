import os
import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['STRIPE_SECRET_KEY'] = ''
os.environ['STRIPE_PUBLISHABLE_KEY'] = ''
os.environ['MAIL_SERVER'] = ''
os.environ['PAYPAL_CLIENT_ID'] = ''
os.environ['PAYPAL_SECRET'] = ''
os.environ['TWILIO_ACCOUNT_SID'] = ''

from app import create_app, db
from app.models import User, Category, Product, Order, OrderItem
from app.models.subscription import ShopSubscription
from app.services.invoice_service import invoice_number, split_ttc, build_invoice_pdf
from app.services.subscription_ops import add_months, activate_from_order, mark_delivered


class ShopReadyTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        admin = User(username='admin', email='admin@florashop.com', password='x', is_admin=True)
        client = User(username='marie', email='marie@test.com', password='x', is_admin=False)
        admin.set_password('admin123')
        client.set_password('marie123')
        db.session.add_all([admin, client])
        category = Category(name='Fleurs Fraîches')
        db.session.add(category)
        db.session.flush()
        self.product = Product(
            name='Bouquet Test',
            price=Decimal('40.00'),
            category_id=category.id,
            stock_qty=12,
        )
        db.session.add(self.product)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self, email, password):
        response = self.client.post('/api/v1/auth/login', json={'email': email, 'password': password})
        return response.get_json()['data']['token']

    def pay(self, extra=None, token=None):
        payload = {
            'email': 'marie@test.com',
            'name': 'Marie',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        }
        if extra:
            payload.update(extra)
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return self.client.post('/api/v1/payments/checkout', json=payload, headers=headers)

    def test_tva_split_from_ttc(self):
        ht, tva = split_ttc(Decimal('40.00'), Decimal('10.00'))
        self.assertEqual(ht + tva, Decimal('40.00'))
        self.assertEqual(ht, Decimal('36.36'))
        self.assertEqual(tva, Decimal('3.64'))

    def test_invoice_pdf_and_guest_download(self):
        created = self.pay()
        self.assertEqual(created.status_code, 201, created.get_json())
        order_id = created.get_json()['order']['id']
        order = db.session.get(Order, order_id)
        self.assertTrue(invoice_number(order).startswith('FAC-'))
        buffer, payload = build_invoice_pdf(order)
        self.assertGreater(len(buffer.getvalue()), 200)
        self.assertEqual(payload['total_ttc'], 40.0)
        denied = self.client.get(f'/api/v1/payments/orders/{order_id}/invoice.pdf')
        self.assertEqual(denied.status_code, 404)
        pdf = self.client.get(
            f'/api/v1/payments/orders/{order_id}/invoice.pdf?email=marie@test.com'
        )
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.mimetype, 'application/pdf')
        other = self.client.get(
            f'/api/v1/payments/orders/{order_id}/invoice.pdf?email=other@test.com'
        )
        self.assertEqual(other.status_code, 404)

    def test_sale_price_is_charged(self):
        self.product.is_on_sale = True
        self.product.sale_price = Decimal('32.00')
        db.session.commit()
        created = self.pay()
        self.assertEqual(created.status_code, 201, created.get_json())
        self.assertEqual(created.get_json()['order']['total_amount'], 32.0)
        catalog = self.client.get('/api/v1/products').get_json()
        row = next(item for item in catalog if item['name'] == 'Bouquet Test')
        self.assertTrue(row['is_on_sale'])
        self.assertEqual(row['effective_price'], 32.0)

    def test_deposit_settle_by_client(self):
        created = self.pay({'deposit': True})
        self.assertEqual(created.status_code, 201, created.get_json())
        order = created.get_json()['order']
        self.assertEqual(order['status'], 'deposit')
        remaining = order['remaining_amount']
        self.assertAlmostEqual(remaining, 28.0, places=2)
        token = self.login('marie@test.com', 'marie123')
        settled = self.client.post(
            f"/api/v1/payments/orders/{order['id']}/settle",
            json={
                'payment_method': 'card',
                'card_number': '4242424242424242',
                'card_expiry': '12/34',
                'card_cvc': '123',
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(settled.status_code, 200, settled.get_json())
        self.assertEqual(settled.get_json()['order']['status'], 'paid')

    def test_tracking_and_refund(self):
        created = self.pay()
        order_id = created.get_json()['order']['id']
        token = self.login('admin@florashop.com', 'admin123')
        headers = {'Authorization': f'Bearer {token}'}
        tracked = self.client.patch(
            f'/api/v1/payments/orders/{order_id}',
            json={'tracking_number': '6X1234567890'},
            headers=headers,
        )
        self.assertEqual(tracked.status_code, 200, tracked.get_json())
        self.assertEqual(tracked.get_json()['order']['tracking_number'], '6X1234567890')
        qty_before = int(db.session.get(Product, self.product.id).stock_qty)
        refunded = self.client.post(
            f'/api/v1/payments/orders/{order_id}/refund',
            json={},
            headers=headers,
        )
        self.assertEqual(refunded.status_code, 200, refunded.get_json())
        self.assertEqual(refunded.get_json()['order']['status'], 'refunded')
        db.session.refresh(self.product)
        self.assertEqual(int(self.product.stock_qty), qty_before + 1)

    def test_subscription_contract_and_delivery(self):
        created = self.pay({
            'items': [{'product_id': 'subscription_monthly', 'quantity': 1, 'type': 'subscription'}],
            'email': 'marie@test.com',
            'name': 'Marie',
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        row = ShopSubscription.query.filter_by(email='marie@test.com').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.status, 'active')
        self.assertEqual(row.period_months, 1)
        self.assertEqual(row.deliveries_count, 1)
        token = self.login('admin@florashop.com', 'admin123')
        due = self.client.get('/api/v1/atelier/today', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(due.status_code, 200)
        row.next_delivery = date.today()
        db.session.commit()
        due = self.client.get('/api/v1/atelier/today', headers={'Authorization': f'Bearer {token}'})
        self.assertTrue(due.get_json()['subscriptions_due'])
        delivered = self.client.patch(
            f'/api/v1/subscriptions/{row.id}',
            json={'deliver': True},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(delivered.status_code, 200, delivered.get_json())
        self.assertEqual(delivered.get_json()['subscription']['deliveries_count'], 2)

    def test_event_quote_reaches_inbox(self):
        created = self.client.post('/api/v1/contact', json={
            'kind': 'devis',
            'name': 'Léa Martin',
            'email': 'lea@test.com',
            'event_date': '12 juin',
            'lieu': 'Orangerie',
            'budget': '1200 €',
            'message': 'Arche et centres de table pour un mariage.',
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        token = self.login('admin@florashop.com', 'admin123')
        inbox = self.client.get('/api/v1/contact', headers={'Authorization': f'Bearer {token}'})
        row = inbox.get_json()['requests'][0]
        self.assertEqual(row['kind'], 'devis')
        self.assertIn('Orangerie', row['message'])

    def test_paypal_and_sms_stay_off_without_keys(self):
        config = self.client.get('/api/v1/payments/config').get_json()
        self.assertFalse(config['paypal_configured'])
        self.assertFalse(config['sms_configured'])
        self.assertIsNone(config['paypal_client_id'])
        create = self.client.post('/api/v1/payments/paypal/create', json={
            'email': 'marie@test.com',
            'name': 'Marie',
            'phone': '+33612345678',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(create.status_code, 503)

    def test_tva_rate_saved_in_settings(self):
        token = self.login('admin@florashop.com', 'admin123')
        updated = self.client.put(
            '/api/v1/settings',
            json={'tva_rate': '20'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()['tva_rate'], 20.0)

    def test_add_months_keeps_calendar(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))

    def test_pages_ready_ui(self):
        commandes = self.client.get('/commandes.html').get_data(as_text=True)
        self.assertIn('invoice.pdf', commandes)
        self.assertIn('settle-form', commandes)
        admin = self.client.get('/admin.html').get_data(as_text=True)
        self.assertIn('setting-tva-rate', admin)
        self.assertIn('data-order-refund', admin)
        self.assertIn('data-order-tracking', admin)
        self.assertIn('atelier-subscriptions', admin)
        event = self.client.get('/evenementiel.html').get_data(as_text=True)
        self.assertIn('devis-form', event)
        self.assertIn('kind: \'devis\'', event)
