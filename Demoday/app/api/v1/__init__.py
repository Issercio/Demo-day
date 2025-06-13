from flask import Blueprint
from .users import users_bp
from .products import products_bp
from .categories import categories_bp

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

api_v1.register_blueprint(users_bp, url_prefix='/users')
api_v1.register_blueprint(products_bp, url_prefix='/products')
api_v1.register_blueprint(categories_bp, url_prefix='/categories')
