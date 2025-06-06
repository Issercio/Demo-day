from flask import Blueprint, jsonify
from .models import Product, Category

api_bp = Blueprint('api', __name__)

@api_bp.route('/')
def api_index():
    return jsonify({
        'message': 'API FloraShop v1',
        'endpoints': {
            'products': '/api/v1/products',
            'categories': '/api/v1/categories'
        }
    })

@api_bp.route('/products')
def get_products():
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'price': p.price,
        'category_id': p.category_id
    } for p in products])

@api_bp.route('/categories')
def get_categories():
    categories = Category.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name
    } for c in categories])
