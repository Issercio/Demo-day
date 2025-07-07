from flask import Blueprint, jsonify, request
from ...services.facade import Facade

bp = Blueprint('prices', __name__)
facade = Facade()

@bp.route('/prices', methods=['GET'])
def get_prices():
    prices = facade.prices.get_all()
    return jsonify([price.to_dict() for price in prices])

@bp.route('/products/<product_id>/price', methods=['GET'])
def get_product_price(product_id):
    price = facade.prices.get_current_price(product_id)
    return jsonify(price.to_dict() if price else {})

@bp.route('/products/<product_id>/price', methods=['POST'])
def update_product_price(product_id):
    data = request.get_json()
    new_price = facade.prices.create({
        'product_id': product_id,
        'amount': data['amount']
    })
    return jsonify(new_price.to_dict()), 201
