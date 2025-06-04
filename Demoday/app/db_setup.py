import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

def setup_and_test_db():
    load_dotenv()
    
    print("🚀 Initialisation de la base de données...")
    
    try:
        # Connexion initiale à PostgreSQL
        conn = psycopg2.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Création de la base de données
        print("📦 Création de la base de données...")
        cur.execute("DROP DATABASE IF EXISTS florashop")
        cur.execute("CREATE DATABASE florashop")
        cur.close()
        conn.close()
        
        # Connexion à la nouvelle base de données
        conn = psycopg2.connect(
            dbname='florashop',
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Création des tables
        print("📋 Création des tables...")
        with open('sql/create_tables.sql', 'r') as file:
            cur.execute(file.read())
            
        # Insertion des données initiales
        print("📝 Insertion des données...")
        with open('sql/insert_initial_data.sql', 'r') as file:
            cur.execute(file.read())
            
        # Test des données
        print("\n🔍 Vérification des données:")
        cur.execute("SELECT COUNT(*) FROM categories")
        print(f"Nombre de catégories: {cur.fetchone()[0]}")
        
        cur.execute("SELECT COUNT(*) FROM products")
        print(f"Nombre de produits: {cur.fetchone()[0]}")
        
        cur.execute("SELECT COUNT(*) FROM users WHERE is_admin = TRUE")
        print(f"Nombre d'administrateurs: {cur.fetchone()[0]}")
        
        print("\n✅ Base de données initialisée avec succès!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    setup_and_test_db()
