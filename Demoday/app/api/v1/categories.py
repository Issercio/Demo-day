from flask import Blueprint, jsonify
from ...persistence.category_repository import CategoryRepository

categories_bp = Blueprint('categories', __name__)
category_repository = CategoryRepository()

@categories_bp.route('/<int:category_id>', methods=['GET'])
def get_category(category_id):
    try:
        category = category_repository.get_by_id(category_id)
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
    except Exception as e:
        return jsonify({'error': str(e)}), 500
