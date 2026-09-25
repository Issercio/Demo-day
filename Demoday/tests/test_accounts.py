import os
import tempfile
import unittest

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['STRIPE_SECRET_KEY'] = ''
os.environ['STRIPE_PUBLISHABLE_KEY'] = ''

from app import create_app, db
from app.models import User
from app.services.demo_accounts import ensure_demo_accounts, ensure_demo_catalog


class AccountsTestCase(unittest.TestCase):
    def setUp(self):
        self._theme_dir = tempfile.TemporaryDirectory()
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SHOP_THEME_PATH'] = os.path.join(self._theme_dir.name, 'shop_theme')
        self.app.config['SHOP_CUSTOM_THEMES_PATH'] = os.path.join(self._theme_dir.name, 'custom_themes.json')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self._theme_dir.cleanup()

    def test_demo_client_account_is_seeded(self):
        ensure_demo_accounts()
        client = User.query.filter_by(email='client@test.com').first()
        self.assertIsNotNone(client)
        self.assertFalse(client.is_admin)
        self.assertEqual(client.username, 'Léa Martin')
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
        self.assertFalse(payload['data']['user']['email_verified'])
        self.assertIn('demo_code', payload['data'])
        self.assertEqual(len(payload['data']['demo_code']), 6)
        user = User.query.filter_by(email='lea@test.com').first()
        self.assertTrue(user.has_modern_hash())
        self.assertNotEqual(user.password, 'lea12345')
        self.assertTrue(user.check_password('lea12345'))
        self.assertFalse(user.email_verified)

    def test_login_rejects_legacy_plaintext(self):
        user = User(username='paul', email='paul@test.com', password='paul123', is_admin=False)
        db.session.add(user)
        db.session.commit()
        response = self.client.post('/api/v1/auth/login', json={
            'email': 'paul@test.com',
            'password': 'paul123',
        })
        self.assertEqual(response.status_code, 401)
        user = db.session.get(User, user.id)
        self.assertEqual(user.password, 'paul123')

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
        self.assertEqual(user.username, 'Marie Dupont')

    def test_demo_flower_catalog_is_seeded(self):
        from app.models import Category, Product
        ensure_demo_catalog()
        names = {category.name for category in Category.query.all()}
        self.assertIn('Fleurs Fraîches', names)
        self.assertGreaterEqual(Product.query.filter_by(name='Bouquet Pivoine').count(), 1)

    def test_demo_catalog_has_colors_and_category_prices(self):
        from decimal import Decimal
        from pathlib import Path
        from app.models import Category, Product
        from app.services.demo_accounts import (
            CATEGORY_PRICE_BANDS,
            DEMO_CATALOG,
            SHOP_COLOR_PALETTE,
            ensure_demo_catalog,
        )

        ensure_demo_catalog()
        shop_names = [name for _, items in DEMO_CATALOG for name, _, _ in items]
        self.assertGreaterEqual(len(shop_names), 50)
        self.assertEqual(len(SHOP_COLOR_PALETTE), 12)

        pivoine = Product.query.filter_by(name='Bouquet Pivoine').first()
        self.assertIsNotNone(pivoine)
        self.assertEqual((pivoine.color or '').lower(), '#e8a0bf')

        payload = self.client.get('/api/v1/products').get_json()
        self.assertIsInstance(payload, list)
        colored = [item for item in payload if item.get('name') == 'Bouquet Pivoine']
        self.assertTrue(colored)
        self.assertEqual((colored[0].get('color') or '').lower(), '#e8a0bf')

        palette = {color.lower() for color in SHOP_COLOR_PALETTE}
        used = set()
        for _, items in DEMO_CATALOG:
            for _, _, color in items:
                self.assertIn(color.lower(), palette)
                used.add(color.lower())
        self.assertEqual(used, palette)

        shop_html = Path(__file__).resolve().parents[1].joinpath('app/templates/shop.html').read_text()
        for color in SHOP_COLOR_PALETTE:
            self.assertIn(color, shop_html)

        extra_categories = ("Plantes d'intérieur", 'Mariage & Événements', 'Deuil', 'Cadeaux')
        names = {category.name for category in Category.query.all()}
        for category_name in extra_categories:
            self.assertIn(category_name, names)

        for category_name, (low, high) in CATEGORY_PRICE_BANDS.items():
            category = Category.query.filter_by(name=category_name).first()
            self.assertIsNotNone(category)
            products = Product.query.filter_by(category_id=category.id).all()
            self.assertGreaterEqual(len(products), 8)
            for product in products:
                self.assertIn((product.color or '').lower(), palette)
                self.assertGreaterEqual(Decimal(str(product.price)), low)
                self.assertLessEqual(Decimal(str(product.price)), high)

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
        self.assertEqual(payload['data']['user']['username'], 'Administrateur')

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
        self.assertIn("consumeAuthNext('accueil.html')", account)
        self.assertNotIn("user.is_admin ? 'admin.html'", account)

    def test_admin_session_hides_marketing_nav_and_compacts_profile(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        css = root.joinpath('app/static/css/style.css').read_text()
        js = root.joinpath('app/static/js/api.js').read_text()
        admin_html = root.joinpath('app/templates/admin.html').read_text()
        panier_html = root.joinpath('app/templates/panier.html').read_text()
        self.assertNotIn('body.admin-page nav li:has(a[href="evenementiel.html"])', css)
        self.assertNotIn('body.admin-session nav li:has(a[href="evenementiel.html"])', css)
        self.assertIn('evenementiel.html', admin_html)
        self.assertIn('id="cart-link"', admin_html)
        self.assertIn('id="profile-link"', panier_html)
        self.assertIn('id="admin-access"', panier_html)
        self.assertIn('nav a#profile-link:focus', css)
        self.assertIn('profile-icon-btn', css)
        self.assertIn("classList.toggle('admin-session', isAdmin)", js)
        self.assertIn('isAdmin && !onAdminPage', js)
        self.assertIn('orders-link', js)
        self.assertIn('commandes.html', js)
        self.assertIn('body.admin-page #admin-btn', css)

    def test_shop_uses_wrapping_product_grid(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        html = root.joinpath('app/templates/shop.html').read_text()
        css = root.joinpath('app/static/css/style.css').read_text()
        self.assertNotIn('products-carousel', html)
        self.assertNotIn('scrollCarousel', html)
        self.assertIn('repeat(auto-fill, minmax(240px, 1fr))', html)
        self.assertIn('repeat(auto-fill, minmax(240px, 1fr))', css)
        self.assertIn('product-photo', html)
        self.assertNotIn('product-color-code', html.split('function displayProductsFromAPI')[1].split('function getProductStockStatus')[0])
        shop_layout = css.split('/* --- SHOP LAYOUT --- */', 1)[1]
        shop_block = shop_layout.split('.shop-container {', 1)[1].split('}', 1)[0]
        self.assertNotIn('overflow-x: hidden', shop_block)
        self.assertIn('padding-bottom', shop_block)
        sidebar = css.split('.sidebar-filters {', 1)[1].split('}', 1)[0]
        self.assertIn('max-height: calc(100vh - 72px)', sidebar)
        self.assertIn('height: auto', sidebar)
        self.assertFalse(
            any(line.strip() == 'height: calc(100vh - 72px);' for line in sidebar.splitlines())
        )
        products_area = css.split('.products-area {', 1)[1].split('}', 1)[0]
        self.assertIn('4.5rem', products_area)
        footer = css.split('.site-footer {', 1)[1].split('}', 1)[0]
        self.assertIn('z-index: 2', footer)
        self.assertIn('flex-shrink: 0', footer)

    def test_shop_filter_bar_stays_compact(self):
        from pathlib import Path
        html = Path(__file__).resolve().parents[1].joinpath('app/templates/shop.html').read_text()
        self.assertNotIn('id="colorPicker"', html)
        self.assertNotIn('id="addColor"', html)
        self.assertNotIn('id="applyFilters"', html)
        self.assertIn('id="resetAllFilters"', html)
        self.assertIn('id="presetColors"', html)
        self.assertIn('id="categories-filters"', html)
        self.assertIn('renderCategoryFilters', html)
        self.assertIn('Nom du bouquet', html)
        self.assertNotIn('Réinitialiser tous les filtres', html)
        css = Path(__file__).resolve().parents[1].joinpath('app/static/css/style.css').read_text()
        sidebar = css.split('.sidebar-filters {', 1)[1].split('}', 1)[0]
        self.assertIn('width: 248px', sidebar)
        self.assertNotIn('id="colorPicker"', css)

    def test_shop_catalog_has_product_photos(self):
        from pathlib import Path
        from app.models import Product
        from app.services.demo_accounts import DEMO_CATALOG, ensure_demo_catalog, product_image_path

        ensure_demo_catalog()
        photos = Path(__file__).resolve().parents[1].joinpath('app/static/img/products')
        for _, items in DEMO_CATALOG:
            for name, _, _ in items:
                image_path = product_image_path(name)
                self.assertTrue(image_path.endswith('.jpg'))
                local = photos.joinpath(Path(image_path).name)
                self.assertTrue(local.is_file(), f'missing photo for {name}')
                self.assertGreater(local.stat().st_size, 8000)

        payload = self.client.get('/api/v1/products').get_json()
        pivoine = next(item for item in payload if item.get('name') == 'Bouquet Pivoine')
        self.assertTrue((pivoine.get('image') or '').startswith('/static/img/products/'))
        stored = Product.query.filter_by(name='Bouquet Pivoine').first()
        self.assertEqual(stored.image, pivoine.get('image'))

    def test_vitrine_is_admin_only_and_updates_shop(self):
        from pathlib import Path
        home = Path(__file__).resolve().parents[1].joinpath('app/templates/accueil.html').read_text()
        admin = Path(__file__).resolve().parents[1].joinpath('app/templates/admin.html').read_text()
        shop = Path(__file__).resolve().parents[1].joinpath('app/templates/shop.html').read_text()
        self.assertNotIn('id="themes"', home)
        self.assertNotIn('setupHomeThemes', home)
        self.assertNotIn('Quel moment voulez-vous fleurir', home)
        self.assertIn('id="vitrine-section"', admin)
        self.assertIn('theme-chips-saison', admin)
        self.assertIn('theme-chips-theme', admin)
        self.assertIn('Saisons', admin)
        self.assertIn('Thèmes', admin)
        self.assertIn('setupAdminVitrine', admin)
        self.assertIn('theme-create-form', admin)
        self.assertIn('create-theme-btn', admin)
        self.assertIn('submitCustomTheme', admin)
        self.assertIn('theme-chip-x', admin)
        self.assertIn('overflow: hidden', admin.split('.theme-chip-wrap', 1)[1][:500])
        self.assertIn('theme-product-search', admin)
        self.assertIn('theme-accent-hex', admin)
        self.assertIn('can_delete', admin)
        self.assertIn('Nouveau thème', admin)
        self.assertNotIn('Les saisons restent', admin)
        self.assertNotIn('ne se créent', admin)
        self.assertNotIn('theme-kind', admin)
        self.assertIn('applyVitrine', admin)
        self.assertIn('PUT', admin)
        self.assertIn('/api/v1/themes', admin)
        self.assertIn('applyShopTheme', shop)
        self.assertIn('payload.applied_ids', shop)
        self.assertIn('toggleVitrineChip', admin)
        self.assertIn('applied_season', admin)
        self.assertIn('theme-banner', shop)
        self.assertIn('syncCategoryChecksToTheme', shop)
        self.assertNotIn('applyThemeFromUrl', shop)
        self.assertNotIn('Tous les bouquets', shop)
        self.assertNotIn('clearShopTheme', shop)
        self.assertNotIn('Boutique en construction', shop)
        self.assertIn('Chargement des bouquets', shop)
        self.assertNotIn('shop.html?theme=', home)

    def test_themes_api_and_product_filter(self):
        from datetime import date
        from app.models import Product
        from app.services.demo_accounts import DEMO_CATALOG
        from app.services.shop_themes import SHOP_THEMES, current_theme_id, product_names_for_theme

        ensure_demo_catalog()
        from app.models.shop_theme import ShopTheme, ThemeProduct, ShopVitrine
        automne = db.session.get(ShopTheme, 'automne')
        self.assertIsNotNone(automne)
        self.assertTrue(automne.links)
        self.assertTrue(all(isinstance(link.product_id, int) for link in automne.links))
        self.assertEqual(automne.links[0].product.name, automne.product_names[0])
        self.assertIsNotNone(automne.links[0].product.category_id)
        self.assertIsNotNone(db.session.get(ShopVitrine, 1))
        self.assertGreaterEqual(ThemeProduct.query.count(), 8)
        catalog_names = {name for _, items in DEMO_CATALOG for name, _, _ in items}
        for theme in SHOP_THEMES:
            for name in theme['products']:
                self.assertIn(name, catalog_names)
                self.assertIsNotNone(Product.query.filter_by(name=name).first(), name)

        self.assertEqual(current_theme_id(date(2026, 9, 18)), 'automne')
        self.assertEqual(current_theme_id(date(2026, 4, 2)), 'printemps')

        payload = self.client.get('/api/v1/themes').get_json()
        ids = [item['id'] for item in payload['themes']]
        self.assertEqual(payload['current'], current_theme_id())
        self.assertIn('printemps', ids)
        self.assertIn('mariage', ids)
        self.assertIn('saint-valentin', ids)

        autumn = self.client.get('/api/v1/products?theme=automne')
        self.assertEqual(autumn.status_code, 200)
        names = [item['name'] for item in autumn.get_json()]
        self.assertEqual(names, list(product_names_for_theme('automne')))
        self.assertNotIn('Rose unique', names)

        full = self.client.get('/api/v1/products').get_json()
        self.assertGreater(len(full), len(names))
        unknown = self.client.get('/api/v1/products?theme=halloween')
        self.assertEqual(unknown.status_code, 400)

        deuil_names = {name for name, _, _ in dict(DEMO_CATALOG)['Deuil']}
        for theme in SHOP_THEMES:
            overlap = set(theme['products']) & deuil_names
            if theme['id'] == 'hommage':
                self.assertTrue(overlap)
            else:
                self.assertFalse(overlap, theme['id'])

        kinds = {item['kind'] for item in payload['themes']}
        self.assertEqual(kinds, {'saison', 'evenement'})
        self.assertIsNone(payload['applied'])
        self.assertEqual(payload['applied_ids'], [])
        self.assertTrue(next(item for item in payload['themes'] if item['id'] == 'mariage')['can_delete'])
        self.assertFalse(next(item for item in payload['themes'] if item['id'] == 'printemps')['can_delete'])

        combo = self.client.get('/api/v1/products?theme=printemps,mariage')
        self.assertEqual(combo.status_code, 200)
        combo_names = [item['name'] for item in combo.get_json()]
        self.assertIn('Bouquet Pivoine', combo_names)
        self.assertIn('Bouquet de mariée', combo_names)
        self.assertNotIn('Gerbe de deuil', combo_names)

    def test_admin_applies_theme_and_shop_payload_updates(self):
        ensure_demo_accounts()
        ensure_demo_catalog()

        guest = self.client.put('/api/v1/themes', json={'id': 'mariage'})
        self.assertEqual(guest.status_code, 401)

        client_login = self.client.post('/api/v1/auth/login', json={
            'email': 'client@test.com',
            'password': 'client123',
        })
        self.assertEqual(client_login.status_code, 200, client_login.get_json())
        client_token = client_login.get_json()['data']['token']
        denied = self.client.put(
            '/api/v1/themes',
            json={'id': 'mariage'},
            headers={'Authorization': f'Bearer {client_token}'},
        )
        self.assertEqual(denied.status_code, 403)

        admin_login = self.client.post('/api/v1/auth/login', json={
            'email': 'admin@florashop.com',
            'password': 'admin123',
        })
        self.assertEqual(admin_login.status_code, 200, admin_login.get_json())
        admin_token = admin_login.get_json()['data']['token']
        headers = {'Authorization': f'Bearer {admin_token}'}

        unknown = self.client.put('/api/v1/themes', json={'id': 'halloween'}, headers=headers)
        self.assertEqual(unknown.status_code, 400)

        applied = self.client.put('/api/v1/themes', json={'id': 'mariage'}, headers=headers)
        self.assertEqual(applied.status_code, 200, applied.get_json())
        payload = applied.get_json()
        self.assertEqual(payload['applied'], 'mariage')
        self.assertEqual(payload['applied_theme'], 'mariage')
        self.assertIsNone(payload['applied_season'])
        self.assertEqual(payload['applied_ids'], ['mariage'])
        self.assertIn('Mariage', payload.get('message', ''))
        mariage = next(item for item in payload['themes'] if item['id'] == 'mariage')
        self.assertTrue(mariage['is_applied'])
        self.assertEqual(mariage['kind'], 'evenement')
        printemps = next(item for item in payload['themes'] if item['id'] == 'printemps')
        self.assertEqual(printemps['kind'], 'saison')
        self.assertFalse(printemps['is_applied'])

        full = self.client.get('/api/v1/products').get_json()
        self.assertGreater(len(full), len(mariage['product_names']))
        self.assertIn('Rose unique', [item['name'] for item in full])

        public = self.client.get('/api/v1/themes').get_json()
        self.assertEqual(public['applied'], 'mariage')

        combo = self.client.put(
            '/api/v1/themes',
            json={'season': 'printemps', 'theme': 'mariage'},
            headers=headers,
        )
        self.assertEqual(combo.status_code, 200, combo.get_json())
        combo_payload = combo.get_json()
        self.assertEqual(combo_payload['applied'], 'printemps,mariage')
        self.assertEqual(combo_payload['applied_ids'], ['printemps', 'mariage'])
        self.assertEqual(combo_payload['applied_season'], 'printemps')
        self.assertEqual(combo_payload['applied_theme'], 'mariage')
        self.assertIn('Printemps + Mariage', combo_payload.get('label'))
        self.assertIn('Bouquet Pivoine', combo_payload['product_names'])
        self.assertIn('Bouquet de mariée', combo_payload['product_names'])
        self.assertTrue(next(item for item in combo_payload['themes'] if item['id'] == 'printemps')['is_applied'])
        self.assertTrue(next(item for item in combo_payload['themes'] if item['id'] == 'mariage')['is_applied'])

        season = self.client.put('/api/v1/themes', json={'id': 'automne'}, headers=headers)
        self.assertEqual(season.status_code, 200)
        season_payload = season.get_json()
        self.assertEqual(season_payload['applied_season'], 'automne')
        self.assertEqual(season_payload['applied_theme'], 'mariage')
        self.assertEqual(season_payload['applied_ids'], ['automne', 'mariage'])

        cleared = self.client.put('/api/v1/themes', json={'id': 'catalogue'}, headers=headers)
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(cleared.get_json()['applied'])
        self.assertEqual(cleared.get_json()['applied_ids'], [])

    def test_admin_can_create_and_delete_custom_theme(self):
        ensure_demo_accounts()
        ensure_demo_catalog()
        admin_login = self.client.post('/api/v1/auth/login', json={
            'email': 'admin@florashop.com',
            'password': 'admin123',
        })
        headers = {'Authorization': f'Bearer {admin_login.get_json()["data"]["token"]}'}

        guest = self.client.post('/api/v1/themes', json={
            'label': 'Anniversaire',
            'kind': 'evenement',
            'products': ['Bouquet Pivoine'],
        })
        self.assertEqual(guest.status_code, 401)

        created = self.client.post('/api/v1/themes', json={
            'label': 'Anniversaire',
            'kind': 'evenement',
            'blurb': 'Pour un gâteau et un bouquet.',
            'accent': '#d94f70',
            'products': ['Bouquet Pivoine', 'Mini bouquet'],
        }, headers=headers)
        self.assertEqual(created.status_code, 201, created.get_json())
        payload = created.get_json()
        custom = next(item for item in payload['themes'] if item['label'] == 'Anniversaire')
        self.assertTrue(custom['is_custom'])
        self.assertEqual(custom['kind'], 'evenement')
        self.assertIn('Bouquet Pivoine', custom['product_names'])
        self.assertTrue(custom['id'].startswith('custom-'))

        as_season = self.client.post('/api/v1/themes', json={
            'label': 'Fausse saison',
            'kind': 'saison',
            'products': ['Bouquet Lilas'],
        }, headers=headers)
        self.assertEqual(as_season.status_code, 201, as_season.get_json())
        fake = next(item for item in as_season.get_json()['themes'] if item['label'] == 'Fausse saison')
        self.assertEqual(fake['kind'], 'evenement')
        self.assertTrue(fake['is_custom'])

        applied = self.client.put(
            '/api/v1/themes',
            json={'season': 'printemps', 'theme': 'mariage'},
            headers=headers,
        )
        self.assertEqual(applied.status_code, 200, applied.get_json())
        self.assertEqual(applied.get_json()['applied_ids'], ['printemps', 'mariage'])

        removed_builtin = self.client.delete('/api/v1/themes/mariage', headers=headers)
        self.assertEqual(removed_builtin.status_code, 200, removed_builtin.get_json())
        remaining_ids = [item['id'] for item in removed_builtin.get_json()['themes']]
        self.assertNotIn('mariage', remaining_ids)
        self.assertEqual(removed_builtin.get_json()['applied_season'], 'printemps')
        self.assertIsNone(removed_builtin.get_json()['applied_theme'])
        self.assertNotIn('mariage', [item['id'] for item in self.client.get('/api/v1/themes').get_json()['themes']])

        keep_season = self.client.delete('/api/v1/themes/printemps', headers=headers)
        self.assertEqual(keep_season.status_code, 400)
        self.assertIn('printemps', [item['id'] for item in self.client.get('/api/v1/themes').get_json()['themes']])

        applied_custom = self.client.put(
            '/api/v1/themes',
            json={'season': None, 'theme': custom['id']},
            headers=headers,
        )
        self.assertEqual(applied_custom.status_code, 200, applied_custom.get_json())
        self.assertEqual(applied_custom.get_json()['applied'], custom['id'])

        deleted = self.client.delete(f'/api/v1/themes/{custom["id"]}', headers=headers)
        self.assertEqual(deleted.status_code, 200, deleted.get_json())
        ids = [item['id'] for item in deleted.get_json()['themes']]
        self.assertNotIn(custom['id'], ids)
        self.assertIsNone(deleted.get_json()['applied'])

    def test_login_lockout_after_five_failures(self):
        user = User(username='lea-lock', email='lea-lock@test.com', password='x', is_admin=False)
        user.set_password('lea12345')
        db.session.add(user)
        db.session.commit()
        for _ in range(4):
            bad = self.client.post('/api/v1/auth/login', json={
                'email': 'lea-lock@test.com',
                'password': 'wrong',
            })
            self.assertEqual(bad.status_code, 401, bad.get_json())
        locked = self.client.post('/api/v1/auth/login', json={
            'email': 'lea-lock@test.com',
            'password': 'wrong',
        })
        self.assertEqual(locked.status_code, 429, locked.get_json())
        self.assertIn('verrouillé', locked.get_json()['message'])
        still = self.client.post('/api/v1/auth/login', json={
            'email': 'lea-lock@test.com',
            'password': 'lea12345',
        })
        self.assertEqual(still.status_code, 429)

    def test_login_success_clears_failed_attempts(self):
        user = User(username='lea-ok', email='lea-ok@test.com', password='x', is_admin=False)
        user.set_password('lea12345')
        db.session.add(user)
        db.session.commit()
        self.client.post('/api/v1/auth/login', json={'email': 'lea-ok@test.com', 'password': 'no'})
        ok = self.client.post('/api/v1/auth/login', json={'email': 'lea-ok@test.com', 'password': 'lea12345'})
        self.assertEqual(ok.status_code, 200, ok.get_json())
        stored = User.query.filter_by(email='lea-ok@test.com').first()
        self.assertEqual(stored.failed_login_count, 0)
        self.assertIsNone(stored.locked_until)

    def test_register_requires_verification_before_login(self):
        created = self.client.post('/api/v1/auth/register', json={
            'username': 'nina',
            'email': 'nina@test.com',
            'password': 'nina1234',
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        code = created.get_json()['data']['demo_code']
        blocked = self.client.post('/api/v1/auth/login', json={
            'email': 'nina@test.com',
            'password': 'nina1234',
        })
        self.assertEqual(blocked.status_code, 403, blocked.get_json())
        self.assertTrue(blocked.get_json().get('needs_verification'))
        bad = self.client.post('/api/v1/auth/verify', json={
            'email': 'nina@test.com',
            'code': '000000',
        })
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post('/api/v1/auth/verify', json={
            'email': 'nina@test.com',
            'code': code,
        })
        self.assertEqual(ok.status_code, 200, ok.get_json())
        self.assertIn('token', ok.get_json()['data'])
        self.assertTrue(ok.get_json()['data']['user']['email_verified'])
        login = self.client.post('/api/v1/auth/login', json={
            'email': 'nina@test.com',
            'password': 'nina1234',
        })
        self.assertEqual(login.status_code, 200, login.get_json())
        by_username = self.client.post('/api/v1/auth/login', json={
            'username': 'nina',
            'password': 'nina1234',
        })
        self.assertEqual(by_username.status_code, 200, by_username.get_json())
        self.assertEqual(by_username.get_json()['data']['user']['username'], 'nina')

    def test_customer_can_update_own_profile(self):
        ensure_demo_accounts()
        login = self.client.post('/api/v1/auth/login', json={
            'email': 'marie@test.com',
            'password': 'marie123',
        })
        token = login.get_json()['data']['token']
        marie = User.query.filter_by(email='marie@test.com').first()
        headers = {'Authorization': f'Bearer {token}'}

        updated = self.client.put(
            f'/api/v1/users/{marie.id}',
            json={'username': 'Marie Fleur', 'phone': '+33612345678'},
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        payload = updated.get_json()
        self.assertEqual(payload.get('username'), 'Marie Fleur')
        self.assertEqual(payload.get('phone'), '+33612345678')
        db.session.refresh(marie)
        self.assertEqual(marie.username, 'Marie Fleur')
        self.assertEqual(marie.phone, '+33612345678')
        self.assertFalse(marie.is_admin)

        stolen = self.client.put(
            f'/api/v1/users/{marie.id}',
            json={'is_admin': True, 'username': 'Marie Admin'},
            headers=headers,
        )
        self.assertEqual(stolen.status_code, 200, stolen.get_json())
        db.session.refresh(marie)
        self.assertFalse(marie.is_admin)
        self.assertEqual(marie.username, 'Marie Admin')

        lea = User.query.filter_by(email='client@test.com').first()
        clash = self.client.put(
            f'/api/v1/users/{marie.id}',
            json={'username': lea.username},
            headers=headers,
        )
        self.assertEqual(clash.status_code, 409)

        other = self.client.put(
            f'/api/v1/users/{lea.id}',
            json={'username': 'Hack'},
            headers=headers,
        )
        self.assertEqual(other.status_code, 403)
        db.session.refresh(lea)
        self.assertNotEqual(lea.username, 'Hack')

        self.client.post('/api/v1/auth/login', json={
            'username': 'Marie Admin',
            'password': 'marie123',
        })
        named = self.client.post('/api/v1/auth/login', json={
            'email': 'Marie Admin',
            'password': 'marie123',
        })
        self.assertEqual(named.status_code, 200, named.get_json())
        self.assertEqual(named.get_json()['data']['user']['username'], 'Marie Admin')

    def test_resend_code_sms_channel(self):
        created = self.client.post('/api/v1/auth/register', json={
            'username': 'sms-user',
            'email': 'sms@test.com',
            'password': 'sms12345',
            'phone': '+33612345678',
            'channel': 'sms',
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        resent = self.client.post('/api/v1/auth/resend-code', json={
            'email': 'sms@test.com',
            'channel': 'sms',
        })
        self.assertEqual(resent.status_code, 200, resent.get_json())
        self.assertEqual(resent.get_json().get('channel'), 'sms')
        self.assertEqual(len(resent.get_json()['demo_code']), 6)

    def test_customer_can_change_password(self):
        ensure_demo_accounts()
        token = self.client.post('/api/v1/auth/login', json={
            'email': 'marie@test.com',
            'password': 'marie123',
        }).get_json()['data']['token']
        denied = self.client.post('/api/v1/auth/change-password', json={
            'current_password': 'marie123',
            'new_password': 'marie999',
        })
        self.assertEqual(denied.status_code, 401)
        wrong = self.client.post(
            '/api/v1/auth/change-password',
            json={'current_password': 'nope', 'new_password': 'marie999'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(wrong.status_code, 401)
        ok = self.client.post(
            '/api/v1/auth/change-password',
            json={'current_password': 'marie123', 'new_password': 'marie999'},
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertEqual(ok.status_code, 200, ok.get_json())
        old = self.client.post('/api/v1/auth/login', json={
            'email': 'marie@test.com',
            'password': 'marie123',
        })
        self.assertEqual(old.status_code, 401)
        fresh = self.client.post('/api/v1/auth/login', json={
            'email': 'marie@test.com',
            'password': 'marie999',
        })
        self.assertEqual(fresh.status_code, 200, fresh.get_json())

    def test_forgot_password_reset_with_demo_code(self):
        ensure_demo_accounts()
        forgot = self.client.post('/api/v1/auth/forgot-password', json={
            'email': 'client@test.com',
        })
        self.assertEqual(forgot.status_code, 200, forgot.get_json())
        code = forgot.get_json()['demo_code']
        reset = self.client.post('/api/v1/auth/reset-password', json={
            'email': 'client@test.com',
            'code': code,
            'new_password': 'client999',
        })
        self.assertEqual(reset.status_code, 200, reset.get_json())
        login = self.client.post('/api/v1/auth/login', json={
            'email': 'client@test.com',
            'password': 'client999',
        })
        self.assertEqual(login.status_code, 200, login.get_json())

    def test_demo_accounts_are_verified(self):
        ensure_demo_accounts()
        marie = User.query.filter_by(email='marie@test.com').first()
        self.assertTrue(marie.email_verified)

    def test_verify_and_password_pages_are_wired(self):
        from pathlib import Path
        verify = self.client.get('/verify-code.html')
        self.assertEqual(verify.status_code, 200)
        self.assertIn('verify-form', verify.get_data(as_text=True))
        self.assertIn('verifyAccount', verify.get_data(as_text=True))
        account = self.client.get('/account.html')
        html = account.get_data(as_text=True)
        self.assertIn('password-form', html)
        self.assertIn('changePassword', html)
        self.assertIn('profile-form', html)
        self.assertIn('updateProfile', html)
        self.assertIn("Nom d'utilisateur ou email", html)
        js = Path(__file__).resolve().parents[1].joinpath('app/static/js/api.js').read_text()
        self.assertIn('this.displayName()', js)
        self.assertIn("user.username || user.email", js)
        forgot = self.client.get('/forgot-password.html')
        self.assertIn('reset-fields', forgot.get_data(as_text=True))


class HttpsRedirectTestCase(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get('FORCE_HTTPS')
        os.environ['FORCE_HTTPS'] = '1'
        os.environ['DATABASE_URL'] = 'sqlite://'
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()
        if self._prev is None:
            os.environ.pop('FORCE_HTTPS', None)
        else:
            os.environ['FORCE_HTTPS'] = self._prev

    def test_http_is_redirected_to_https(self):
        response = self.client.get('/accueil.html', base_url='http://localhost', follow_redirects=False)
        self.assertEqual(response.status_code, 301)
        self.assertTrue((response.headers.get('Location') or '').startswith('https://'))

    def test_forwarded_https_is_allowed(self):
        response = self.client.get('/accueil.html', headers={'X-Forwarded-Proto': 'https'})
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
