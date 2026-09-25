"""Batterie de non-régression : fuites, IDOR, auth, commerce, pages."""

import os
import unittest
from datetime import date, timedelta
from unittest.mock import patch

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['STRIPE_SECRET_KEY'] = ''
os.environ['STRIPE_PUBLISHABLE_KEY'] = ''
os.environ['MAIL_SERVER'] = ''

from app import create_app, db
from app.models import User, Category, Product, Order

SECRET_JSON_KEYS = (
    'password',
    'verify_code_hash',
    'verify_code_expires',
    'failed_login_count',
    'locked_until',
    'stripe_payment_intent_id',
)

ADMIN_ONLY = (
    ('GET', '/api/v1/users'),
    ('GET', '/api/v1/contact'),
    ('GET', '/api/v1/atelier/today'),
    ('GET', '/api/v1/promos'),
    ('GET', '/api/v1/payments/orders'),
    ('PUT', '/api/v1/settings'),
    ('POST', '/api/v1/categories'),
    ('POST', '/api/v1/products'),
    ('POST', '/api/v1/promos'),
)

PUBLIC_GET = (
    '/api/v1/products',
    '/api/v1/categories',
    '/api/v1/themes',
    '/api/v1/settings',
    '/api/v1/payments/config',
)


def open_day():
    day = date.today()
    while day.weekday() == 6:
        day += timedelta(days=1)
    return day


def walk(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


class BatteryTestCase(unittest.TestCase):
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
        admin = User(username='admin', email='admin@florashop.com', password='x', is_admin=True)
        marie = User(username='marie', email='marie@test.com', password='x', is_admin=False)
        other = User(username='client', email='client@test.com', password='x', is_admin=False)
        admin.set_password('admin123')
        marie.set_password('marie123')
        other.set_password('client123')
        db.session.add_all([admin, marie, other])
        category = Category(name='Fleurs Fraîches')
        db.session.add(category)
        db.session.flush()
        self.product = Product(
            name='Bouquet Test',
            price=29.99,
            category_id=category.id,
            stock_qty=12,
            description='Tulipes d’atelier.',
        )
        db.session.add(self.product)
        db.session.commit()
        self.admin = admin
        self.marie = marie
        self.other = other

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self, email, password):
        response = self.client.post('/api/v1/auth/login', json={'email': email, 'password': password})
        payload = response.get_json()
        self.assertTrue(payload.get('success'), payload)
        return payload['data']['token']

    def auth(self, email, password):
        return {'Authorization': f'Bearer {self.login(email, password)}'}

    def pay(self, extra=None, headers=None):
        payload = {
            'email': 'invite@test.com',
            'name': 'Invité',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        }
        if extra:
            payload.update(extra)
        return self.client.post('/api/v1/payments/checkout', json=payload, headers=headers or {})

    def assert_no_secrets(self, payload, extra=()):
        keys = set(walk(payload))
        for name in SECRET_JSON_KEYS + extra:
            self.assertNotIn(name, keys, payload)

    def test_public_catalog_and_settings_are_readable(self):
        for path in PUBLIC_GET:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assert_no_secrets(response.get_json() or {})

    def test_admin_routes_reject_anonymous_and_client(self):
        marie = self.auth('marie@test.com', 'marie123')
        for method, path in ADMIN_ONLY:
            raw = self.client.open(path, method=method, json={'name': 'Hack', 'legal_name': 'Hack'})
            self.assertIn(raw.status_code, (401, 405), (method, path, raw.status_code, raw.get_json()))
            denied = self.client.open(
                path,
                method=method,
                json={'name': 'Hack', 'legal_name': 'Hack', 'code': 'HACK10', 'percent': 10},
                headers=marie,
            )
            self.assertEqual(denied.status_code, 403, (method, path, denied.get_json()))

    def test_login_json_hides_hash_and_lockout(self):
        response = self.client.post('/api/v1/auth/login', json={
            'email': 'marie@test.com',
            'password': 'marie123',
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        user = payload['data']['user']
        self.assert_no_secrets(payload)
        self.assertEqual(user['email'], 'marie@test.com')
        self.assertFalse(user['is_admin'])
        self.assertNotEqual(self.marie.password, 'marie123')
        db.session.refresh(self.marie)
        self.assertTrue(self.marie.has_modern_hash())

    def test_wrong_password_does_not_reveal_account(self):
        missing = self.client.post('/api/v1/auth/login', json={
            'email': 'inconnu@test.com',
            'password': 'whatever1',
        })
        bad = self.client.post('/api/v1/auth/login', json={
            'email': 'marie@test.com',
            'password': 'wrong-password',
        })
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(bad.status_code, 401)
        self.assertEqual(missing.get_json()['message'], bad.get_json()['message'])

    def test_register_cannot_self_promote_and_hides_password(self):
        response = self.client.post('/api/v1/auth/register', json={
            'username': 'intrus',
            'email': 'intrus@test.com',
            'password': 'intrus12',
            'is_admin': True,
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        payload = response.get_json()
        self.assert_no_secrets(payload['data']['user'])
        created = User.query.filter_by(email='intrus@test.com').first()
        self.assertFalse(created.is_admin)
        self.assertNotEqual(created.password, 'intrus12')

    def test_codes_absent_when_testing_flag_is_off(self):
        self.app.config['TESTING'] = False
        try:
            created = self.client.post('/api/v1/auth/register', json={
                'username': 'codecheck',
                'email': 'codecheck@test.com',
                'password': 'codecheck',
            })
            self.assertNotIn('demo_code', created.get_json().get('data') or {})
            forgot = self.client.post('/api/v1/auth/forgot-password', json={
                'email': 'codecheck@test.com',
            })
            unknown = self.client.post('/api/v1/auth/forgot-password', json={
                'email': 'absent@test.com',
            })
            self.assertNotIn('demo_code', forgot.get_json())
            self.assertEqual(forgot.get_json()['message'], unknown.get_json()['message'])
        finally:
            self.app.config['TESTING'] = True

    def test_client_cannot_read_or_edit_other_profile(self):
        headers = self.auth('marie@test.com', 'marie123')
        stolen = self.client.get(f'/api/v1/users/{self.admin.id}', headers=headers)
        self.assertEqual(stolen.status_code, 404)
        self.assertNotIn('admin@florashop.com', stolen.get_data(as_text=True))
        patched = self.client.put(
            f'/api/v1/users/{self.other.id}',
            json={'username': 'Hack'},
            headers=headers,
        )
        self.assertEqual(patched.status_code, 404)
        db.session.refresh(self.other)
        self.assertEqual(self.other.username, 'client')

    def test_client_list_users_is_forbidden(self):
        headers = self.auth('marie@test.com', 'marie123')
        listed = self.client.get('/api/v1/users', headers=headers)
        self.assertEqual(listed.status_code, 403)
        admin = self.auth('admin@florashop.com', 'admin123')
        ok = self.client.get('/api/v1/users', headers=admin)
        self.assertEqual(ok.status_code, 200)
        rows = ok.get_json()
        self.assertGreaterEqual(len(rows), 3)
        for row in rows:
            self.assert_no_secrets(row)

    def test_guest_and_client_orders_are_isolated(self):
        guest = self.pay()
        self.assertEqual(guest.status_code, 201, guest.get_json())
        guest_id = guest.get_json()['order']['id']
        self.assert_no_secrets(guest.get_json()['order'])

        marie_headers = self.auth('marie@test.com', 'marie123')
        marie = self.pay({'email': 'spoof@test.com', 'name': 'Marie'}, headers=marie_headers)
        self.assertEqual(marie.status_code, 201)
        marie_order = marie.get_json()['order']
        self.assertEqual(marie_order['email'], 'marie@test.com')
        self.assert_no_secrets(marie_order)

        other = self.auth('client@test.com', 'client123')
        stolen = self.client.get(f'/api/v1/payments/orders/{marie_order["id"]}', headers=other)
        self.assertEqual(stolen.status_code, 404)
        self.assertNotIn('marie@test.com', stolen.get_data(as_text=True))

        mine = self.client.get('/api/v1/payments/my-orders', headers=marie_headers)
        ids = [row['id'] for row in mine.get_json()['orders']]
        self.assertIn(marie_order['id'], ids)
        self.assertNotIn(guest_id, ids)

        track_ok = self.client.post('/api/v1/payments/track', json={
            'email': 'invite@test.com',
            'order_id': guest_id,
        })
        track_bad = self.client.post('/api/v1/payments/track', json={
            'email': 'client@test.com',
            'order_id': guest_id,
        })
        self.assertEqual(track_ok.status_code, 200)
        self.assert_no_secrets(track_ok.get_json()['order'])
        self.assertEqual(track_bad.status_code, 404)

    def test_admin_sees_stripe_id_client_does_not(self):
        paid = self.pay()
        order_id = paid.get_json()['order']['id']
        row = db.session.get(Order, order_id)
        row.stripe_payment_intent_id = 'pi_secret_should_stay_server_side'
        db.session.commit()

        admin = self.auth('admin@florashop.com', 'admin123')
        detail = self.client.get(f'/api/v1/payments/orders/{order_id}', headers=admin)
        self.assertEqual(detail.get_json()['order']['stripe_payment_intent_id'], 'pi_secret_should_stay_server_side')

        track = self.client.post('/api/v1/payments/track', json={
            'email': 'invite@test.com',
            'order_id': order_id,
        })
        self.assertNotIn('stripe_payment_intent_id', track.get_json()['order'])

    def test_checkout_ignores_client_price_and_empty_cart(self):
        empty = self.pay({'items': []})
        self.assertEqual(empty.status_code, 400)
        inflated = self.pay({'items': [{'product_id': self.product.id, 'quantity': 1, 'price': 0.01}]})
        self.assertEqual(inflated.status_code, 201, inflated.get_json())
        self.assertEqual(inflated.get_json()['order']['total_amount'], 29.99)

    def test_declined_card_does_not_mark_paid(self):
        refused = self.pay({'card_number': '4000000000000002'})
        self.assertEqual(refused.status_code, 402)
        order = refused.get_json()['order']
        self.assertEqual(order['status'], 'failed')
        self.assert_no_secrets(order)

    def test_delivery_covers_france_and_rejects_foreign(self):
        paris = self.client.get('/api/v1/shipping?type=livraison&address=12 rue 75001 Paris')
        marseille = self.client.get('/api/v1/shipping?type=livraison&address=1 quai 13001 Marseille')
        nantes = self.client.get('/api/v1/shipping?type=livraison&address=5 cours 44000 Nantes')
        reunion = self.client.get('/api/v1/shipping?type=livraison&address=12 rue 97400 Saint-Denis')
        rome = self.client.get('/api/v1/shipping?type=livraison&address=Via Roma 00100 Roma')
        incomplete = self.client.get('/api/v1/shipping?type=livraison&address=Marseille')
        self.assertEqual(paris.status_code, 200)
        self.assertEqual(marseille.status_code, 200)
        self.assertEqual(nantes.status_code, 200)
        self.assertEqual(reunion.status_code, 200)
        self.assertEqual(rome.status_code, 400)
        self.assertEqual(incomplete.status_code, 400)

    def test_delivery_restriction_and_restore(self):
        admin = self.auth('admin@florashop.com', 'admin123')
        limited = self.client.put(
            '/api/v1/settings',
            json={'delivery_prefixes': '75,92'},
            headers=admin,
        )
        self.assertFalse(limited.get_json().get('delivery_nationwide'))
        self.assertEqual(self.client.get('/api/v1/shipping?type=livraison&address=1 quai 13001 Marseille').status_code, 400)
        restored = self.client.put(
            '/api/v1/settings',
            json={'delivery_prefixes': 'FR'},
            headers=admin,
        )
        self.assertTrue(restored.get_json().get('delivery_nationwide'))
        self.assertEqual(self.client.get('/api/v1/shipping?type=livraison&address=1 quai 13001 Marseille').status_code, 200)

    def test_contact_inbox_stays_admin_only(self):
        created = self.client.post('/api/v1/contact', json={
            'name': 'Léa',
            'email': 'lea@test.com',
            'message': 'Devis mariage, arche et boutonnières pour juin.',
        })
        self.assertEqual(created.status_code, 201)
        contact_id = created.get_json()['id']
        marie = self.auth('marie@test.com', 'marie123')
        self.assertEqual(self.client.get('/api/v1/contact', headers=marie).status_code, 403)
        self.assertEqual(
            self.client.patch(f'/api/v1/contact/{contact_id}', json={'reply': 'ok'}, headers=marie).status_code,
            403,
        )
        admin = self.auth('admin@florashop.com', 'admin123')
        inbox = self.client.get('/api/v1/contact', headers=admin)
        self.assertEqual(inbox.status_code, 200)
        self.assertEqual(inbox.get_json()['requests'][0]['email'], 'lea@test.com')

    def test_guest_carts_do_not_mix(self):
        self.client.put(
            '/api/v1/cart',
            json={'items': [{'id': self.product.id, 'quantity': 2}]},
            headers={'X-Cart-Token': 'guest-token-aaa'},
        )
        self.client.put(
            '/api/v1/cart',
            json={'items': [{'id': self.product.id, 'quantity': 1}]},
            headers={'X-Cart-Token': 'guest-token-bbb'},
        )
        a = self.client.get('/api/v1/cart', headers={'X-Cart-Token': 'guest-token-aaa'})
        b = self.client.get('/api/v1/cart', headers={'X-Cart-Token': 'guest-token-bbb'})
        self.assertEqual(a.get_json()['count'], 2)
        self.assertEqual(b.get_json()['count'], 1)

    def test_promo_list_is_admin_quote_is_public(self):
        admin = self.auth('admin@florashop.com', 'admin123')
        created = self.client.post(
            '/api/v1/promos',
            json={'code': 'FLEURS10', 'percent': 10},
            headers=admin,
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        self.assertEqual(self.client.get('/api/v1/promos').status_code, 401)
        quote = self.client.get('/api/v1/promo/quote?code=FLEURS10&subtotal=29.99')
        self.assertEqual(quote.status_code, 200)
        self.assertEqual(quote.get_json()['discount'], 3.0)

    def test_client_cannot_create_or_delete_product(self):
        headers = self.auth('marie@test.com', 'marie123')
        created = self.client.post(
            '/api/v1/products',
            json={'name': 'Hack', 'price': 1, 'category_id': self.product.category_id},
            headers=headers,
        )
        self.assertEqual(created.status_code, 403)
        deleted = self.client.delete(f'/api/v1/products/{self.product.id}', headers=headers)
        self.assertEqual(deleted.status_code, 403)
        self.assertIsNotNone(db.session.get(Product, self.product.id))

    def test_forged_admin_claim_cannot_open_atelier(self):
        import jwt
        from datetime import datetime, timezone
        token = jwt.encode(
            {
                'sub': str(self.marie.id),
                'email': self.marie.email,
                'is_admin': True,
                'exp': datetime.now(timezone.utc) + timedelta(days=1),
            },
            self.app.config['SECRET_KEY'],
            algorithm='HS256',
        )
        response = self.client.get(
            '/api/v1/atelier/today',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 403)

    def test_server_error_body_stays_generic(self):
        with patch('app.routes.Product.query') as query:
            query.all.side_effect = RuntimeError('SECRET_LEAK_XYZ')
            response = self.client.get('/api/v1/products')
        self.assertEqual(response.status_code, 500)
        body = response.get_data(as_text=True)
        self.assertNotIn('SECRET_LEAK_XYZ', body)
        self.assertNotIn('Traceback', body)

    def test_webhook_without_signature_does_not_echo_internals(self):
        response = self.client.post('/api/v1/payments/webhook', data=b'{}')
        self.assertIn(response.status_code, (400, 503))
        body = response.get_data(as_text=True)
        self.assertNotIn('Traceback', body)
        self.assertNotIn('sk_live', body)

    def test_pages_do_not_embed_secrets_or_debug_routes(self):
        pages = (
            '/accueil.html',
            '/shop.html',
            '/panier.html',
            '/checkout.html',
            '/commandes.html',
            '/contact.html',
            '/admin.html',
            '/cgv.html',
            '/account.html',
        )
        for path in pages:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            html = response.get_data(as_text=True)
            self.assertNotIn('sk_live', html)
            self.assertNotIn('sk_test_', html)
            self.assertNotIn('/api/v1/debug/', html)
            self.assertNotIn('verify_code_hash', html)

    def test_unknown_pages_are_404(self):
        self.assertEqual(self.client.get('/index.html').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/debug/categories').status_code, 404)
        self.assertEqual(self.client.get('/etc/passwd').status_code, 404)

    def test_payment_config_never_exposes_secret_key(self):
        config = self.client.get('/api/v1/payments/config').get_json()
        blob = str(config)
        self.assertNotIn('sk_', blob)
        self.assertNotIn('SECRET', blob)
        self.assertIn(config['mode'], ('test', 'stripe'))

    def test_order_item_json_uses_catalog_name(self):
        paid = self.pay()
        item = paid.get_json()['order']['items'][0]
        self.assertEqual(item['product']['name'], 'Bouquet Test')
        self.assertAlmostEqual(item['price'], 29.99, places=2)
        self.assertNotIn('password', str(item).lower())
