from app.extensions import db
from werkzeug.security import check_password_hash, generate_password_hash


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # Hash Werkzeug (pbkdf2:...). Les anciens comptes en clair restent lisibles via check_password().
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, raw_password):
        """Stocke un hash, jamais le mot de passe en clair."""
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """Accepte un hash moderne, ou un ancien mot de passe encore stocké en clair."""
        stored = self.password or ''
        if stored.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
            return check_password_hash(stored, raw_password)
        return stored == raw_password

    def to_dict(self):
        # Jamais de mot de passe dans le JSON envoyé au navigateur.
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin
        }
