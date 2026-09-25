"""Vérification email/SMS et codes de reset.

Le hash est stocké en base ; le code en clair n’est jamais loggé ni renvoyé
hors `TESTING=True` (suite unittest).
"""

from __future__ import annotations

import os
import re
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

CODE_MINUTES = 15
CHANNELS = ('email', 'sms')
PURPOSES = ('verify', 'reset')
PHONE_RE = re.compile(r'^\+?[0-9][0-9 .\-]{7,18}$')


def ensure_verification_columns():
    inspector = inspect(db.engine)
    if 'users' not in inspector.get_table_names():
        return
    existing = {column['name'] for column in inspector.get_columns('users')}
    # Compte déjà en base = considéré vérifié (comptes de démo).
    additions = {
        'email_verified': 'BOOLEAN DEFAULT 1',
        'phone': 'VARCHAR(20)',
        'verify_code_hash': 'VARCHAR(255)',
        'verify_code_expires': 'DATETIME',
        'verify_channel': 'VARCHAR(10)',
        'verify_purpose': 'VARCHAR(10)',
    }
    for name, ddl in additions.items():
        if name not in existing:
            db.session.execute(text(f'ALTER TABLE users ADD COLUMN {name} {ddl}'))
    db.session.commit()


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def normalize_phone(value):
    raw = (value or '').strip()
    if not raw:
        return None
    if not PHONE_RE.fullmatch(raw):
        return False
    return re.sub(r'[ .\-]', '', raw)


def _plain_code():
    return f'{secrets.randbelow(1_000_000):06d}'


def issue_code(user, *, channel='email', purpose='verify'):
    """Pose un nouveau code (hash + expiry) et le « livre » (log, email optionnel, JSON démo)."""
    channel = (channel or 'email').strip().lower()
    purpose = (purpose or 'verify').strip().lower()
    if channel not in CHANNELS:
        channel = 'email'
    if purpose not in PURPOSES:
        purpose = 'verify'
    code = _plain_code()
    user.verify_code_hash = generate_password_hash(code)
    user.verify_code_expires = _now() + timedelta(minutes=CODE_MINUTES)
    user.verify_channel = channel
    user.verify_purpose = purpose
    if channel == 'sms' and user.phone:
        pass
    db.session.commit()
    _deliver(user, code, channel, purpose)
    return code


def check_code(user, code, *, purpose='verify'):
    stored = getattr(user, 'verify_code_hash', None) or ''
    expires = _aware(getattr(user, 'verify_code_expires', None))
    if not stored or not expires or expires <= _now():
        return False
    if (getattr(user, 'verify_purpose', None) or 'verify') != purpose:
        return False
    raw = (code or '').strip()
    if len(raw) != 6 or not raw.isdigit():
        return False
    return check_password_hash(stored, raw)


def clear_code(user):
    user.verify_code_hash = None
    user.verify_code_expires = None
    user.verify_channel = None
    user.verify_purpose = None


def _deliver(user, code, channel, purpose):
    from flask import current_app

    current_app.logger.info(
        'Code %s émis via %s (SMTP si MAIL_SERVER)',
        purpose,
        channel,
    )
    host = (os.environ.get('MAIL_SERVER') or '').strip()
    if channel == 'email' and host:
        try:
            msg = EmailMessage()
            msg['Subject'] = 'FloraShop — votre code'
            msg['From'] = os.environ.get('MAIL_FROM', 'noreply@localhost')
            msg['To'] = user.email
            msg.set_content(
                f'Votre code {purpose} est {code}. Il expire dans {CODE_MINUTES} minutes.'
            )
            port = int(os.environ.get('MAIL_PORT') or '25')
            with smtplib.SMTP(host, port, timeout=5) as smtp:
                smtp.send_message(msg)
        except Exception:
            current_app.logger.exception('Envoi email du code impossible — le mode démo reste valable')
