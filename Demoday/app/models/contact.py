from app.extensions import db
from app.models.base_model import utc_now

CONTACT_STATUSES = ('nouveau', 'lu', 'traite')


class ContactRequest(db.Model):
    __tablename__ = 'contact_requests'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='nouveau')
    reply_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'message': self.message,
            'status': self.status,
            'reply_text': self.reply_text,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
