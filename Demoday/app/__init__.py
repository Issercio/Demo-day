import psycopg2
from psycopg2.extras import DictCursor
import os
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

def test_database_connection():
    # Afficher les paramètres de connexion (sans le mot de passe)
    print(f"Tentative de connexion à la base de données:")
    print(f"Host: {os.getenv('DB_HOST')}")
    print(f"Port: {os.getenv('DB_PORT')}")
    print(f"Database: {os.getenv('DB_NAME')}")
    print(f"User: {os.getenv('DB_USER')}")

    try:
        # Connexion à la base de données
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        
        # Création d'un curseur
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Test des requêtes basiques
        print("Test des requêtes sur la base de données...")
        
        # Test 1: Vérification des tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cur.fetchall()
        print("\nTables trouvées:", [table[0] for table in tables])
        
        # Test 2: Vérification des catégories
        cur.execute("SELECT COUNT(*) FROM categories")
        categories_count = cur.fetchone()[0]
        print(f"\nNombre de catégories: {categories_count}")
        
        # Test 3: Vérification des produits
        cur.execute("SELECT COUNT(*) FROM products")
        products_count = cur.fetchone()[0]
        print(f"Nombre de produits: {products_count}")
        
        # Test 4: Vérification de l'admin
        cur.execute("SELECT COUNT(*) FROM users WHERE is_admin = TRUE")
        admin_count = cur.fetchone()[0]
        print(f"Nombre d'administrateurs: {admin_count}")
        
        print("\nTous les tests ont réussi!")
        
        # Fermeture des connexions
        cur.close()
        conn.close()
        
    except psycopg2.errors.UndefinedTable as e:
        print("\nErreur: Les tables n'existent pas encore dans la base de données.")
        print("Veuillez exécuter les commandes suivantes:")
        print("psql -U postgres -d florashop -f sql/create_tables.sql")
        print("psql -U postgres -d florashop -f sql/insert_initial_data.sql")
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
