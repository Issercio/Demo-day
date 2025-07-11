from flask import Blueprint, jsonify, request, current_app
from flask_cors import CORS
# CORRECTION : import direct depuis models
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

# Routes pour les catégories - CORRECTION MAJEURE
@api_bp.route('/categories', methods=['GET', 'POST'])
def categories():
    if request.method == 'POST':
        try:
            data = request.get_json()
            print(f"=== CREATION CATEGORIE ===")
            print(f"Données reçues: {data}")
            
            if not data or not data.get('name'):
                return jsonify({'error': 'Le nom de la catégorie est requis'}), 400
            
            # Vérifier si la catégorie existe déjà
            existing = Category.query.filter_by(name=data['name']).first()
            if existing:
                return jsonify({'error': 'Une catégorie avec ce nom existe déjà'}), 400
            
            category = Category(name=data['name'])
            db.session.add(category)
            db.session.flush()  # IMPORTANT: flush pour obtenir l'ID
            
            print(f"Catégorie créée avec ID: {category.id}")
            
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
            print(f"Retour API: {result}")
            return jsonify(result), 201
            
        except Exception as e:
            print(f"Erreur création catégorie: {str(e)}")
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    # GET - Liste des catégories avec VALIDATION STRICTE
    try:
        print(f"=== GET CATEGORIES ===")
        categories = Category.query.all()
        result = []
        
        for c in categories:
            # VALIDATION CRITIQUE de chaque catégorie
            if c.id is None:
                print(f"ERREUR: Catégorie '{c.name}' sans ID détectée!")
                continue  # Skip cette catégorie corrompue
                
            category_dict = {
                'id': int(c.id),
                'name': str(c.name)
            }
            print(f"Catégorie valide: {category_dict}")
            result.append(category_dict)
        
        print(f"Résultat final: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"Erreur récupération catégories: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route PUT pour catégorie - AVEC VALIDATION
@api_bp.route('/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    try:
        print(f"=== MODIFICATION CATEGORIE ===")
        print(f"ID reçu: {category_id} (type: {type(category_id)})")
        
        # VALIDATION de l'ID en entrée
        if not isinstance(category_id, int) or category_id <= 0:
            return jsonify({'error': 'ID de catégorie invalide'}), 400
        
        data = request.get_json()
        print(f"Données: {data}")
        
        if not data or not data.get('name'):
            return jsonify({'error': 'Le nom de la catégorie est requis'}), 400
        
        category = Category.query.get(category_id)
        if not category:
            print(f"Catégorie avec ID {category_id} non trouvée")
            return jsonify({'error': 'Catégorie non trouvée'}), 404
        
        # VALIDATION que la catégorie a bien un ID
        if category.id is None:
            print(f"ERREUR: Catégorie corrompue sans ID!")
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
        
        print(f"Modification réussie: {old_name} -> {category.name}")
        
        return jsonify({
            'message': 'Catégorie mise à jour avec succès',
            'category': {
                'id': int(category.id),
                'name': str(category.name)
            }
        }), 200
        
    except Exception as e:
        print(f"Erreur modification catégorie: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Route DELETE pour catégorie - AVEC VALIDATION
@api_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    try:
        print(f"=== SUPPRESSION CATEGORIE ===")
        print(f"ID reçu: {category_id} (type: {type(category_id)})")
        
        # VALIDATION de l'ID en entrée
        if not isinstance(category_id, int) or category_id <= 0:
            return jsonify({'error': 'ID de catégorie invalide'}), 400
        
        category = Category.query.get(category_id)
        if not category:
            print(f"Catégorie avec ID {category_id} non trouvée")
            return jsonify({'error': 'Catégorie non trouvée'}), 404
            
        # VALIDATION que la catégorie a bien un ID
        if category.id is None:
            print(f"ERREUR: Catégorie corrompue sans ID!")
            return jsonify({'error': 'Catégorie corrompue'}), 500
            
        print(f"Catégorie trouvée: {category.name} (ID: {category.id})")
        
        # Supprimer les produits associés
        products_deleted = Product.query.filter_by(category_id=category_id).delete()
        print(f"Produits supprimés: {products_deleted}")
        
        # Supprimer la catégorie
        category_name = category.name
        db.session.delete(category)
        db.session.commit()
        
        print(f"Suppression réussie")
        return jsonify({
            'message': f'Catégorie "{category_name}" et {products_deleted} produits supprimés avec succès'
        }), 200
        
    except Exception as e:
        print(f"Erreur suppression catégorie: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Routes pour les produits - CORRIGÉE PROPREMENT
@api_bp.route('/products', methods=['GET', 'POST'])
def products():
    if request.method == 'POST':
        try:
            data = request.get_json()
            required_fields = ['name', 'price', 'category_id']
            for field in required_fields:
                if not data or field not in data:
                    return jsonify({'error': f'Le champ {field} est requis'}), 400
            
            category = Category.query.get(int(data['category_id']))
            if not category:
                return jsonify({'error': 'Catégorie non trouvée'}), 404

            product = Product(
                name=data['name'],
                price=float(data['price']),
                category_id=int(data['category_id']),
                stock=int(data.get('stock', 0))
            )
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
            return jsonify({'error': str(e)}), 500
    
    # GET - Liste des produits PROPRE
    try:
        products = Product.query.all()
        result = []
        for p in products:
            if p.id is not None:
                result.append(p.to_dict())
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route DELETE pour produit - SIMPLIFIÉE
@api_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Produit non trouvé'}), 404
        
        product_name = product.name
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({'message': f'Produit "{product_name}" supprimé avec succès'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ENDPOINT DE DEBUG pour diagnostiquer les IDs
@api_bp.route('/debug/categories', methods=['GET'])
def debug_categories():
    try:
        categories = Category.query.all()
        debug_info = []
        
        for c in categories:
            debug_info.append({
                'raw_id': c.id,
                'id_type': type(c.id).__name__,
                'id_is_none': c.id is None,
                'name': c.name,
                'str_id': str(c.id) if c.id is not None else 'None'
            })
        
        return jsonify({
            'total_categories': len(categories),
            'debug_info': debug_info
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500