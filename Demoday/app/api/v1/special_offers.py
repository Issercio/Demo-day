from flask import Blueprint, jsonify
from app.models import Product

special_offers_bp = Blueprint('special_offers', __name__)

@special_offers_bp.route('/special-offers', methods=['GET'])
def get_special_offers():
    offers = Product.query.filter_by(is_on_sale=True).all()
    result = [
        {
            'id': p.id,
            'name': p.name,
            'original_price': p.price,
            'sale_price': p.sale_price
        }
        for p in offers
    ]
    return jsonify(result), 200