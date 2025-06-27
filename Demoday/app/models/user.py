from ..models.base_model import BaseModel
from app.extensions import db

class User(BaseModel):
    __tablename__ = 'users'

    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)  # Stocke le hash du mot de passe
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def __init__(self, username, email, password, is_admin=False):
        self.username = username
        self.email = email
        self.password = password  # Stocke toujours un hash !
        self.is_admin = is_admin

    def to_dict(self, include_password=False):
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin
        }
        if include_password:
            data['password'] = self.password
        return data
