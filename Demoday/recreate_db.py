import os
import sys
sys.path.append('/root/Demo-day-1/Demoday')

from app import create_app, db
from app.models import User, Category, Product

def recreate_database():
    app = create_app()
    
    with app.app_context():
        print("Suppression de toutes les tables...")
        db.drop_all()
        
        print("Création des nouvelles tables...")
        db.create_all()
        
        print("Insertion de l'utilisateur admin...")
        admin = User(
            username='admin',
            email='admin@florashop.com',
            password='$2b$12$tXuY6/3rkTWjgGqW0QTQzqu/p7Zv4iLF0YLcLIQEHgGOXXIRMbmml.',
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        
        print("✅ Base de données recréée avec succès!")
        print("✅ Admin créé: admin@florashop.com / admin123")

if __name__ == "__main__":
    recreate_database()
