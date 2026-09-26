from flask import Blueprint, jsonify, request, render_template, abort
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from .models import Product, Category, User
from . import db
from app.api.v1.auth_utils import admin_required_response, json_internal_error, self_or_admin_required_response
from app.services.checkout_service import parse_money
from app.services.demo_accounts import normalize_hex_color, repair_shop_if_needed
from app.services.product_images import payload_from_request, save_product_image
from app.services.shop_ops import parse_stock_qty
from app.services.shop_commerce import apply_sale_fields, parse_description
from app.services.shop_themes import (
    create_custom_theme,
    delete_custom_theme,
    filter_products_by_theme,
    set_applied_theme_id,
    set_applied_vitrine,
    themes_payload,
)

api_bp = Blueprint('api', __name__)
main_bp = Blueprint('main', __name__)
CORS(api_bp, origins=[
    'http://localhost:8000',
    'http://localhost:5000',
    'http://127.0.0.1:5000',
    'http://localhost:5001',
    'http://127.0.0.1:5001',
    'http://localhost:5002',
    'http://127.0.0.1:5002',
    'https://localhost:5000',
    'https://127.0.0.1:5000',
    'https://localhost:5002',
    'https://127.0.0.1:5002',
])

TEMPLATE_PAGES = {
    'accueil.html',
    'account.html',
    'admin.html',
    'checkout.html',
    'commandes.html',
    'contact.html',
    'cgv.html',
    'entreprises.html',
    'evenementiel.html',
    'forgot-password.html',
    'panier.html',
    'payment.html',
    'portfolio.html',
    'register.html',
    'shop.html',
    'subscription.html',
    'subscription_payment.html',
    'verify-code.html',
}

PAGE_ALIASES = {
    'accueil': 'accueil.html',
    'account': 'account.html',
    'admin': 'admin.html',
    'checkout': 'checkout.html',
    'commandes': 'commandes.html',
    'contact': 'contact.html',
    'cgv': 'cgv.html',
    'entreprises': 'entreprises.html',
    'evenementiel': 'evenementiel.html',
    'forgot-password': 'forgot-password.html',
    'panier': 'panier.html',
    'payment': 'payment.html',
    'portfolio': 'portfolio.html',
    'register': 'register.html',
    'shop': 'shop.html',
    'subscription': 'subscription.html',
    'subscription-payment': 'subscription_payment.html',
    'verify-code': 'verify-code.html',
}

@api_bp.route('/')
def api_index():
    return jsonify({
        'message': 'API FloraShop v1',
        'endpoints': {
            'Catalogue': '/api/v1/products · /api/v1/categories · /api/v1/themes',
            'Auth': '/api/v1/auth/login · /register · /verify',
            'Panier': '/api/v1/cart',
            'Paiement': '/api/v1/payments/checkout',
            'Contact': '/api/v1/contact',
        }
    })

# Route GET / DELETE / PUT spécifique pour un utilisateur
@api_bp.route('/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
def get_user(user_id):
    denied = self_or_admin_required_response(user_id)  # GET/PUT/DELETE : soi-même ou fleuriste
    if denied:
        return denied

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    if request.method == 'DELETE':
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Utilisateur supprimé'}), 200

    if request.method == 'PUT':
        from app.api.v1.auth_utils import load_current_user
        from app.services.profile_service import apply_profile_update
        actor, _error = load_current_user()
        failed = apply_profile_update(user, request.get_json() or {}, actor=actor)
        if failed:
            body, status = failed
            return jsonify(body), status
        # `is_admin` du JSON est ignoré : on ne promeut personne par PUT.

    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'phone': user.phone,
        'is_admin': user.is_admin,
        'email_verified': bool(user.email_verified),
    })

# Route GET spécifique pour un produit
@api_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    try:
        product = db.session.get(Product, product_id)
        if not product:
            return jsonify({'error': 'Produit non trouvé'}), 404
            
        category = db.session.get(Category, product.category_id)
        if not category:
            return jsonify({'error': 'Catégorie non trouvée'}), 404
            
        payload = product.to_dict()
        if category and not payload.get('category'):
            payload['category'] = {'id': category.id, 'name': category.name}
        return jsonify(payload)
    except HTTPException:
        raise
    except Exception:
        return json_internal_error()

# Route GET spécifique pour une catégorie
@api_bp.route('/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    category = db.session.get(Category, category_id)
    if not category:
        return jsonify({'error': 'Catégorie non trouvée'}), 404
    return jsonify({
        'id': category.id,
        'name': category.name,
        'products': [{
            'id': product.id,
            'name': product.name
        } for product in category.products]
    })

# Routes pour les utilisateurs
@api_bp.route('/users', methods=['GET', 'POST'])
def users():
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data or not data.get('username') or not data.get('email') or not data.get('password'):
                return jsonify({'error': 'Tous les champs sont requis'}), 400

            denied = admin_required_response()
            if denied:
                return denied

            existing_user = User.query.filter_by(username=data['username']).first()
            if existing_user:
                return jsonify({'error': 'Nom d\'utilisateur déjà pris'}), 400

            existing_email = User.query.filter_by(email=data['email']).first()
            if existing_email:
                return jsonify({'error': 'Email déjà utilisé'}), 400

            user = User(
                username=data['username'],
                email=data['email'],
                password='x',  # NOT NULL ; hash posé juste après
                is_admin=False  # le JSON ne peut pas créer un fleuriste
            )
            user.set_password(data['password'])
            db.session.add(user)
            db.session.commit()
            
            return jsonify({
                'message': 'Utilisateur créé avec succès',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_admin': user.is_admin
                }
            }), 201
        except Exception as e:
            db.session.rollback()
            return json_internal_error()

    denied = admin_required_response()  # liste emails / rôles : fleuriste only
    if denied:
        return denied
    try:
        users = User.query.all()
        return jsonify([user.to_dict() for user in users])
    except Exception as e:
        return json_internal_error()

# Routes pour les catégories - CORRECTION MAJEURE
@api_bp.route('/categories', methods=['GET', 'POST'])
def categories():
    if request.method == 'POST':
        denied = admin_required_response()
        if denied:
            return denied
        try:
            data = request.get_json()
            
            if not data or not data.get('name'):
                return jsonify({'error': 'Le nom de la catégorie est requis'}), 400
            
            # Vérifier si la catégorie existe déjà
            existing = Category.query.filter_by(name=data['name']).first()
            if existing:
                return jsonify({'error': 'Une catégorie avec ce nom existe déjà'}), 400
            
            category = Category(name=data['name'])
            db.session.add(category)
            db.session.flush()  # IMPORTANT: flush pour obtenir l'ID
            
            
            # VERIFICATION CRITIQUE de l'ID
            if category.id is None:
                db.session.rollback()
                return jsonify({'error': 'Erreur lors de la génération de l\'ID'}), 500
            
            db.session.commit()
            
            # RETOUR SÉCURISÉ avec validation
            result = {
                'message': 'Catégorie créée avec succès',
                'category': {
                    'id': int(category.id),
                    'name': str(category.name)
                }
            }
            return jsonify(result), 201
            
        except Exception as e:
            db.session.rollback()
            return json_internal_error()
    
    # GET - Liste des catégories avec VALIDATION STRICTE
    try:
        categories = Category.query.all()
        result = []
        
        for c in categories:
            # VALIDATION CRITIQUE de chaque catégorie
            if c.id is None:
                continue  # Skip cette catégorie corrompue
                
            category_dict = {
                'id': int(c.id),
                'name': str(c.name)
            }
            result.append(category_dict)
        
        return jsonify(result)
        
    except Exception as e:
        return json_internal_error()

# Route PUT pour catégorie - AVEC VALIDATION
@api_bp.route('/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    denied = admin_required_response()
    if denied:
        return denied
    try:
        
        # VALIDATION de l'ID en entrée
        if not isinstance(category_id, int) or category_id <= 0:
            return jsonify({'error': 'ID de catégorie invalide'}), 400
        
        data = request.get_json()
        
        if not data or not data.get('name'):
            return jsonify({'error': 'Le nom de la catégorie est requis'}), 400
        
        category = db.session.get(Category, category_id)
        if not category:
            return jsonify({'error': 'Catégorie non trouvée'}), 404
        
        # VALIDATION que la catégorie a bien un ID
        if category.id is None:
            return jsonify({'error': 'Catégorie corrompue'}), 500
        
        # Vérifier unicité du nom
        existing = Category.query.filter(
            Category.name == data['name'], 
            Category.id != category_id
        ).first()
        if existing:
            return jsonify({'error': 'Une catégorie avec ce nom existe déjà'}), 400
            
        old_name = category.name
        category.name = data['name']
        db.session.commit()
        
        
        return jsonify({
            'message': 'Catégorie mise à jour avec succès',
            'category': {
                'id': int(category.id),
                'name': str(category.name)
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return json_internal_error()

# Route DELETE pour catégorie - AVEC VALIDATION
@api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    denied = admin_required_response()
    if denied:
        return denied
    try:
        
        # VALIDATION de l'ID en entrée
        if not isinstance(category_id, int) or category_id <= 0:
            return jsonify({'error': 'ID de catégorie invalide'}), 400
        
        category = db.session.get(Category, category_id)
        if not category:
            return jsonify({'error': 'Catégorie non trouvée'}), 404
            
        # VALIDATION que la catégorie a bien un ID
        if category.id is None:
            return jsonify({'error': 'Catégorie corrompue'}), 500
            
        
        # Supprimer les produits associés
        products_deleted = Product.query.filter_by(category_id=category_id).delete()
        
        # Supprimer la catégorie
        category_name = category.name
        db.session.delete(category)
        db.session.commit()
        
        return jsonify({
            'message': f'Catégorie "{category_name}" et {products_deleted} produits supprimés avec succès'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return json_internal_error()

# Routes pour les produits
@api_bp.route('/products', methods=['GET', 'POST'])
def products():
    if request.method == 'POST':
        # Création + photo : réservé au fleuriste (vérifié en base, pas au claim JWT).
        denied = admin_required_response()
        if denied:
            return denied
        try:
            data, image_file = payload_from_request()  # JSON ou multipart (photo produit)
            required_fields = ['name', 'price', 'category_id']
            for field in required_fields:
                if not data or data.get(field) in (None, ''):
                    return jsonify({'error': f'Le champ {field} est requis'}), 400
            
            category = db.session.get(Category, int(data['category_id']))
            if not category:
                return jsonify({'error': 'Catégorie non trouvée'}), 404

            try:
                image_url = save_product_image(image_file, data['name'])
            except ValueError as exc:
                return jsonify({'error': str(exc)}), 400

            try:
                price = parse_money(data['price'])
                stock_qty = parse_stock_qty(data.get('stock_qty'), default=12)
                description = parse_description(data.get('description'))
            except ValueError as exc:
                return jsonify({'error': str(exc)}), 400

            product = Product(
                name=data['name'],
                price=price,
                category_id=int(data['category_id']),
                color=normalize_hex_color(data.get('color') or data.get('hex_color')),
                image=image_url,
                stock_qty=stock_qty,
                description=description,
            )
            apply_sale_fields(product, data)
            db.session.add(product)
            db.session.flush()
            
            if product.id is None:
                db.session.rollback()
                return jsonify({'error': 'Erreur génération ID'}), 500
            
            db.session.commit()
            
            return jsonify({
                'message': 'Produit créé avec succès',
                'product': product.to_dict()
            }), 201
        except Exception as e:
            db.session.rollback()
            return json_internal_error()
    
    # GET : catalogue complet. La vitrine se filtre côté boutique via GET /themes.
    # ?theme=printemps,mariage = union optionnelle (admin / Swagger), pas le défaut.
    try:
        repair_shop_if_needed()
        theme_id = (request.args.get('theme') or '').strip().lower()
        products = Product.query.all()
        if theme_id:
            try:
                products = filter_products_by_theme(products, theme_id)
            except KeyError:
                return jsonify({'error': 'Thème inconnu'}), 400
        result = []
        for p in products:
            if p.id is not None:
                result.append(p.to_dict())
        return jsonify(result)
    except Exception as e:
        return json_internal_error()

# Route PUT pour produit
@api_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    denied = admin_required_response()
    if denied:
        return denied
    try:
        
        data, image_file = payload_from_request()
        
        if not data and not image_file:
            return jsonify({'error': 'Données requises'}), 400
        
        product = db.session.get(Product, int(product_id))
        if not product:
            return jsonify({'error': 'Produit non trouvé'}), 404
            
        # Mise à jour des champs fournis
        if data.get('name') not in (None, ''):
            product.name = str(data['name'])
        if data.get('price') not in (None, ''):
            try:
                product.price = parse_money(data['price'])
            except ValueError as exc:
                return jsonify({'error': str(exc)}), 400
        if data.get('category_id') not in (None, ''):
            category = db.session.get(Category, int(data['category_id']))
            if not category:
                return jsonify({'error': 'Catégorie non trouvée'}), 404
            product.category_id = int(data['category_id'])
        if data.get('stock_qty') not in (None, ''):
            try:
                product.stock_qty = parse_stock_qty(data.get('stock_qty'))
            except ValueError as exc:
                return jsonify({'error': str(exc)}), 400
        if 'description' in data:
            try:
                product.description = parse_description(data.get('description'))
            except ValueError as exc:
                return jsonify({'error': str(exc)}), 400
        try:
            apply_sale_fields(product, data)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        if 'color' in data or 'hex_color' in data:
            product.color = normalize_hex_color(data.get('color') or data.get('hex_color'))
        if image_file and image_file.filename:
            try:
                product.image = save_product_image(image_file, product.name)
            except ValueError as exc:
                return jsonify({'error': str(exc)}), 400
            
        db.session.commit()
        
        
        return jsonify({
            'message': 'Produit mis à jour avec succès',
            'product': product.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return json_internal_error()

# Route DELETE pour produit - SIMPLIFIÉE
@api_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    denied = admin_required_response()
    if denied:
        return denied
    try:
        product = db.session.get(Product, product_id)
        if not product:
            return jsonify({'error': 'Produit non trouvé'}), 404
        
        product_name = product.name
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({'message': f'Produit "{product_name}" supprimé avec succès'}), 200
    except Exception as e:
        db.session.rollback()
        return json_internal_error()

@api_bp.route('/themes', methods=['GET', 'PUT', 'POST'])
def shop_themes():
    if request.method == 'POST':
        denied = admin_required_response()  # création de thème événement, pas une saison
        if denied:
            return denied
        data = request.get_json(silent=True) or {}
        try:
            created = create_custom_theme(data)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        payload = themes_payload()
        payload['message'] = f'Thème créé : {created["label"]}.'
        return jsonify(payload), 201

    if request.method == 'PUT':
        # Seul le fleuriste change la vitrine ; le shop public relit GET ensuite.
        denied = admin_required_response()
        if denied:
            return denied
        data = request.get_json(silent=True) or {}
        try:
            if 'season' in data:
                # Combo : une saison ET/OU un thème événement.
                set_applied_vitrine(data.get('season'), data.get('theme'))
            else:
                theme_id = data.get('id')
                if theme_id is None:
                    theme_id = data.get('theme')
                set_applied_theme_id(theme_id)
        except KeyError:
            return jsonify({'error': 'Thème inconnu'}), 400
        payload = themes_payload()
        payload['message'] = (
            'Catalogue complet affiché dans le shop.'
            if not payload.get('applied_ids')
            else f'Vitrine du shop : {payload["label"]}.'
        )
        return jsonify(payload)

    try:
        repair_shop_if_needed()
        return jsonify(themes_payload())  # GET public : le shop lit la vitrine sans JWT
    except Exception:
        db.session.rollback()
        try:
            from app.services.demo_accounts import ensure_demo_catalog
            ensure_demo_catalog()
            return jsonify(themes_payload())
        except Exception:
            return json_internal_error()


@api_bp.route('/themes/<theme_id>', methods=['DELETE'])
def delete_shop_theme(theme_id):
    denied = admin_required_response()  # saison refusée plus bas ; thème événement OK
    if denied:
        return denied
    try:
        delete_custom_theme(theme_id)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except KeyError:
        return jsonify({'error': 'Thème inconnu'}), 404
    payload = themes_payload()
    payload['message'] = 'Thème supprimé.'
    return jsonify(payload)


@main_bp.route('/')
def index():
    """Page d'accueil"""
    return render_template('accueil.html')

@main_bp.before_app_request
def serve_homepage_on_root():
    """Évite le 404 RESTX sur / en servant explicitement l'accueil."""
    if request.path == '/':
        return render_template('accueil.html')

@main_bp.route('/<string:page_alias>')
def alias_page(page_alias):
    """Alias courts sans extension HTML (ex: /shop, /checkout)."""
    if page_alias.endswith('.html') and page_alias in TEMPLATE_PAGES:
        return render_template(page_alias)

    template_name = PAGE_ALIASES.get(page_alias)
    if not template_name:
        abort(404)
    return render_template(template_name)

@main_bp.route('/<path:template_name>')
def template_page(template_name):
    """Servir explicitement les pages HTML présentes dans templates/."""
    if template_name not in TEMPLATE_PAGES:
        abort(404)
    return render_template(template_name)