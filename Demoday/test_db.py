from app import create_app, db
from app.models import User

def test_db():
    app = create_app()
    with app.app_context():
        # Check for admin user
        admin = User.query.filter_by(email='admin@florashop.com').first()
        if admin:
            print("Admin exists:")
            print(f"Username: {admin.username}")
            print(f"Email: {admin.email}")
            print(f"Is Admin: {admin.is_admin}")
            # Test password
            test_pwd = 'adminpassword'
            if admin.check_password(test_pwd):
                print("Password check successful")
            else:
                print("Password check failed")
        else:
            print("Admin user not found")

if __name__ == '__main__':
    test_db()