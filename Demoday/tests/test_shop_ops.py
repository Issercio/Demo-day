import os
import unittest
from datetime import date, timedelta

os.environ['DATABASE_URL'] = 'sqlite://'

from app import create_app, db
from app.models import User, Category, Product


class ShopOpsTestCase(unittest.TestCase):
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
        self.product = Product(name='Bouquet Test', price=29.99, category_id=category.id, stock_qty=12)
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

    def test_contact_form_reaches_admin(self):
        created = self.client.post('/api/v1/contact', json={
            'name': 'Léa Martin',
            'email': 'lea@test.com',
            'message': 'Devis pour un mariage en juin, arche et boutonnieres.',
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        listed = self.client.get('/api/v1/contact')
        self.assertEqual(listed.status_code, 401)
        token = self.login('admin@florashop.com', 'admin123')
        inbox = self.client.get('/api/v1/contact', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(inbox.status_code, 200)
        rows = inbox.get_json()['requests']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'nouveau')
        patched = self.client.patch(
            f"/api/v1/contact/{rows[0]['id']}",
            json={'status': 'traite'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.get_json()['request']['status'], 'traite')

    def test_guest_cart_is_stored_on_server(self):
        headers = {'X-Cart-Token': 'guest-token-abc'}
        saved = self.client.put('/api/v1/cart', json={
            'items': [{'id': self.product.id, 'name': 'Bouquet Test', 'quantity': 2}],
        }, headers=headers)
        self.assertEqual(saved.status_code, 200, saved.get_json())
        loaded = self.client.get('/api/v1/cart', headers=headers)
        self.assertEqual(loaded.status_code, 200)
        items = loaded.get_json()['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(int(items[0]['quantity']), 2)
        self.assertEqual(float(items[0]['price']), 29.99)

    def test_login_merges_guest_cart(self):
        self.client.put('/api/v1/cart', json={
            'items': [{'id': self.product.id, 'name': 'Bouquet Test', 'quantity': 1}],
        }, headers={'X-Cart-Token': 'merge-token-1'})
        token = self.login('marie@test.com', 'marie123')
        merged = self.client.get('/api/v1/cart', headers={
            'Authorization': f'Bearer {token}',
            'X-Cart-Token': 'merge-token-1',
        })
        self.assertEqual(merged.status_code, 200)
        self.assertGreaterEqual(merged.get_json()['count'], 1)

    def test_checkout_uses_server_cart_and_stock(self):
        headers = {'X-Cart-Token': 'pay-token-1'}
        self.client.put('/api/v1/cart', json={
            'items': [{'product_id': self.product.id, 'id': self.product.id, 'quantity': 3}],
        }, headers=headers)
        paid = self.client.post('/api/v1/payments/checkout', json={
            'email': 'invite@test.com',
            'name': 'Invité',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'fulfillment_type': 'retrait',
            'fulfillment_date': (date.today() if date.today().weekday() != 6 else date.today() + timedelta(days=1)).isoformat(),
            'fulfillment_slot': 'matin',
        }, headers=headers)
        self.assertEqual(paid.status_code, 201, paid.get_json())
        order = paid.get_json()['order']
        self.assertEqual(order['fulfillment_type'], 'retrait')
        db.session.refresh(self.product)
        self.assertEqual(int(self.product.stock_qty), 9)
        empty = self.client.get('/api/v1/cart', headers=headers)
        self.assertEqual(empty.get_json()['count'], 0)

    def test_out_of_stock_is_rejected(self):
        self.product.stock_qty = 0
        db.session.commit()
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 400)

    def test_atelier_today_is_admin_only(self):
        self.assertEqual(self.client.get('/api/v1/atelier/today').status_code, 401)
        token = self.login('marie@test.com', 'marie123')
        self.assertEqual(
            self.client.get('/api/v1/atelier/today', headers={'Authorization': f'Bearer {token}'}).status_code,
            403,
        )
        admin = self.login('admin@florashop.com', 'admin123')
        today = self.client.get('/api/v1/atelier/today', headers={'Authorization': f'Bearer {admin}'})
        self.assertEqual(today.status_code, 200)
        payload = today.get_json()
        self.assertIn('to_prep', payload)
        self.assertIn('upcoming_pickups', payload)

    def test_admin_page_has_today_board_and_inbox(self):
        html = self.client.get('/admin.html').get_data(as_text=True)
        self.assertIn('atelier-today', html)
        self.assertIn('contact-inbox', html)
        self.assertIn('shop-settings', html)
        self.assertIn('promo-section', html)
        self.assertIn('/static/img/logo.png', html)
        self.assertIn('FloraShop', html)
        self.assertNotIn('Pivoine & Lilas', html.replace('&amp;', '&'))
        self.assertNotIn('pivoine-lilas', html.lower())

    def test_site_brand_is_florashop(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1].joinpath('app/templates')
        offenders = []
        for path in sorted(root.glob('*.html')):
            text = path.read_text()
            plain = text.replace('&amp;', '&')
            if 'Pivoine & Lilas' in plain or 'pivoine-lilas' in text.lower():
                offenders.append(path.name)
        self.assertEqual(offenders, [])
        home = (root / 'accueil.html').read_text()
        self.assertIn('FloraShop', home)

    def test_admin_can_set_stock(self):
        token = self.login('admin@florashop.com', 'admin123')
        updated = self.client.put(
            f'/api/v1/products/{self.product.id}',
            json={'stock_qty': 2},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        listed = self.client.get('/api/v1/products').get_json()
        row = next(item for item in listed if item['id'] == self.product.id)
        self.assertEqual(row['stock_qty'], 2)
        self.assertEqual(row['stock_status'], 'low')
