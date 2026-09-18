import os
import unittest

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['STRIPE_SECRET_KEY'] = ''
os.environ['STRIPE_PUBLISHABLE_KEY'] = ''

from app import create_app, db
from app.models import User
from app.services.demo_accounts import ensure_demo_accounts, ensure_demo_catalog


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

    def test_demo_flower_catalog_is_seeded(self):
        from app.models import Category, Product
        ensure_demo_catalog()
        names = {category.name for category in Category.query.all()}
        self.assertIn('Fleurs Fraîches', names)
        self.assertGreaterEqual(Product.query.filter_by(name='Bouquet Pivoine').count(), 1)

    def test_admin_login_returns_is_admin_true(self):
        ensure_demo_accounts()
        response = self.client.post('/api/v1/auth/login', json={
            'email': 'admin@florashop.com',
            'password': 'admin123',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertTrue(payload['data']['user']['is_admin'])
        self.assertEqual(payload['data']['user']['email'], 'admin@florashop.com')

    def test_demo_seed_restores_admin_flag(self):
        ensure_demo_accounts()
        admin = User.query.filter_by(email='admin@florashop.com').first()
        admin.is_admin = False
        db.session.commit()
        ensure_demo_accounts()
        admin = User.query.filter_by(email='admin@florashop.com').first()
        self.assertTrue(admin.is_admin)

    def test_home_template_keeps_admin_nav_for_florist(self):
        from pathlib import Path
        html = Path(__file__).resolve().parents[1].joinpath('app/templates/accueil.html').read_text()
        self.assertIn('id="admin-access"', html)
        self.assertNotIn("adminAccess.style.display = 'none'", html)
        account = Path(__file__).resolve().parents[1].joinpath('app/templates/account.html').read_text()
        self.assertIn("user.is_admin ? 'admin.html'", account)

    def test_admin_session_hides_marketing_nav_and_compacts_profile(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        css = root.joinpath('app/static/css/style.css').read_text()
        js = root.joinpath('app/static/js/api.js').read_text()
        self.assertIn('body.admin-session nav li:has(a[href="evenementiel.html"])', css)
        self.assertIn('nav a#profile-link:focus', css)
        self.assertIn('profile-icon-btn', css)
        self.assertIn("classList.toggle('admin-session', isAdmin)", js)
        self.assertIn('isAdmin && !onAdminPage', js)
        self.assertIn('body.admin-page #admin-btn', css)


if __name__ == '__main__':
    unittest.main()
