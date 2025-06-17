import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

def setup_database():
    load_dotenv()
    
    print("🔄 Initialisation/Mise à jour de la base de données...")
    
    try:
        # Connexion à PostgreSQL
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        conn.autocommit = True
        cur = conn.cursor()

        # Sauvegarde des données existantes si nécessaire
        print("📦 Sauvegarde des données existantes...")
        try:
            cur.execute("SELECT * FROM products")
            products_backup = cur.fetchall()
            cur.execute("SELECT * FROM categories")
            categories_backup = cur.fetchall()
        except:
            products_backup = []
            categories_backup = []

        # Suppression et recréation des tables
        print("🔨 Mise à jour du schéma de la base de données...")
        with open('sql/create_tables.sql', 'r') as file:
            # Supprimer les tables existantes dans l'ordre inverse des dépendances
            cur.execute("DROP TABLE IF EXISTS products CASCADE")
            cur.execute("DROP TABLE IF EXISTS categories CASCADE")
            cur.execute("DROP TABLE IF EXISTS users CASCADE")
            # Créer les nouvelles tables
            cur.execute(file.read())

        # Réinsertion des données initiales
        print("📝 Réinsertion des données...")
        with open('sql/insert_initial_data.sql', 'r') as file:
            cur.execute(file.read())

        print("✅ Base de données mise à jour avec succès!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    setup_database()
