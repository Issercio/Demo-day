"""Mise à jour du profil client : nom d'utilisateur, email, téléphone.

Le mot de passe ne passe pas par ici pour un self-update (POST /auth/change-password).
Un PUT JSON ne peut jamais poser is_admin.
"""

from sqlalchemy import func

from app.extensions import db
from app.models.user import User
from app.services.account_verification import normalize_phone

USERNAME_MAX = 50


def apply_profile_update(user, data, *, actor):
    """Applique les champs profil. Retourne (error_body, status) ou None si OK."""
    payload = data or {}
    next_username = user.username
    next_email = user.email
    next_phone = user.phone
    next_password = None

    if 'username' in payload:
        username = (payload.get('username') or '').strip()
        if not username or len(username) > USERNAME_MAX:
            return {'success': False, 'message': "Nom d'utilisateur invalide (1 à 50 caractères)."}, 400
        taken = User.query.filter(
            func.lower(User.username) == username.lower(),
            User.id != user.id,
        ).first()
        if taken:
            return {'success': False, 'message': "Nom d'utilisateur déjà pris"}, 409
        next_username = username

    if 'email' in payload:
        email = (payload.get('email') or '').strip()
        if not email or '@' not in email or '.' not in email.rsplit('@', 1)[-1]:
            return {'success': False, 'message': 'Email invalide'}, 400
        taken = User.query.filter(
            func.lower(User.email) == email.lower(),
            User.id != user.id,
        ).first()
        if taken:
            return {'success': False, 'message': 'Email déjà utilisé'}, 409
        next_email = email

    if 'phone' in payload:
        phone = normalize_phone(payload.get('phone'))
        if phone is False:
            return {'success': False, 'message': 'Numéro de téléphone invalide'}, 400
        next_phone = phone

    # Mot de passe : seulement un fleuriste qui édite un autre compte.
    if actor is not None and actor.is_admin and actor.id != user.id and payload.get('password'):
        password = payload.get('password') or ''
        if len(password) < 6:
            return {'success': False, 'message': 'Mot de passe trop court (6 caractères min.)'}, 400
        next_password = password

    user.username = next_username
    user.email = next_email
    user.phone = next_phone
    if next_password:
        user.set_password(next_password)

    db.session.commit()
    return None
