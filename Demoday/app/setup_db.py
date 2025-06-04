import os
import psycopg2
from dotenv import load_dotenv

def setup_database():
    load_dotenv()
    
    print("🔄 Initialisation de la base de données...")
    
    try:
        # Connexion à la base de données
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Lecture et exécution du script de création des tables
        print("📊 Création des tables...")
        with open('sql/create_tables.sql', 'r') as file:
            cur.execute(file.read())
        
        # Lecture et exécution du script d'insertion des données
        print("📝 Insertion des données initiales...")
        with open('sql/insert_initial_data.sql', 'r') as file:
            cur.execute(file.read())
            
        print("✅ Base de données initialisée avec succès!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    setup_database()
