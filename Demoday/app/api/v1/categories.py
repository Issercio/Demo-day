from flask import Blueprint, jsonify, request
from app.models import Category
from app import db

categories_bp = Blueprint('categories_v1', __name__)

@categories_bp.route('', methods=['GET', 'POST'])
def handle_categories():
    if request.method == 'POST':
        try:
            print("=== POST CATEGORY V1 ===")
            data = request.get_json()
            print(f"Données V1: {data}")
            
            if not data or not data.get('name'):
                return jsonify({'error': 'Nom requis'}), 400
            
            category = Category(name=data['name'])
            db.session.add(category)
            db.session.flush()
            
            if category.id is None:
                db.session.rollback()
                return jsonify({'error': 'Erreur génération ID'}), 500
            
            db.session.commit()
            
            result = {
                'id': int(category.id),
                'name': str(category.name)
            }
            print(f"Catégorie créée V1: {result}")
            return jsonify(result), 201
            
        except Exception as e:
            print(f"Erreur V1 POST: {str(e)}")
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    # GET
    try:
        print("=== GET CATEGORIES V1 ===")
        categories = Category.query.all()
        result = []
        
        for cat in categories:
            if cat.id is not None:
                category_dict = {
                    'id': int(cat.id),
                    'name': str(cat.name)
                }
                print(f"Catégorie V1: {category_dict}")
                result.append(category_dict)
        
        print(f"Total V1: {len(result)}")
        return jsonify(result)
        
    except Exception as e:
        print(f"Erreur V1 GET: {str(e)}")
        return jsonify({'error': str(e)}), 500

@categories_bp.route('/<int:category_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_category(category_id):
    try:
        print(f"=== {request.method} CATEGORY {category_id} V1 ===")
        category = Category.query.get(category_id)
        
        if not category:
            return jsonify({'error': 'Catégorie non trouvée'}), 404
        
        if category.id is None:
            return jsonify({'error': 'Catégorie corrompue'}), 500
        
        if request.method == 'GET':
            result = {
                'id': int(category.id),
                'name': str(category.name)
            }
            return jsonify(result)
        
        elif request.method == 'PUT':
            data = request.get_json()
            if not data or not data.get('name'):
                return jsonify({'error': 'Nom requis'}), 400
            
            category.name = data['name']
            db.session.commit()
            
            result = {
                'id': int(category.id),
                'name': str(category.name)
            }
            return jsonify(result)
        
        elif request.method == 'DELETE':
            from app.models import Product
            Product.query.filter_by(category_id=category_id).delete()
            
            category_name = category.name
            db.session.delete(category)
            db.session.commit()
            
            return jsonify({'message': f'Catégorie "{category_name}" supprimée'}), 200
            
    except Exception as e:
        print(f"Erreur V1 {request.method}: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
