from flask import Flask, redirect
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
            "origins": ["http://localhost:8000", "http://localhost:5000"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Configuration de la base de données et autres paramètres
    app.config.update(
        SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:root@localhost:5432/florashop',
        SQLALCHEMY_TRACK_MODIFICATIONS = False,
        JSON_AS_ASCII = False,
        SECRET_KEY = 'dev_secret_key_123',  # Clé pour JWT
        ADMIN_TOKEN = 'florashop_admin_2024_secure'
    )

    # Initialisation des extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import des modèles pour l'initialisation
    from app.models import Category, Product, User  # Suppression de Review et Price

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
    
    # Redirection de la racine vers Swagger UI
    @app.route('/')
    def index():
        return redirect('/api/v1')
    
    return app

# ----------- Fonction de test de la base de données (optionnelle) -----------

import psycopg2
from psycopg2.extras import DictCursor

def test_database_connection():
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
if __name__ == "__main__":
    test_database_connection()
