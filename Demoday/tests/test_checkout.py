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
        admin = User(username='admin', email='admin@florashop.com', password='admin123', is_admin=True)
        client = User(username='marie', email='marie@test.com', password='marie123', is_admin=False)
        other = User(username='client', email='client@test.com', password='client123', is_admin=False)
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
        self.assertEqual(payload['order']['payment_label'], 'Paiement refusé')
        self.assertIsNone(payload['order']['prep_status'])
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

    def test_admin_advances_prep_and_settles_deposit(self):
        created = self.client.post('/api/v1/payments/checkout', json={
            'email': 'marie@test.com',
            'name': 'Marie Test',
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

    def test_client_order_json_hides_stripe_id(self):
        order_id, token = self._checkout_as('marie@test.com', 'marie123', 'Marie Test')
        order = db.session.get(Order, order_id)
        order.stripe_payment_intent_id = 'pi_secret_should_not_leak'
        db.session.commit()
        mine = self.client.get(
            '/api/v1/payments/my-orders',
            headers={'Authorization': f'Bearer {token}'},
        )
        payload = next(row for row in mine.get_json()['orders'] if row['id'] == order_id)
        self.assertNotIn('stripe_payment_intent_id', payload)
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
        self.assertIn('Suivi de mes commandes', html)
        self.assertIn('/api/v1/payments/my-orders', html)
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
        checkout = self.client.get('/checkout.html').get_data(as_text=True)
        self.assertIn('Suivre ma commande', checkout)
        self.assertIn('commandes.html#order-', checkout)
        self.assertIn('success-actions', checkout)


if __name__ == '__main__':
    unittest.main()
