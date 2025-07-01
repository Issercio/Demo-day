from flask_restx import Namespace, Resource, fields
from app.models.product import Product
from app.models.category import Category
from app.extensions import db

api = Namespace('products', description='Produits CRUD et offres spéciales')

# Modèle catégorie (nom uniquement)
category_model = api.model('Category', {
    'name': fields.String(description='Nom de la catégorie')
})

# Modèle entrée POST (sans is_on_sale)
product_input_model_post = api.model('ProductInputPost', {
    'name': fields.String(required=True),
    'price': fields.Float(required=True),
    'category': fields.Nested(category_model, required=True)
})

# Modèle entrée PATCH (avec is_on_sale)
product_input_model_patch = api.model('ProductInputPatch', {
    'name': fields.String(),
    'price': fields.Float(),
    'category': fields.Nested(category_model),
    'is_on_sale': fields.Boolean()
})

# Modèle sortie GET (sans id ni is_on_sale)
product_output_model = api.model('ProductOutput', {
    'name': fields.String(required=True),
    'price': fields.Float(required=True),
    'category': fields.Nested(category_model)
})

@api.route('')
class ProductList(Resource):
    @api.marshal_list_with(product_output_model)
    def get(self):
        """Liste tous les produits (sans is_on_sale)"""
        return Product.query.all()

    @api.expect(product_input_model_post, validate=True)
    @api.marshal_with(product_output_model, code=201)
    def post(self):
        """Crée un produit (sans is_on_sale dans le payload)"""
        data = api.payload
        category_name = data['category']['name']
        category = Category.query.filter_by(name=category_name).first()
        if not category:
            category = Category(name=category_name)
            db.session.add(category)
            db.session.commit()
        product = Product(
            name=data['name'],
            price=data['price'],
            category=category
        )
        db.session.add(product)
        db.session.commit()
        return product, 201

@api.route('/<string:product_name>')
class ProductResource(Resource):
    @api.marshal_with(product_output_model)
    def get(self, product_name):
        """Récupère un produit par son nom (sans is_on_sale)"""
        product = Product.query.filter_by(name=product_name).first_or_404()
        return product

    @api.expect(product_input_model_patch, validate=False)
    @api.marshal_with(product_output_model)
    def patch(self, product_name):
        """Modifie un produit (is_on_sale accepté uniquement ici)"""
        product = Product.query.filter_by(name=product_name).first_or_404()
        data = api.payload
        if 'name' in data:
            product.name = data['name']
        if 'price' in data:
            product.price = data['price']
        if 'category' in data and 'name' in data['category']:
            category = Category.query.filter_by(name=data['category']['name']).first()
            if not category:
                category = Category(name=data['category']['name'])
                db.session.add(category)
                db.session.commit()
            product.category = category
        if 'is_on_sale' in data:
            product.is_on_sale = data['is_on_sale']
        db.session.commit()
        return product

    def delete(self, product_name):
        """Supprime un produit par son nom"""
        product = Product.query.filter_by(name=product_name).first_or_404()
        db.session.delete(product)
        db.session.commit()
        return {'message': 'Product deleted'}
