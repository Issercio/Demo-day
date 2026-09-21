from app.extensions import db
from werkzeug.security import check_password_hash, generate_password_hash

# Older databases stored bcrypt $2b$... hashes.
# Werkzeug, lui, préfixe pbkdf2: / scrypt: / argon2:
MODERN_HASH_PREFIXES = ('pbkdf2:', 'scrypt:', 'argon2:')
BCRYPT_PREFIXES = ('$2a$', '$2b$', '$2y$')


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # Hash Werkzeug (pbkdf2:...). Les anciens comptes en clair restent lisibles via check_password().
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # jamais admin par défaut
    orders = db.relationship('Order', back_populates='user', lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, raw_password):
        """Stocke un hash, jamais le mot de passe en clair."""
        self.password = generate_password_hash(raw_password)

    def has_modern_hash(self):
        return (self.password or '').startswith(MODERN_HASH_PREFIXES)  # pbkdf2/scrypt/argon2

    def check_password(self, raw_password):
        """Accepte Werkzeug, bcrypt ($2b$), ou un ancien mot de passe encore en clair."""
        stored = self.password or ''
        if stored.startswith(MODERN_HASH_PREFIXES):
            return check_password_hash(stored, raw_password)
        if stored.startswith(BCRYPT_PREFIXES):
            try:
                import bcrypt
                return bcrypt.checkpw(raw_password.encode('utf-8'), stored.encode('utf-8'))
            except (ValueError, TypeError, Exception):
                return False
        return stored == raw_password  # ancien compte clair : le login migrera vers Werkzeug

    def to_dict(self):
        # Jamais de mot de passe dans le JSON envoyé au navigateur.
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin
        }
