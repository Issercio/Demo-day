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
    # Hash Werkzeug (pbkdf2:...). Un mot de passe encore en clair est refusé (seed démo le répare).
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # jamais admin par défaut
    failed_login_count = db.Column(db.Integer, default=0)  # CNIL : compteur d'échecs
    locked_until = db.Column(db.DateTime, nullable=True)  # None = pas de verrou
    # Comptes déjà en base / démo = vérifiés. L'inscription pose email_verified=False.
    email_verified = db.Column(db.Boolean, default=True)
    phone = db.Column(db.String(20), nullable=True)
    verify_code_hash = db.Column(db.String(255), nullable=True)
    verify_code_expires = db.Column(db.DateTime, nullable=True)
    verify_channel = db.Column(db.String(10), nullable=True)  # email | sms
    verify_purpose = db.Column(db.String(10), nullable=True)  # verify | reset
    orders = db.relationship('Order', back_populates='user', lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, raw_password):
        """Stocke un hash, jamais le mot de passe en clair."""
        self.password = generate_password_hash(raw_password)

    def has_modern_hash(self):
        return (self.password or '').startswith(MODERN_HASH_PREFIXES)  # pbkdf2/scrypt/argon2

    def check_password(self, raw_password):
        """Accepte Werkzeug ou bcrypt ($2b$). Un mot de passe encore en clair est refusé."""
        stored = self.password or ''
        if stored.startswith(MODERN_HASH_PREFIXES):
            return check_password_hash(stored, raw_password)
        if stored.startswith(BCRYPT_PREFIXES):
            try:
                import bcrypt
                return bcrypt.checkpw(raw_password.encode('utf-8'), stored.encode('utf-8'))
            except (ValueError, TypeError, Exception):
                return False
        return False

    def to_dict(self):
        # Jamais de mot de passe dans le JSON envoyé au navigateur.
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'email_verified': bool(self.email_verified),
            'phone': self.phone,
        }
