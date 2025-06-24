from flask import Blueprint, jsonify, request, current_app
from flask_cors import CORS
from .models import Product, Category, User
from . import db

api_bp = Blueprint('api', __name__)
CORS(api_bp)

@api_bp.route('/')
def api_index():
    return jsonify({
        'message': 'API FloraShop v1',
        'endpoints': {
            'Test POST': {
                'Test création utilisateur': {
                    'url': '/api/v1/users',
                    'method': 'POST',
                    'body': {
                        'username': 'string',
                        'email': 'string',
                        'password': 'string'
                    }
                },
                'Test création produit': {
                    'url': '/api/v1/products',
                    'method': 'POST',
                    'body': {
                        'name': 'string',
                        'price': 'number',
                        'category_id': 'number'
                    }
                },
                'Test création catégorie': {
                    'url': '/api/v1/categories',
                    'method': 'POST',
                    'body': {
                        'name': 'string'
                    }
                }
            },
            'Test GET': {
                'Test récupération utilisateur par ID': '/api/v1/users/1',
                'Test récupération produit par ID': '/api/v1/products/1',
                'Test récupération catégorie par ID': '/api/v1/categories/1',
                'Test récupération de tous les utilisateurs': '/api/v1/users'
            }
        }
    })

# Route GET spécifique pour un utilisateur
@api_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_admin': user.is_admin,
        'password': user.password
    })

# Route GET spécifique pour un produit
@api_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Produit non trouvé'}), 404
            
        category = Category.query.get(product.category_id)
        if not category:
            return jsonify({'error': 'Catégorie non trouvée'}), 404
            
        return jsonify({
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'category': {
                'id': category.id,
                'name': category.name
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route GET spécifique pour une catégorie
@api_bp.route('/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    category = Category.query.get(category_id)
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
            
            # Vérification du token admin
            admin_token = request.headers.get('Admin-Token')
            is_admin = admin_token == current_app.config['ADMIN_TOKEN']

            existing_user = User.query.filter_by(username=data['username']).first()
            if existing_user:
                return jsonify({'error': 'Nom d\'utilisateur déjà pris'}), 400

            existing_email = User.query.filter_by(email=data['email']).first()
            if existing_email:
                return jsonify({'error': 'Email déjà utilisé'}), 400

            user = User(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                is_admin=is_admin  # Définir is_admin en fonction du token
            )
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
            return jsonify({'error': str(e)}), 500

    try:
        users = User.query.all()
        return jsonify([user.to_dict() for user in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Routes pour les produits
@api_bp.route('/products', methods=['GET', 'POST'])
def products():
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data or not data.get('name') or not data.get('price') or not data.get('category_id'):
                return jsonify({'error': 'Tous les champs sont requis'}), 400
            
            category = Category.query.get(data['category_id'])
            if not category:
                return jsonify({'error': 'Catégorie non trouvée'}), 404

            product = Product(
                name=data['name'],
                price=data['price'],
                category_id=data['category_id']
            )
            db.session.add(product)
            db.session.commit()
            
            return jsonify({
                'message': 'Produit créé avec succès',
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'price': product.price,
                    'category_id': product.category_id
                }
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    try:
        products = Product.query.all()
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'price': p.price,
            'category': {
                'id': p.category_id,
                'name': Category.query.get(p.category_id).name if p.category_id else None
            }
        } for p in products])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Routes pour les catégories
@api_bp.route('/categories', methods=['GET', 'POST'])
def categories():
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data or not data.get('name'):
                return jsonify({'error': 'Le nom de la catégorie est requis'}), 400
            
            category = Category(name=data['name'])
            db.session.add(category)
            db.session.commit()
            
            return jsonify({
                'message': 'Catégorie créée avec succès',
                'category': {
                    'id': category.id,
                    'name': category.name
                }
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    # GET - Liste des catégories
    categories = Category.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name
    } for c in categories])

# Route DELETE pour utilisateur
@api_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': 'Utilisateur supprimé avec succès'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Route DELETE pour produit
@api_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Produit non trouvé'}), 404
        db.session.delete(product)
        db.session.commit()
        return jsonify({'message': 'Produit supprimé avec succès'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Route DELETE pour catégorie
@api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    try:
        category = Category.query.get(category_id)
        if not category:
            return jsonify({'error': 'Catégorie non trouvée'}), 404
        # Supprimer d'abord tous les produits de la catégorie
        Product.query.filter_by(category_id=category_id).delete()
        db.session.delete(category)
        db.session.commit()
        return jsonify({'message': 'Catégorie et ses produits supprimés avec succès'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500