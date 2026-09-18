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


if __name__ == '__main__':
    unittest.main()
