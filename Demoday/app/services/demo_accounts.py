"""Comptes de démo créés au démarrage s'ils n'existent pas encore."""

from app.extensions import db
from app.models.user import User

# Compte client demandé pour la démo (en plus de Marie et de l'admin).
DEMO_ACCOUNTS = (
    ('admin', 'admin@florashop.com', 'admin123', True),
    ('marie', 'marie@test.com', 'marie123', False),
    ('client', 'client@test.com', 'client123', False),
)


def ensure_demo_accounts():
    created = []
    for username, email, password, is_admin in DEMO_ACCOUNTS:
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, email=email, is_admin=is_admin, password='x')
            user.set_password(password)
            db.session.add(user)
            created.append(email)
            continue
        # Ancien compte en clair : on le re-hash sans changer le mot de passe connu.
        if user.password and not user.password.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
            if user.check_password(password):
                user.set_password(password)
    db.session.commit()
    return created
