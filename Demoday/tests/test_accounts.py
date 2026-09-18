import os
import unittest

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['STRIPE_SECRET_KEY'] = ''
os.environ['STRIPE_PUBLISHABLE_KEY'] = ''

from app import create_app, db
from app.models import User
from app.services.demo_accounts import ensure_demo_accounts


class AccountsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_demo_client_account_is_seeded(self):
        ensure_demo_accounts()
        client = User.query.filter_by(email='client@test.com').first()
        self.assertIsNotNone(client)
        self.assertFalse(client.is_admin)
        self.assertEqual(client.username, 'client')
        self.assertTrue(client.check_password('client123'))
        self.assertNotEqual(client.password, 'client123')

    def test_register_hashes_password_and_hides_it(self):
        response = self.client.post('/api/v1/auth/register', json={
            'username': 'lea',
            'email': 'lea@test.com',
            'password': 'lea12345',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        payload = response.get_json()
        self.assertNotIn('password', payload['data']['user'])
        user = User.query.filter_by(email='lea@test.com').first()
        self.assertTrue(user.has_modern_hash())
        self.assertNotEqual(user.password, 'lea12345')
        self.assertTrue(user.check_password('lea12345'))

    def test_login_accepts_legacy_plaintext_then_rehashes(self):
        user = User(username='paul', email='paul@test.com', password='paul123', is_admin=False)
        db.session.add(user)
        db.session.commit()
        response = self.client.post('/api/v1/auth/login', json={
            'email': 'paul@test.com',
            'password': 'paul123',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        user = db.session.get(User, user.id)
        self.assertTrue(user.has_modern_hash())

    def test_login_accepts_legacy_bcrypt_hash(self):
        import bcrypt
        hashed = bcrypt.hashpw(b'marie123', bcrypt.gensalt()).decode('utf-8')
        user = User(username='marie', email='marie@test.com', password=hashed, is_admin=False)
        db.session.add(user)
        db.session.commit()
        response = self.client.post('/api/v1/auth/login', json={
            'email': 'marie@test.com',
            'password': 'marie123',
        })
        self.assertEqual(response.status_code, 200, response.get_json())

    def test_demo_seed_resets_unusable_marie_password(self):
        user = User(
            username='marie',
            email='marie@test.com',
            password='$2b$12$not-a-valid-hash-xxxxxxxxxxxx',
            is_admin=False,
        )
        db.session.add(user)
        db.session.commit()
        ensure_demo_accounts()
        user = User.query.filter_by(email='marie@test.com').first()
        self.assertTrue(user.check_password('marie123'))


if __name__ == '__main__':
    unittest.main()
