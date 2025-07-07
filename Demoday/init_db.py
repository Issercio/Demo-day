from app import create_app, db
from app.models import User

def init_db():
    app = create_app()
    with app.app_context():
        # Drop and recreate all tables
        db.drop_all()
        db.create_all()
        
        try:
            # Create admin user
            admin = User(username='admin', email='admin@florashop.com')
            admin.password = 'adminpassword'  # Uses password property
            admin.is_admin = True
            
            db.session.add(admin)
            db.session.commit()
            print("Database initialized successfully")
            
        except Exception as e:
            print(f"Error creating admin user: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    init_db()