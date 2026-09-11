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


if __name__ == '__main__':
    unittest.main()
