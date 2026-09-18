from datetime import datetime, timezone
from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BaseModel(db.Model):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)