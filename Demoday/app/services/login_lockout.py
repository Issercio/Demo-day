"""Verrouillage login CNIL : 5 échecs → 15 minutes sans nouvel essai."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect, text

from app.extensions import db

MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15


def ensure_login_lockout_columns():
    inspector = inspect(db.engine)
    if 'users' not in inspector.get_table_names():
        return
    existing = {column['name'] for column in inspector.get_columns('users')}
    if 'failed_login_count' not in existing:
        db.session.execute(text('ALTER TABLE users ADD COLUMN failed_login_count INTEGER DEFAULT 0'))
    if 'locked_until' not in existing:
        db.session.execute(text('ALTER TABLE users ADD COLUMN locked_until DATETIME'))
    db.session.commit()


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def lockout_error(user):
    """Message 429 si le compte est encore verrouillé, sinon None."""
    until = _aware(getattr(user, 'locked_until', None))
    if until is None or until <= _now():
        return None
    minutes = max(1, int((until - _now()).total_seconds() // 60) + 1)
    return (
        {
            'success': False,
            'message': (
                f'Compte temporairement verrouillé après {MAX_FAILED_LOGINS} essais. '
                f'Réessayez dans {minutes} min (CNIL).'
            ),
        },
        429,
    )


def record_failed_login(user):
    count = int(getattr(user, 'failed_login_count', 0) or 0) + 1
    user.failed_login_count = count
    if count >= MAX_FAILED_LOGINS:
        user.locked_until = _now() + timedelta(minutes=LOCK_MINUTES)
    db.session.commit()
    return lockout_error(user)


def clear_failed_logins(user):
    user.failed_login_count = 0
    user.locked_until = None
    db.session.commit()
