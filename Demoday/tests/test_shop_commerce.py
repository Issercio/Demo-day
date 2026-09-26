import os
import unittest
from datetime import date, timedelta

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['STRIPE_SECRET_KEY'] = ''
os.environ['STRIPE_PUBLISHABLE_KEY'] = ''
os.environ['MAIL_SERVER'] = ''

from app import create_app, db
from app.models import User, Category, Product
from app.models.settings import PromoCode


def open_day():
    day = date.today()
    while day.weekday() == 6:
        day += timedelta(days=1)
    return day


def a_sunday():
    today = date.today()
    return today + timedelta(days=(6 - today.weekday()) % 7)


class ShopCommerceTestCase(unittest.TestCase):
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
        admin.set_password('admin123')
        client.set_password('marie123')
        db.session.add_all([admin, client])
        category = Category(name='Fleurs Fraîches')
        db.session.add(category)
        db.session.flush()
        self.product = Product(
            name='Bouquet Test',
            price=29.99,
            category_id=category.id,
            stock_qty=12,
            description='Tulipes d’atelier, ruban vintage.',
        )
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

    def pay(self, extra=None):
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
        return self.client.post('/api/v1/payments/checkout', json=payload)

    def test_postgres_scheme_is_rewritten(self):
        from app import database_uri
        previous = os.environ.get('DATABASE_URL')
        os.environ['DATABASE_URL'] = 'postgres://u:p@localhost:5432/florashop'
        try:
            self.assertEqual(database_uri(), 'postgresql://u:p@localhost:5432/florashop')
        finally:
            if previous is None:
                os.environ.pop('DATABASE_URL', None)
            else:
                os.environ['DATABASE_URL'] = previous
        public = self.client.get('/api/v1/settings')
        self.assertEqual(public.status_code, 200)
        data = public.get_json()
        self.assertEqual(data['legal_name'], 'FloraShop')
        self.assertTrue(data.get('delivery_nationwide'))
        self.assertEqual(data.get('delivery_prefixes'), 'FR')
        self.assertFalse(data['mail_configured'])
        denied = self.client.put('/api/v1/settings', json={'legal_name': 'Atelier Test'})
        self.assertEqual(denied.status_code, 401)
        token = self.login('admin@florashop.com', 'admin123')
        updated = self.client.put(
            '/api/v1/settings',
            json={
                'legal_name': 'Atelier Test',
                'email': 'atelier@test.com',
                'delivery_fee': '12.50',
                'delivery_prefixes': '75,92',
                'closed_weekdays': '0,6',
                'siren': '',
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        body = updated.get_json()
        self.assertEqual(body['legal_name'], 'Atelier Test')
        self.assertEqual(body['delivery_fee'], 12.5)
        self.assertEqual(body['delivery_prefixes'], '75,92')
        self.assertFalse(body.get('delivery_nationwide'))
        self.assertEqual(body['closed_weekdays'], '0,6')
        self.assertEqual(body.get('siren') or '', '')
        self.assertEqual(body.get('delivery_carrier') or '', '')
        self.assertEqual(body.get('legal_form') or '', '')
        delivery_only = self.client.put(
            '/api/v1/settings',
            json={'delivery_carrier': 'Chronopost'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(delivery_only.status_code, 200, delivery_only.get_json())
        self.assertEqual(delivery_only.get_json()['legal_name'], 'Atelier Test')
        self.assertEqual(delivery_only.get_json()['delivery_carrier'], 'Chronopost')

    def test_guest_can_track_own_order_only(self):
        paid = self.pay()
        self.assertEqual(paid.status_code, 201, paid.get_json())
        order_id = paid.get_json()['order']['id']
        found = self.client.post('/api/v1/payments/track', json={
            'email': 'invite@test.com',
            'order_id': order_id,
        })
        self.assertEqual(found.status_code, 200, found.get_json())
        self.assertEqual(found.get_json()['order']['id'], order_id)
        self.assertNotIn('stripe_payment_intent_id', found.get_json()['order'])
        missing = self.client.post('/api/v1/payments/track', json={
            'email': 'autre@test.com',
            'order_id': order_id,
        })
        self.assertEqual(missing.status_code, 404)

    def test_shipping_quote_and_checkout_adds_fee(self):
        bad = self.client.get('/api/v1/shipping?type=livraison&address=Marseille')
        self.assertEqual(bad.status_code, 400)
        paris = self.client.get('/api/v1/shipping?type=livraison&address=12 rue des Fleurs 75001 Paris')
        self.assertEqual(paris.status_code, 200, paris.get_json())
        self.assertEqual(paris.get_json()['shipping'], 8.9)
        self.assertEqual(paris.get_json()['zone'], 'metro')
        self.assertEqual(paris.get_json()['eta'], '24–48 h')
        marseille = self.client.get('/api/v1/shipping?type=livraison&address=1 quai 13001 Marseille')
        self.assertEqual(marseille.status_code, 200, marseille.get_json())
        self.assertEqual(marseille.get_json()['shipping'], 8.9)
        lyon = self.client.get('/api/v1/shipping?type=livraison&address=5 place Bellecour 69002 Lyon')
        self.assertEqual(lyon.status_code, 200)
        reunion = self.client.get('/api/v1/shipping?type=livraison&address=12 rue de la Plage 97400 Saint-Denis')
        self.assertEqual(reunion.status_code, 200)
        self.assertEqual(reunion.get_json()['shipping'], 16.9)
        self.assertEqual(reunion.get_json()['zone'], 'overseas')
        self.assertEqual(reunion.get_json()['eta'], '3–5 jours ouvrés')
        foreign = self.client.get('/api/v1/shipping?type=livraison&address=Via Roma 00100 Roma')
        self.assertEqual(foreign.status_code, 400)
        paid = self.pay({
            'address': '1 quai 13001 Marseille',
            'fulfillment_type': 'livraison',
            'fulfillment_date': open_day().isoformat(),
            'fulfillment_slot': 'matin',
        })
        self.assertEqual(paid.status_code, 201, paid.get_json())
        order = paid.get_json()['order']
        self.assertEqual(order['shipping_amount'], 8.9)
        self.assertEqual(order['total_amount'], 38.89)

    def test_admin_can_restrict_delivery_departments(self):
        token = self.login('admin@florashop.com', 'admin123')
        restricted = self.client.put(
            '/api/v1/settings',
            json={'delivery_prefixes': '75,92'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(restricted.status_code, 200, restricted.get_json())
        body = restricted.get_json()
        self.assertEqual(body['delivery_prefixes'], '75,92')
        self.assertFalse(body.get('delivery_nationwide'))
        ok = self.client.get('/api/v1/shipping?type=livraison&address=12 rue des Fleurs 75001 Paris')
        self.assertEqual(ok.status_code, 200)
        outside = self.client.get('/api/v1/shipping?type=livraison&address=1 quai 13001 Marseille')
        self.assertEqual(outside.status_code, 400)
        paid = self.pay({
            'address': '1 quai 13001 Marseille',
            'fulfillment_type': 'livraison',
            'fulfillment_date': open_day().isoformat(),
            'fulfillment_slot': 'matin',
        })
        self.assertEqual(paid.status_code, 400)
        restored = self.client.put(
            '/api/v1/settings',
            json={'delivery_prefixes': 'FR'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(restored.status_code, 200, restored.get_json())
        self.assertTrue(restored.get_json().get('delivery_nationwide'))
        nationwide = self.client.get('/api/v1/shipping?type=livraison&address=1 quai 13001 Marseille')
        self.assertEqual(nationwide.status_code, 200)

    def test_closed_sunday_is_rejected(self):
        sunday = a_sunday()
        response = self.pay({
            'fulfillment_type': 'retrait',
            'fulfillment_date': sunday.isoformat(),
            'fulfillment_slot': 'matin',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('fermé', response.get_json()['error'])

    def test_promo_code_reduces_total(self):
        token = self.login('admin@florashop.com', 'admin123')
        created = self.client.post(
            '/api/v1/promos',
            json={'code': 'WELCOME10', 'percent': 10},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        quote = self.client.get('/api/v1/promo/quote?code=WELCOME10&subtotal=29.99')
        self.assertEqual(quote.status_code, 200)
        self.assertEqual(quote.get_json()['discount'], 3.0)
        paid = self.pay({'promo_code': 'WELCOME10'})
        self.assertEqual(paid.status_code, 201, paid.get_json())
        order = paid.get_json()['order']
        self.assertEqual(order['promo_code'], 'WELCOME10')
        self.assertEqual(order['discount_amount'], 3.0)
        self.assertEqual(order['total_amount'], 26.99)
        row = PromoCode.query.filter_by(code='WELCOME10').first()
        self.assertEqual(int(row.uses_count), 1)
        bogus = self.pay({'promo_code': 'NOPE'})
        self.assertEqual(bogus.status_code, 400)

    def test_contact_reply_marks_traite(self):
        created = self.client.post('/api/v1/contact', json={
            'name': 'Léa Martin',
            'email': 'lea@test.com',
            'message': 'Devis pour un mariage en juin, arche et boutonnières.',
        })
        self.assertEqual(created.status_code, 201)
        contact_id = created.get_json()['id']
        token = self.login('admin@florashop.com', 'admin123')
        replied = self.client.patch(
            f'/api/v1/contact/{contact_id}',
            json={'reply': 'Merci, nous vous rappelons demain.'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(replied.status_code, 200, replied.get_json())
        row = replied.get_json()['request']
        self.assertEqual(row['status'], 'traite')
        self.assertIn('rappelons', row['reply_text'])

    def test_product_description_roundtrip(self):
        listed = self.client.get('/api/v1/products').get_json()
        row = next(item for item in listed if item['id'] == self.product.id)
        self.assertIn('atelier', row['description'])
        token = self.login('admin@florashop.com', 'admin123')
        updated = self.client.put(
            f'/api/v1/products/{self.product.id}',
            json={'description': 'Neroli et pivoines, 12 tiges.'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()['product']['description'], 'Neroli et pivoines, 12 tiges.')

    def test_pages_expose_commerce_ui(self):
        commandes = self.client.get('/commandes.html').get_data(as_text=True)
        self.assertIn('guest-track', commandes)
        self.assertIn('/api/v1/payments/track', commandes)
        checkout = self.client.get('/checkout.html').get_data(as_text=True)
        self.assertIn('style.css', checkout)
        self.assertIn('promo-code', checkout)
        self.assertIn('/api/v1/shipping', checkout)
        self.assertIn('Livraison en France', checkout)
        self.assertIn('stripe-card-mount', checkout)
        self.assertIn('https://js.stripe.com/v3/', checkout)
        self.assertIn('create-payment-intent', checkout)
        admin = self.client.get('/admin.html').get_data(as_text=True)
        self.assertIn('shop-settings', admin)
        self.assertIn('promo-section', admin)
        self.assertIn('data-contact-send', admin)
        self.assertIn('product-description', admin)
        self.assertIn('toute la France', admin)
        self.assertIn('setting-carrier', admin)
        self.assertNotIn('setting-siren', admin)
        self.assertIn('identite.html', admin)
        self.assertIn('atelier-tabs', admin)
        self.assertIn('setting-fee-overseas', admin)
        identite = self.client.get('/identite.html').get_data(as_text=True)
        self.assertIn('setting-siren', identite)
        self.assertIn('setting-tva-rate', identite)
        self.assertIn('setting-legal-name', identite)
        self.assertIn('guardAdminPage', identite)
        self.assertNotIn('setting-carrier', identite)
        cgv = self.client.get('/cgv.html').get_data(as_text=True)
        self.assertIn('/api/v1/settings', cgv)
        self.assertIn('legal-name', cgv)
