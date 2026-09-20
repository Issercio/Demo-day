import os
import unittest

os.environ['DATABASE_URL'] = 'sqlite://'

from app import create_app, db
from app.models import User, Category, Product


class AdminGuardTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
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
        db.session.add(Product(name='Bouquet Test', price=29.99, category_id=category.id))
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

    def test_client_cannot_create_category(self):
        token = self.login('marie@test.com', 'marie123')
        response = self.client.post(
            '/api/v1/categories',
            json={'name': 'Hack'},
            headers={'Authorization': f'Bearer {token}'}
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_create_category(self):
        response = self.client.post('/api/v1/categories', json={'name': 'Hack'})
        self.assertEqual(response.status_code, 401)

    def test_admin_can_create_category(self):
        token = self.login('admin@florashop.com', 'admin123')
        response = self.client.post(
            '/api/v1/categories',
            json={'name': 'Nouveautés'},
            headers={'Authorization': f'Bearer {token}'}
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn('category', response.get_json())

    def test_user_list_hides_from_client(self):
        token = self.login('marie@test.com', 'marie123')
        response = self.client.get('/api/v1/users', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(response.status_code, 403)

    def test_user_detail_does_not_leak_password(self):
        token = self.login('marie@test.com', 'marie123')
        response = self.client.get('/api/v1/users/2', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertNotIn('password', payload)
        self.assertEqual(payload['email'], 'marie@test.com')

    def test_shop_catalog_stays_public(self):
        response = self.client.get('/api/v1/products')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.get_json()), 1)

    def test_admin_token_header_cannot_create_user(self):
        response = self.client.post('/api/v1/users', json={
            'username': 'hacker',
            'email': 'hacker@test.com',
            'password': 'hacker123',
        }, headers={'Admin-Token': 'florashop_admin_2024_secure'})
        self.assertIn(response.status_code, (401, 403))
        self.assertIsNone(User.query.filter_by(email='hacker@test.com').first())

    def test_forged_admin_jwt_claim_is_ignored(self):
        import jwt
        from datetime import datetime, timedelta, timezone
        token = jwt.encode(
            {
                'sub': '2',
                'email': 'marie@test.com',
                'is_admin': True,
                'exp': datetime.now(timezone.utc) + timedelta(days=1),
            },
            self.app.config['SECRET_KEY'],
            algorithm='HS256',
        )
        response = self.client.post(
            '/api/v1/categories',
            json={'name': 'Forged'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_api_cannot_mint_admin_via_json_flag(self):
        token = self.login('admin@florashop.com', 'admin123')
        response = self.client.post(
            '/api/v1/users',
            json={
                'username': 'staff',
                'email': 'staff@test.com',
                'password': 'staff123',
                'is_admin': True,
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        created = User.query.filter_by(email='staff@test.com').first()
        self.assertIsNotNone(created)
        self.assertFalse(created.is_admin)

    def test_admin_put_cannot_promote_user(self):
        token = self.login('admin@florashop.com', 'admin123')
        marie = User.query.filter_by(email='marie@test.com').first()
        response = self.client.put(
            f'/api/v1/users/{marie.id}',
            json={'is_admin': True, 'username': 'marie'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        db.session.refresh(marie)
        self.assertFalse(marie.is_admin)

    def test_register_json_cannot_mint_admin(self):
        response = self.client.post('/api/v1/auth/register', json={
            'username': 'intruder',
            'email': 'intruder@test.com',
            'password': 'intruder123',
            'is_admin': True,
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        created = User.query.filter_by(email='intruder@test.com').first()
        self.assertIsNotNone(created)
        self.assertFalse(created.is_admin)

    def test_client_cannot_read_other_user(self):
        token = self.login('marie@test.com', 'marie123')
        admin = User.query.filter_by(email='admin@florashop.com').first()
        response = self.client.get(
            f'/api/v1/users/{admin.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 403)

    def test_client_cannot_delete_admin(self):
        token = self.login('marie@test.com', 'marie123')
        admin = User.query.filter_by(email='admin@florashop.com').first()
        response = self.client.delete(
            f'/api/v1/users/{admin.id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIsNotNone(db.session.get(User, admin.id))

    def test_anonymous_cannot_read_user(self):
        response = self.client.get('/api/v1/users/1')
        self.assertEqual(response.status_code, 401)

    def test_placeholder_secret_cannot_forge_admin(self):
        import jwt
        from datetime import datetime, timedelta, timezone
        admin = User.query.filter_by(email='admin@florashop.com').first()
        for leaked in (
            'florashop-dev-secret-key-min-32-chars',
            'change-me-to-a-long-random-string-min-32-chars',
        ):
            token = jwt.encode(
                {
                    'sub': str(admin.id),
                    'email': admin.email,
                    'is_admin': True,
                    'exp': datetime.now(timezone.utc) + timedelta(days=1),
                },
                leaked,
                algorithm='HS256',
            )
            response = self.client.post(
                '/api/v1/categories',
                json={'name': 'Leaked'},
                headers={'Authorization': f'Bearer {token}'},
            )
            self.assertEqual(response.status_code, 401, leaked)
        self.assertNotIn(self.app.config['SECRET_KEY'], (
            'florashop-dev-secret-key-min-32-chars',
            'change-me-to-a-long-random-string-min-32-chars',
        ))
        self.assertGreaterEqual(len(self.app.config['SECRET_KEY']), 32)

    def test_client_cannot_hit_debug_categories(self):
        token = self.login('marie@test.com', 'marie123')
        response = self.client.get(
            '/api/v1/debug/categories',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 403)

    def test_secret_key_survives_app_restart(self):
        from app import create_app
        first = create_app().config['SECRET_KEY']
        second = create_app().config['SECRET_KEY']
        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first), 32)

    def test_admin_page_stays_clean_without_popup(self):
        html = self.client.get('/admin.html').get_data(as_text=True)
        self.assertEqual(self.client.get('/admin.html').status_code, 200)
        self.assertIn('Administration du catalogue', html)
        self.assertIn('id="admin-notice"', html)
        self.assertNotIn("alert('Accès réservé aux administrateurs')", html)
        self.assertIn('ACCUEIL', html)
        self.assertIn('ÉVÈNEMENTIEL', html)
        self.assertIn('id="product-image"', html)
        self.assertIn('product-image-preview', html)
        self.assertIn('renderOrderCard', html)
        self.assertIn('Prix unit.', html)
        self.assertIn('create-theme-btn', html)
        self.assertIn('theme-create-form', html)
        self.assertIn('Payée', html)
        self.assertIn('Carte bancaire', html)
        self.assertIn('orderProductImage', html)
        self.assertIn('order-lines-wrap', html)

    def test_admin_can_create_product_with_image(self):
        from io import BytesIO
        from pathlib import Path
        from app.models import Category, Product

        token = self.login('admin@florashop.com', 'admin123')
        category = Category.query.filter_by(name='Fleurs Fraîches').first()
        photo = Path(__file__).resolve().parents[1].joinpath('app/static/img/products/rose-unique.jpg')
        response = self.client.post(
            '/api/v1/products',
            data={
                'name': 'Bouquet studio',
                'price': '21.50',
                'category_id': str(category.id),
                'color': '#d94f70',
                'image': (BytesIO(photo.read_bytes()), 'studio.jpg'),
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        payload = response.get_json()['product']
        self.assertEqual(payload['name'], 'Bouquet studio')
        self.assertTrue((payload.get('image') or '').startswith('/static/img/products/'))
        stored = Product.query.filter_by(name='Bouquet studio').first()
        self.assertIsNotNone(stored)
        saved = Path(__file__).resolve().parents[1].joinpath('app', payload['image'].lstrip('/'))
        self.assertTrue(saved.is_file())
        self.assertGreater(saved.stat().st_size, 1000)
        saved.unlink()

    def test_json_product_create_still_works(self):
        from app.models import Category
        token = self.login('admin@florashop.com', 'admin123')
        category = Category.query.filter_by(name='Fleurs Fraîches').first()
        response = self.client.post(
            '/api/v1/products',
            json={'name': 'Bouquet json', 'price': 18.5, 'category_id': category.id},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertEqual(response.get_json()['product']['name'], 'Bouquet json')

    def test_client_cannot_upload_product_image(self):
        from io import BytesIO
        from app.models import Category
        token = self.login('marie@test.com', 'marie123')
        category = Category.query.filter_by(name='Fleurs Fraîches').first()
        response = self.client.post(
            '/api/v1/products',
            data={
                'name': 'Hack photo',
                'price': '12',
                'category_id': str(category.id),
                'image': (BytesIO(b'not-an-image-but-long-enough-to-pass-size'), 'hack.jpg'),
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 403)

    def test_rejects_non_image_upload(self):
        from io import BytesIO
        from app.models import Category
        token = self.login('admin@florashop.com', 'admin123')
        category = Category.query.filter_by(name='Fleurs Fraîches').first()
        response = self.client.post(
            '/api/v1/products',
            data={
                'name': 'Fichier texte',
                'price': '12',
                'category_id': str(category.id),
                'image': (BytesIO(b'this is not an image file at all'), 'notes.txt'),
            },
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('image', (response.get_json() or {}).get('error', '').lower())


if __name__ == '__main__':
    unittest.main()
