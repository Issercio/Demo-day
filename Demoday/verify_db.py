from app import create_app, db
from app.models import User
from sqlalchemy import inspect

def verify_db():
    app = create_app()
    with app.app_context():
        # Check if tables exist
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Tables in database: {tables}")
        
        # Check for admin user
        admin = User.query.filter_by(email='admin@florashop.com').first()
        if admin:
            print("\nAdmin user exists:")
            print(f"Username: {admin.username}")
            print(f"Email: {admin.email}")
            print(f"Is Admin: {admin.is_admin}")
        else:
            print("\nCreating admin user...")
            admin = User(
                username='admin',
                email='admin@florashop.com',
                password='adminpassword',
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")

if __name__ == '__main__':
    verify_db()