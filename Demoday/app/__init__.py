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

def create_app():
    app = Flask(__name__)
    
    # Configuration CORS plus permissive
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:8000", "http://localhost:5000", "http://127.0.0.1:5000"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Configuration de la base de données et autres paramètres
    app.config.update(
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://postgres:root@localhost:5432/florashop'),
        SQLALCHEMY_TRACK_MODIFICATIONS = False,
        JSON_AS_ASCII = False,
        SECRET_KEY = os.environ.get('SECRET_KEY', 'florashop-dev-secret-key-min-32-chars'),
        ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', 'florashop_admin_2024_secure'),
        STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', ''),
        STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', ''),
        STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', ''),
    )

    # Initialisation des extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import des modèles pour l'initialisation
    from .models import Category, Product, User, Order, OrderItem

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
            from app.services.demo_accounts import ensure_demo_accounts
            ensure_runtime_schema()
            ensure_demo_accounts()
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
