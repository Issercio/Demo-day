from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from app.extensions import db
import os
from dotenv import load_dotenv
from flask_restx import Api

# Initialisation de Migrate
migrate = Migrate()

# Chargement des variables d'environnement
load_dotenv()

PLACEHOLDER_SECRET_KEYS = {
    '',
    'change-me-to-a-long-random-string-min-32-chars',
    'florashop-dev-secret-key-min-32-chars',
}  # clés d'exemple du dépôt : un JWT signé avec elles serait forgeable


def resolve_secret_key():
    """Refuse les SECRET_KEY d'exemple du dépôt (sinon n'importe qui forge un JWT admin).

    La clé générée est écrite dans instance/secret_key : un redémarrage local
    ne déconnecte pas le fleuriste.
    """
    key = (os.environ.get('SECRET_KEY') or '').strip()
    if key not in PLACEHOLDER_SECRET_KEYS and len(key) >= 32:
        return key

    instance_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'instance'))
    secret_path = os.path.join(instance_dir, 'secret_key')
    try:
        if os.path.isfile(secret_path):
            with open(secret_path, encoding='utf-8') as handle:
                stored = handle.read().strip()
            if len(stored) >= 32:
                return stored
        os.makedirs(instance_dir, exist_ok=True)
        generated = os.urandom(32).hex()
        fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # lecture propriétaire seule
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(generated)
        return generated
    except OSError:
        return os.urandom(32).hex()


def database_uri():
    """Render / Heroku envoient parfois postgres:// ; SQLAlchemy 2 attend postgresql://."""
    raw = (os.environ.get('DATABASE_URL') or 'sqlite:///florashop.db').strip()
    if raw.startswith('postgres://'):
        return 'postgresql://' + raw[len('postgres://'):]
    return raw


def create_app():
    app = Flask(__name__)
    
    # Pages servies par Flask : same-origin. CORS sert au front local (8000 / 5000).
    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "http://localhost:8000",
                "http://localhost:5000",
                "http://127.0.0.1:5000",
                "https://localhost:5000",
                "https://127.0.0.1:5000",
            ],
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Cart-Token"]
        }
    })
    
    # Configuration de la base de données et autres paramètres
    app.config.update(
        SQLALCHEMY_DATABASE_URI = database_uri(),
        SQLALCHEMY_TRACK_MODIFICATIONS = False,
        JSON_AS_ASCII = False,
        SECRET_KEY = resolve_secret_key(),  # signature JWT + Flask
        STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', ''),
        STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', ''),
        STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', ''),
        MAX_CONTENT_LENGTH = 4 * 1024 * 1024,  # photos produits : 4 Mo max
        PREFERRED_URL_SCHEME = 'https' if os.environ.get('FORCE_HTTPS', '').lower() in ('1', 'true', 'yes') else 'http',
        PROPAGATE_EXCEPTIONS = False,
    )

    # Initialisation des extensions
    db.init_app(app)
    migrate.init_app(app, db)

    if app.config['PREFERRED_URL_SCHEME'] == 'https':
        from werkzeug.middleware.proxy_fix import ProxyFix
        from flask import request, redirect

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
        # Derrière nginx : HTTP → HTTPS. En local, lancer ./run-https.sh.

        @app.before_request
        def redirect_to_https():
            proto = request.headers.get('X-Forwarded-Proto', request.scheme)
            if proto != 'https':
                https_url = request.url.replace('http://', 'https://', 1)
                return redirect(https_url, code=301)

    # Import des modèles pour l'initialisation
    from .models import Category, Product, User, Order, OrderItem, ShopTheme, ShopVitrine, ThemeProduct, ContactRequest, Cart, ShopSettings, PromoCode

    # Swagger UI : ajout du header Authorization
    authorizations = {
        'Bearer Auth': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': "Collez ici le token retourné par /auth/login"
        }
    }

    # Initialisation de Flask-RESTX
    api = Api(
        app, 
        version='1.0', 
        title='FloraShop API', 
        doc='/api/v1',
        description='API complète pour la gestion de la boutique FloraShop',
        authorizations=authorizations,
        security='Bearer Auth'
    )

    # IMPORTANT : Enregistrer les routes directes AVANT les namespaces
    from app.routes import api_bp, main_bp
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(main_bp)  # Routes principales sans préfixe
    
    # Enregistrement du blueprint des paiements
    from app.api.v1.payments import payments_bp
    app.register_blueprint(payments_bp, url_prefix='/api/v1/payments')
    from app.api.v1.ops import ops_bp
    app.register_blueprint(ops_bp, url_prefix='/api/v1')

    # Enregistrement des namespaces
    from app.api.v1.products_restx import api as products_ns
    api.add_namespace(products_ns, path='/api/v1/products')

    from app.api.v1.users_restx import api as users_ns
    api.add_namespace(users_ns, path='/api/v1/users')

    from app.api.v1.categories_restx import api as categories_ns
    api.add_namespace(categories_ns, path='/api/v1/categories')

    from app.api.v1.auth import api as auth_ns
    api.add_namespace(auth_ns, path='/api/v1/auth')
    # Suppression de reviews_restx

    with app.app_context():
        try:
            from app.services.checkout_service import ensure_runtime_schema
            from app.services.demo_accounts import ensure_demo_accounts, ensure_demo_catalog
            from app.services.shop_ops import ensure_ops_schema
            from app.services.shop_commerce import ensure_commerce_schema
            # SQLite existante : d'abord les colonnes commerce, puis le catalogue.
            ensure_commerce_schema()
            ensure_runtime_schema()
            ensure_ops_schema()
            ensure_demo_accounts()
            ensure_demo_catalog()
        except Exception as exc:
            app.logger.warning('Initialisation schéma / comptes démo ignorée: %s', exc)
    
    return app

# ----------- Optional PostgreSQL connectivity check (not used at request time) -----------

try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    psycopg2 = None
    DictCursor = None

def test_database_connection():
    if psycopg2 is None:
        print('psycopg2 is not installed. This helper is only for PostgreSQL.')
        return False

    print(f"Tentative de connexion à la base de données:")
    print(f"Host: {os.getenv('DB_HOST')}")
    print(f"Port: {os.getenv('DB_PORT')}")
    print(f"Database: {os.getenv('DB_NAME')}")
    print(f"User: {os.getenv('DB_USER')}")

    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        cur = conn.cursor(cursor_factory=DictCursor)
        
        print("Test des requêtes sur la base de données...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cur.fetchall()
        print("\nTables trouvées:", [table[0] for table in tables])
        
        cur.execute("SELECT COUNT(*) FROM categories")
        categories_count = cur.fetchone()[0]
        print(f"\nNombre de catégories: {categories_count}")
        
        cur.execute("SELECT COUNT(*) FROM products")
        products_count = cur.fetchone()[0]
        print(f"Nombre de produits: {products_count}")
        
        cur.execute("SELECT COUNT(*) FROM users WHERE is_admin = TRUE")
        admin_count = cur.fetchone()[0]
        print(f"Nombre d'administrateurs: {admin_count}")
        
        print("\nTous les tests ont réussi!")
        cur.close()
        conn.close()
        
    except psycopg2.errors.UndefinedTable as e:
        print("\nErreur: Les tables n'existent pas encore dans la base de données.")
        print("Veuillez exécuter les migrations Flask ou créer les tables manuellement.")
        return False
    except psycopg2.OperationalError as e:
        print(f"\nErreur de connexion à la base de données:")
        print(f"Détails: {str(e)}")
        print("\nVérifiez que:")
        print("1. PostgreSQL est en cours d'exécution")
        print("2. Les informations de connexion dans le fichier .env sont correctes")
        print("3. L'utilisateur et la base de données existent dans PostgreSQL")
        return False
    except Exception as e:
        print(f"\nErreur inattendue: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    test_database_connection()
