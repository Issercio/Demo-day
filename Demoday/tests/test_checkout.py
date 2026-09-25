import os
import unittest

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
        admin = User(username='admin', email='admin@florashop.com', password='x', is_admin=True)
        client = User(username='marie', email='marie@test.com', password='x', is_admin=False)
        other = User(username='client', email='client@test.com', password='x', is_admin=False)
        admin.set_password('admin123')
        client.set_password('marie123')
        other.set_password('client123')
        db.session.add_all([admin, client, other])
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
            'phone': '+33612345678',
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
        self.assertEqual(order['payment_label'], 'Payée')
        self.assertEqual(order['prep_status'], 'a_preparer')
        self.assertEqual(order['prep_label'], 'À préparer')
        self.assertIsNone(order['deposit_amount'])
        self.assertEqual(order['total_amount'], 59.98)
        self.assertEqual(order['card_last4'], '4242')
        self.assertEqual(order['payment_method'], 'card')
        self.assertEqual(len(order['items']), 1)
        self.assertEqual(order['items'][0]['quantity'], 2)
        self.assertTrue(order['guest'])
        self.assertEqual(order['phone'], '+33612345678')
        self.assertIsNone(order['user_id'])
        self.assertEqual(Order.query.filter_by(status='paid').count(), 1)

    def test_prices_come_from_database_not_client(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
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
            'phone': '+33612345678',
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
        self.assertEqual(payload['order']['payment_label'], 'Paiement refusé')
        self.assertIsNone(payload['order']['prep_status'])
        self.assertEqual(Order.query.filter_by(status='paid').count(), 0)

    def test_insufficient_funds_card(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
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
            'phone': '+33612345678',
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
            'phone': '+33612345678',
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
            'phone': '+33612345678',
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
            'phone': '+33612345678',
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
        self.assertEqual(orders[0]['customer_name'], 'Marie Test')
        self.assertEqual(orders[0]['payment_method'], 'card')
        self.assertEqual(orders[0]['card_last4'], '4242')
        self.assertEqual(orders[0]['items'][0]['quantity'], 1)
        self.assertAlmostEqual(orders[0]['items'][0]['price'], 29.99, places=2)
        self.assertEqual(orders[0]['items'][0]['product']['name'], 'Bouquet Test')

    def test_checkout_total_uses_decimal_cents(self):
        """10.10 x 3 must be 30.30, not a binary-float approximation."""
        self.product.price = '10.10'
        db.session.commit()
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 3}],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()['order']['total_amount'], 30.30)

    def test_unknown_luhn_card_is_declined(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4111111111111111',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 402, response.get_json())
        payload = response.get_json()
        self.assertIn('inconnue', payload['error'].lower())
        self.assertEqual(payload['order']['status'], 'failed')
        self.assertEqual(Order.query.filter_by(status='paid').count(), 0)

    def _checkout_as(self, email, password, name):
        token = self.login(email, password)
        response = self.client.post(
            '/api/v1/payments/checkout',
            json={
                'email': email,
                'name': name,
                'payment_method': 'card',
                'card_number': '4242424242424242',
                'card_expiry': '12/34',
                'card_cvc': '123',
                'items': [{'product_id': self.product.id, 'quantity': 1}],
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['order']['id'], token

    def test_anonymous_cannot_read_order(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        order_id = response.get_json()['order']['id']
        detail = self.client.get(f'/api/v1/payments/orders/{order_id}')
        self.assertEqual(detail.status_code, 401)

    def test_buyer_can_read_own_order(self):
        order_id, token = self._checkout_as('marie@test.com', 'marie123', 'Marie Test')
        response = self.client.get(
            f'/api/v1/payments/orders/{order_id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['order']['email'], 'marie@test.com')

    def test_other_client_cannot_read_order(self):
        order_id, _token = self._checkout_as('marie@test.com', 'marie123', 'Marie Test')
        other = self.login('client@test.com', 'client123')
        response = self.client.get(
            f'/api/v1/payments/orders/{order_id}',
            headers={'Authorization': f'Bearer {other}'},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_read_any_order(self):
        order_id, _token = self._checkout_as('marie@test.com', 'marie123', 'Marie Test')
        admin = self.login('admin@florashop.com', 'admin123')
        response = self.client.get(
            f'/api/v1/payments/orders/{order_id}',
            headers={'Authorization': f'Bearer {admin}'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['order']['id'], order_id)

    def test_logged_in_checkout_ignores_spoofed_email(self):
        token = self.login('marie@test.com', 'marie123')
        response = self.client.post(
            '/api/v1/payments/checkout',
            json={
                'email': 'admin@florashop.com',
                'name': 'Not Admin',
                'payment_method': 'card',
                'card_number': '4242424242424242',
                'card_expiry': '12/34',
                'card_cvc': '123',
                'items': [{'product_id': self.product.id, 'quantity': 1}],
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        order = response.get_json()['order']
        self.assertEqual(order['email'], 'marie@test.com')
        marie = User.query.filter_by(email='marie@test.com').first()
        self.assertEqual(order['user_id'], marie.id)

    def test_invalid_bearer_token_rejected_on_checkout(self):
        response = self.client.post(
            '/api/v1/payments/checkout',
            json={
                'email': 'marie@test.com',
                'name': 'Marie Test',
                'payment_method': 'card',
                'card_number': '4242424242424242',
                'card_expiry': '12/34',
                'card_cvc': '123',
                'items': [{'product_id': self.product.id, 'quantity': 1}],
            },
            headers={'Authorization': 'Bearer not-a-jwt'},
        )
        self.assertEqual(response.status_code, 401)

    def test_empty_cart_is_rejected(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [],
        })
        self.assertEqual(response.status_code, 400)

    def test_unknown_product_is_rejected(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': 99999, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 400)

    def test_saved_card_sandbox_creates_paid_order(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'saved',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        order = response.get_json()['order']
        self.assertEqual(order['status'], 'paid')
        self.assertEqual(order['payment_method'], 'saved')
        self.assertEqual(order['card_last4'], '4242')
        self.assertEqual(order['prep_status'], 'a_preparer')

    def test_missing_order_is_not_found(self):
        token = self.login('marie@test.com', 'marie123')
        response = self.client.get(
            '/api/v1/payments/orders/99999',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 404)

    def test_deposit_checkout_records_thirty_percent(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'deposit': True,
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        order = response.get_json()['order']
        self.assertEqual(order['status'], 'deposit')
        self.assertEqual(order['payment_label'], 'Acompte versé')
        self.assertEqual(order['prep_status'], 'a_preparer')
        self.assertEqual(order['prep_label'], 'À préparer')
        self.assertEqual(order['total_amount'], 29.99)
        self.assertEqual(order['deposit_amount'], 9.00)
        self.assertEqual(order['remaining_amount'], 20.99)

    def test_client_cannot_patch_order(self):
        order_id, token = self._checkout_as('marie@test.com', 'marie123', 'Marie Test')
        response = self.client.patch(
            f'/api/v1/payments/orders/{order_id}',
            json={'prep_status': 'pret'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 403)

    def test_client_cannot_delete_order(self):
        order_id, token = self._checkout_as('marie@test.com', 'marie123', 'Marie Test')
        response = self.client.delete(
            f'/api/v1/payments/orders/{order_id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIsNotNone(db.session.get(Order, order_id))

    def test_admin_can_delete_order(self):
        created = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        order_id = created.get_json()['order']['id']
        admin = self.login('admin@florashop.com', 'admin123')
        response = self.client.delete(
            f'/api/v1/payments/orders/{order_id}',
            headers={'Authorization': f'Bearer {admin}'},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertIsNone(db.session.get(Order, order_id))

    def test_anonymous_cannot_delete_order(self):
        created = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        order_id = created.get_json()['order']['id']
        response = self.client.delete(f'/api/v1/payments/orders/{order_id}')
        self.assertEqual(response.status_code, 401)
        self.assertIsNotNone(db.session.get(Order, order_id))

    def test_admin_advances_prep_and_settles_deposit(self):
        created = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'deposit': True,
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        order_id = created.get_json()['order']['id']
        admin = self.login('admin@florashop.com', 'admin123')
        headers = {'Authorization': f'Bearer {admin}'}
        prep = self.client.patch(
            f'/api/v1/payments/orders/{order_id}',
            json={'prep_status': 'en_preparation'},
            headers=headers,
        )
        self.assertEqual(prep.status_code, 200, prep.get_json())
        self.assertEqual(prep.get_json()['order']['prep_status'], 'en_preparation')
        self.assertEqual(prep.get_json()['order']['prep_label'], 'En préparation')
        invalid = self.client.patch(
            f'/api/v1/payments/orders/{order_id}',
            json={'prep_status': 'livree'},
            headers=headers,
        )
        self.assertEqual(invalid.status_code, 400)
        settled = self.client.patch(
            f'/api/v1/payments/orders/{order_id}',
            json={'settle_payment': True},
            headers=headers,
        )
        self.assertEqual(settled.status_code, 200, settled.get_json())
        payload = settled.get_json()['order']
        self.assertEqual(payload['status'], 'paid')
        self.assertEqual(payload['payment_label'], 'Payée')
        self.assertEqual(payload['deposit_amount'], 9.00)
        self.assertIsNone(payload['remaining_amount'])
        already = self.client.patch(
            f'/api/v1/payments/orders/{order_id}',
            json={'settle_payment': True},
            headers=headers,
        )
        self.assertEqual(already.status_code, 400)

    def test_cannot_prep_a_failed_order(self):
        failed = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4000000000000002',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        order_id = failed.get_json()['order']['id']
        admin = self.login('admin@florashop.com', 'admin123')
        response = self.client.patch(
            f'/api/v1/payments/orders/{order_id}',
            json={'prep_status': 'a_preparer'},
            headers={'Authorization': f'Bearer {admin}'},
        )
        self.assertEqual(response.status_code, 400)

    def test_anonymous_cannot_list_own_orders(self):
        response = self.client.get('/api/v1/payments/my-orders')
        self.assertEqual(response.status_code, 401)

    def test_client_lists_only_own_orders(self):
        marie_id, marie_token = self._checkout_as('marie@test.com', 'marie123', 'Marie Test')
        other_id, _other_token = self._checkout_as('client@test.com', 'client123', 'Léa Martin')
        mine = self.client.get(
            '/api/v1/payments/my-orders',
            headers={'Authorization': f'Bearer {marie_token}'},
        )
        self.assertEqual(mine.status_code, 200, mine.get_json())
        payload = mine.get_json()['orders']
        ids = [order['id'] for order in payload]
        self.assertIn(marie_id, ids)
        self.assertNotIn(other_id, ids)
        self.assertTrue(all(order['email'] == 'marie@test.com' for order in payload))
        mine_order = next(order for order in payload if order['id'] == marie_id)
        self.assertEqual(mine_order['payment_label'], 'Payée')
        self.assertEqual(mine_order['prep_status'], 'a_preparer')
        self.assertEqual(mine_order['prep_label'], 'À préparer')

    def test_guest_order_shows_after_login_by_email(self):
        created = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Dupont',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        order_id = created.get_json()['order']['id']
        token = self.login('marie@test.com', 'marie123')
        mine = self.client.get(
            '/api/v1/payments/my-orders',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(mine.status_code, 200)
        ids = [order['id'] for order in mine.get_json()['orders']]
        self.assertIn(order_id, ids)

    def test_guest_checkout_requires_phone_or_address(self):
        missing = self.client.post('/api/v1/payments/checkout', json={
            'email': 'invite@test.com',
            'name': 'Invité Test',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(missing.status_code, 400, missing.get_json())
        by_address = self.client.post('/api/v1/payments/checkout', json={
            'email': 'invite@test.com',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'address': '12 rue des Lilas, 74140 Sciez',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(by_address.status_code, 201, by_address.get_json())
        order = by_address.get_json()['order']
        self.assertTrue(order['guest'])
        self.assertEqual(order['customer_name'], 'Invité')
        self.assertEqual(order['address'], '12 rue des Lilas, 74140 Sciez')
        self.assertIsNone(order['phone'])

    def test_client_order_json_hides_stripe_id(self):
        order_id, token = self._checkout_as('marie@test.com', 'marie123', 'Marie Test')
        order = db.session.get(Order, order_id)
        order.stripe_payment_intent_id = 'pi_secret_should_not_leak'
        order.payment_reference = 'pi_secret_should_not_leak'
        db.session.commit()
        mine = self.client.get(
            '/api/v1/payments/my-orders',
            headers={'Authorization': f'Bearer {token}'},
        )
        payload = next(row for row in mine.get_json()['orders'] if row['id'] == order_id)
        self.assertNotIn('stripe_payment_intent_id', payload)
        self.assertNotEqual(payload.get('payment_reference'), 'pi_secret_should_not_leak')
        detail = self.client.get(
            f'/api/v1/payments/orders/{order_id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn('stripe_payment_intent_id', detail.get_json()['order'])
        admin = self.login('admin@florashop.com', 'admin123')
        listed = self.client.get(
            '/api/v1/payments/orders',
            headers={'Authorization': f'Bearer {admin}'},
        )
        admin_order = next(row for row in listed.get_json()['orders'] if row['id'] == order_id)
        self.assertEqual(admin_order['stripe_payment_intent_id'], 'pi_secret_should_not_leak')

    def test_commandes_page_has_client_tracking(self):
        html = self.client.get('/commandes.html').get_data(as_text=True)
        self.assertEqual(self.client.get('/commandes.html').status_code, 200)
        self.assertEqual(self.client.get('/commandes').status_code, 200)
        self.assertIn('Suivi de commande', html)
        self.assertIn('/api/v1/payments/my-orders', html)
        self.assertIn('/api/v1/payments/track', html)
        self.assertIn('guest-track-form', html)
        self.assertIn('track-steps', html)
        self.assertIn('À préparer', html)
        self.assertIn('not(:last-child)::after', html)
        self.assertIn('Voir le détail', html)
        self.assertIn('data-open-order', html)
        self.assertIn('/api/v1/payments/orders/', html)
        self.assertNotIn('settle_payment', html)
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        js = root.joinpath('app/static/js/api.js').read_text()
        self.assertIn('Mes commandes', js)
        self.assertIn('Suivre une commande', js)
        checkout = self.client.get('/checkout.html').get_data(as_text=True)
        self.assertIn('Suivre ma commande', checkout)
        self.assertIn('commandes.html', checkout)
        self.assertIn('success-actions', checkout)
        self.assertIn('identity-gate', checkout)
        self.assertIn('Continuer en invité', checkout)
        self.assertIn('Créer un compte', checkout)
        self.assertIn('fulfillment-date', checkout)
        self.assertIn('card-message', checkout)

    def test_checkout_rejects_payment_intent_id(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'payment_intent_id': 'pi_stolen_from_someone_else',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('confirm-payment', (response.get_json() or {}).get('error', ''))
        self.assertEqual(Order.query.count(), 0)

    def test_confirm_payment_requires_auth(self):
        response = self.client.post(
            '/api/v1/payments/confirm-payment',
            json={'payment_intent_id': 'pi_anything'},
        )
        self.assertEqual(response.status_code, 401)

    def test_confirm_payment_rejects_other_client(self):
        order_id, _token = self._checkout_as('marie@test.com', 'marie123', 'Marie Test')
        order = db.session.get(Order, order_id)
        order.stripe_payment_intent_id = 'pi_owned_by_marie'
        db.session.commit()
        other = self.login('client@test.com', 'client123')
        response = self.client.post(
            '/api/v1/payments/confirm-payment',
            json={'payment_intent_id': 'pi_owned_by_marie'},
            headers={'Authorization': f'Bearer {other}'},
        )
        self.assertEqual(response.status_code, 403)

    def test_create_payment_intent_rejects_bad_token(self):
        response = self.client.post(
            '/api/v1/payments/create-payment-intent',
            json={
                'email': 'admin@florashop.com',
                'user_id': 1,
                'items': [{'product_id': self.product.id, 'quantity': 1}],
            },
            headers={'Authorization': 'Bearer not-a-jwt'},
        )
        self.assertEqual(response.status_code, 401)

    def test_card_success_reference_is_not_a_stripe_id(self):
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        order = response.get_json()['order']
        self.assertFalse(str(order.get('payment_reference') or '').startswith('pi_'))
        self.assertNotIn('stripe_payment_intent_id', order)

    def test_checkout_saves_fulfillment_and_card_message(self):
        from datetime import date, timedelta
        wanted = (date.today() + timedelta(days=2)).isoformat()
        response = self.client.post('/api/v1/payments/checkout', json={
            'email': 'invite@test.com',
            'name': 'Invité Fleurs',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'fulfillment_type': 'retrait',
            'fulfillment_date': wanted,
            'fulfillment_slot': 'apres-midi',
            'card_message': 'Pour maman, avec tout mon amour.',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        order = response.get_json()['order']
        self.assertEqual(order['fulfillment_type'], 'retrait')
        self.assertEqual(order['fulfillment_date'], wanted)
        self.assertEqual(order['fulfillment_slot'], 'apres-midi')
        self.assertEqual(order['card_message'], 'Pour maman, avec tout mon amour.')
        self.assertTrue(response.get_json().get('demo_notice'))

    def test_guest_can_track_order_by_email_and_code(self):
        created = self.client.post('/api/v1/payments/checkout', json={
            'email': 'guest-track@test.com',
            'name': 'Invité',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        order_id = created.get_json()['order']['id']

        denied = self.client.get('/api/v1/payments/my-orders')
        self.assertEqual(denied.status_code, 401)

        found = self.client.post('/api/v1/payments/track', json={
            'email': 'guest-track@test.com',
            'order_id': order_id,
        })
        self.assertEqual(found.status_code, 200, found.get_json())
        self.assertEqual(found.get_json()['orders'][0]['id'], order_id)

        missing = self.client.post('/api/v1/payments/track', json={
            'email': 'other@test.com',
            'order_id': order_id,
        })
        self.assertEqual(missing.status_code, 404)

        code_res = self.client.post('/api/v1/payments/track-request', json={
            'email': 'guest-track@test.com',
        })
        self.assertEqual(code_res.status_code, 200, code_res.get_json())
        demo_code = code_res.get_json()['demo_code']
        listed = self.client.post('/api/v1/payments/track', json={
            'email': 'guest-track@test.com',
            'code': demo_code,
        })
        self.assertEqual(listed.status_code, 200, listed.get_json())
        self.assertEqual(listed.get_json()['orders'][0]['id'], order_id)

    def test_checkout_decrements_server_stock_and_rejects_out_of_stock(self):
        self.product.stock_qty = 1
        db.session.commit()
        ok = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(ok.status_code, 201, ok.get_json())
        db.session.refresh(self.product)
        self.assertEqual(self.product.stock_qty, 0)

        refused = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
            'phone': '+33612345678',
            'payment_method': 'card',
            'card_number': '4242424242424242',
            'card_expiry': '12/34',
            'card_cvc': '123',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        })
        self.assertEqual(refused.status_code, 400, refused.get_json())
        self.assertIn('stock', refused.get_json()['error'].lower())

    def test_prep_patch_returns_demo_sms_notice(self):
        order_id, token = self._checkout_as('marie@test.com', 'marie123', 'Marie Test')
        user = User.query.filter_by(email='marie@test.com').first()
        user.phone = '+33612345678'
        order = db.session.get(Order, order_id)
        order.phone = '+33612345678'
        db.session.commit()
        admin = self.login('admin@florashop.com', 'admin123')
        response = self.client.patch(
            f'/api/v1/payments/orders/{order_id}',
            json={'prep_status': 'en_preparation'},
            headers={'Authorization': f'Bearer {admin}'},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['order']['prep_status'], 'en_preparation')
        self.assertIn('en préparation', response.get_json()['demo_notice'])
        self.assertEqual(response.get_json()['notice']['channel'], 'sms')


if __name__ == '__main__':
    unittest.main()
