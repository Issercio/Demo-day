from flask import Blueprint, jsonify
from ...persistence.product_repository import ProductRepository

products_bp = Blueprint('products', __name__)
product_repository = ProductRepository()

@products_bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    try:
        product = product_repository.get_by_id(product_id)
        if not product:
            return jsonify({'error': 'Produit non trouvé'}), 404
        return jsonify({
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'category': {
                'id': product.category.id,
                'name': product.category.name
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
