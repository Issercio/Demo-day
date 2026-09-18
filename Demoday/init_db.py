"""Create tables and seed demo accounts (hashed passwords)."""

from app import create_app, db
from app.services.demo_accounts import ensure_demo_accounts, ensure_demo_catalog


def init_db():
    app = create_app()
    with app.app_context():
        db.create_all()
        created = ensure_demo_accounts()
        ensure_demo_catalog()
        print('Database tables are ready.')
        if created:
            print('Created demo accounts:', ', '.join(created))
        else:
            print('Demo accounts already present (passwords re-hashed if needed).')


if __name__ == '__main__':
    init_db()