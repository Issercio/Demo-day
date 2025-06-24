from flask_restx import Namespace, Resource, fields
from app.models import Product
from app.extensions import db

api = Namespace('products', description='Produits CRUD et offres spéciales')

product_model = api.model('Product', {
    'id': fields.Integer(readOnly=True),
    'name': fields.String(required=True),
    'price': fields.Float(required=True),
    'category_id': fields.Integer(required=True),
    'is_on_sale': fields.Boolean,
    'sale_price': fields.Float
})

@api.route('')
class ProductList(Resource):
    @api.marshal_list_with(product_model)
    def get(self):
        return Product.query.all()

    @api.expect(product_model, validate=True)
    def post(self):
        data = api.payload
        product = Product(
            name=data['name'],
            price=data['price'],
            category_id=data['category_id'],
            is_on_sale=data.get('is_on_sale', False),
            sale_price=data.get('sale_price')
        )
        db.session.add(product)
        db.session.commit()
        return {'message': 'Product created', 'id': product.id}, 201

@api.route('/<int:product_id>')
class ProductResource(Resource):
    @api.marshal_with(product_model)
    def get(self, product_id):
        return Product.query.get_or_404(product_id)

    @api.expect(product_model, validate=False)
    def patch(self, product_id):
        product = Product.query.get_or_404(product_id)
        data = api.payload
        for key in data:
            setattr(product, key, data[key])
        db.session.commit()
        return {'message': 'Product updated'}

    def delete(self, product_id):
        product = Product.query.get_or_404(product_id)
        db.session.delete(product)
        db.session.commit()
        return {'message': 'Product deleted'}

@api.route('/special-offers')
class SpecialOffers(Resource):
    @api.marshal_list_with(product_model)
    def get(self):
        return Product.query.filter_by(is_on_sale=True).all()
