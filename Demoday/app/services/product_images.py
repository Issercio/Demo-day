"""Photos catalogue : upload admin, nom unique, types et taille contrôlés."""

from pathlib import Path
from uuid import uuid4

from flask import current_app, request
from werkzeug.utils import secure_filename

from app.services.demo_accounts import product_slug

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_IMAGE_BYTES = 4 * 1024 * 1024


def product_images_dir():
    folder = Path(current_app.static_folder) / 'img' / 'products'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_product_image(file_storage, product_name):
    if file_storage is None or not getattr(file_storage, 'filename', None):
        return None

    filename = secure_filename(file_storage.filename or '')  # enlève ../ et caractères dangereux
    ext = Path(filename).suffix.lower()
    if ext == '.jpeg':
        ext = '.jpg'
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Format d'image non supporté (jpg, png, webp, gif).")

    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if size > MAX_IMAGE_BYTES:
        raise ValueError('Image trop lourde (max 4 Mo).')
    if size < 32:
        raise ValueError('Fichier image invalide.')

    slug = product_slug(product_name) or 'produit'
    dest_name = f'{slug}-{uuid4().hex[:8]}{ext}'  # évite d'écraser une autre photo
    dest = product_images_dir() / dest_name
    file_storage.save(str(dest))
    return f'/static/img/products/{dest_name}'


def payload_from_request():
    """JSON classique ou formulaire multipart (champ fichier `image`)."""
    content_type = request.content_type or ''
    if 'multipart/form-data' in content_type or request.files:
        form = request.form
        data = {}
        for key in ('name', 'price', 'category_id', 'color', 'hex_color'):
            if key in form:
                data[key] = form.get(key)
        if 'color' not in data and 'hex_color' in data:
            data['color'] = data.get('hex_color')
        return data, request.files.get('image')
    return request.get_json(silent=True) or {}, None
