from flask import Blueprint, jsonify, request
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
            'products': '/api/v1/products',
            'categories': '/api/v1/categories'
        }
    })

# Routes pour les utilisateurs
@api_bp.route('/users', methods=['GET', 'POST'])
def users():
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data or not data.get('username') or not data.get('email') or not data.get('password'):
                return jsonify({'error': 'Tous les champs sont requis'}), 400
            
            existing_user = User.query.filter_by(username=data['username']).first()
            if existing_user:
                return jsonify({'error': 'Nom d\'utilisateur déjà pris'}), 400

            existing_email = User.query.filter_by(email=data['email']).first()
            if existing_email:
                return jsonify({'error': 'Email déjà utilisé'}), 400

            user = User(
                username=data['username'],
                email=data['email'],
                password=data['password']
            )
            db.session.add(user)
            db.session.commit()
            
            # Retourner l'utilisateur créé
            return jsonify({
                'message': 'Utilisateur créé avec succès',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    # GET - Liste des utilisateurs
    try:
        users = User.query.all()
        return jsonify([{
            'id': u.id,
            'username': u.username,
            'email': u.email
        } for u in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Routes pour les produits
@api_bp.route('/products', methods=['GET', 'POST'])
def products():
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data or not data.get('name') or not data.get('price'):
                return jsonify({'error': 'Nom et prix sont requis'}), 400
            
            if not data.get('category_id'):
                return jsonify({'error': 'Veuillez sélectionner une catégorie'}), 400

            # Vérifier si la catégorie existe
            category = Category.query.get(data['category_id'])
            if not category:
                return jsonify({'error': 'Catégorie invalide'}), 400

            product = Product(
                name=data['name'],
                price=float(data['price']),
                category_id=int(data['category_id'])
            )
            db.session.add(product)
            db.session.commit()
            
            # Retourner le produit créé
            return jsonify({
                'message': 'Produit créé avec succès',
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'price': product.price,
                    'category_id': product.category_id,
                    'category_name': category.name
                }
            }), 201
        except ValueError as e:
            return jsonify({'error': 'Prix ou catégorie invalide'}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    # GET - Liste des produits
    try:
        products = Product.query.all()
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'price': p.price,
            'category_id': p.category_id
        } for p in products])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Routes pour les catégories
@api_bp.route('/categories', methods=['GET', 'POST'])
def categories():
    if request.method == 'POST':
        data = request.get_json()
        category = Category(name=data['name'])
        db.session.add(category)
        db.session.commit()
        return jsonify({'message': 'Catégorie créée avec succès', 'id': category.id}), 201
    else:
        categories = Category.query.all()
        return jsonify([{
            'id': c.id,
            'name': c.name
        } for c in categories])
