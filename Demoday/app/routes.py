from flask import Blueprint, render_template, jsonify, request, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models import User, Product, Category
from app import db

# Blueprint definitions
frontend = Blueprint('frontend', __name__)
api = Blueprint('api', __name__, url_prefix='/api/v1')

# Frontend routes
@frontend.route('/')
def index():
    return render_template('frontend/index.html')

@frontend.route('/products')
def products_page():
    return render_template('products.html')

@frontend.route('/categories')
def categories_page():
    return render_template('categories.html')

@frontend.route('/api/docs')
def api_docs():
    return render_template('api_docs.html')

# Authentication routes
@api.route('/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        current_app.logger.info(f"Login attempt for email: {data.get('email')}")
        
        user = User.query.filter_by(email=data.get('email')).first()
        if not user:
            return jsonify({'error': 'User not found'}), 401

        if not user.check_password(data.get('password')):
            return jsonify({'error': 'Invalid password'}), 401

        token = create_access_token(identity=user.id)
        return jsonify({
            'token': token,
            'user': user.to_dict()
        })
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'An error occurred during login'}), 500

@api.route('/auth/admin-token', methods=['POST'])
def create_admin_token():
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()
    
    if user and user.check_password(data.get('password')) and user.is_admin:
        access_token = create_access_token(
            identity=user.id,
            additional_claims={'is_admin': True}
        )
        return jsonify({
            'token': access_token,
            'type': 'Bearer',
            'expires_in': 86400
        })
    return jsonify({'error': 'Invalid credentials or not admin'}), 401

# User routes
@api.route('/users', methods=['POST'])
def create_user():
    try:
        data = request.get_json()

        # Vérifie si l'email existe déjà
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 400

        # Vérifie si le username existe déjà
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already taken'}), 400

        # Crée un nouvel utilisateur avec le mot de passe hashé
        user = User(
            username=data['username'],
            email=data['email']
        )
        user.set_password(data['password'])  # Hash le mot de passe

        db.session.add(user)
        db.session.commit()

        return jsonify({
            'message': 'User created successfully',
            'user': user.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# Product routes
@api.route('/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'price': p.price,
        'category_id': p.category_id,
        'category_name': p.category.name if p.category else None
    } for p in products])

@api.route('/products', methods=['POST'])
@jwt_required()
def create_product():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    product = Product(
        name=data['name'],
        price=data['price'],
        category_id=data['category_id']
    )
    db.session.add(product)
    db.session.commit()
    return jsonify(product.to_dict()), 201

# Category routes
@api.route('/categories', methods=['GET'])
def get_categories():
    categories = Category.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name
    } for c in categories])

@api.route('/categories', methods=['POST'])
@jwt_required()
def create_category():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    category = Category(name=data['name'])
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201

# Admin verification route
@api.route('/admin/check')
@jwt_required()
def check_admin():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user or not user.is_admin:
        return jsonify({'message': 'Admin access required'}), 403
    return jsonify({'message': 'Admin access granted'})

# Error handlers
@api.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@api.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500
