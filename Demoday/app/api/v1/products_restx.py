from flask_restx import Resource, fields, Namespace
from flask import request
# CORRECTION : import direct depuis models
from app.models import Product, Category
from app import db
from app.api.v1.auth_utils import require_admin_token
from app.services.checkout_service import parse_money

api = Namespace('products', description='Gestion des produits')

# Modèle SANS stock
product_model = api.model('Product', {
    'id': fields.Integer(required=True, description='ID du produit'),
    'name': fields.String(required=True, description='Nom du produit'),
    'price': fields.Float(required=True, description='Prix du produit'),
    'category_id': fields.Integer(description='ID de la catégorie'),
    'color': fields.String(description='Code couleur hexadécimal du produit'),
})

@api.route('')
class ProductList(Resource):
    @api.marshal_list_with(product_model)
    def get(self):
        """Récupérer tous les produits"""
        try:
            print("=== GET PRODUCTS RESTX ===")
            products = Product.query.all()  # catalogue complet, sans filtre vitrine (le shop filtre côté client)
            result = []
            
            for prod in products:
                if prod.id is not None:
                    product_dict = {
                        'id': int(prod.id),
                        'name': str(prod.name),
                        'price': float(prod.price),
                        'category_id': prod.category_id,
                        'color': prod.color,
                    }
                    print(f"Produit RESTX: {product_dict}")
                    result.append(product_dict)
            
            print(f"Total produits RESTX: {len(result)}")
            return result
        except Exception as e:
            print(f"Erreur RESTX GET products: {str(e)}")
            api.abort(500, f"Erreur serveur: {str(e)}")

    @api.expect(product_model)
    @api.marshal_with(product_model, code=201)
    @require_admin_token
    def post(self):
        """Créer un nouveau produit"""
        try:
            print("=== POST PRODUCT RESTX ===")
            data = request.json
            print(f"Données reçues RESTX: {data}")
            
            required_fields = ['name', 'price', 'category_id']
            for field in required_fields:
                if not data or field not in data:
                    api.abort(400, f'Le champ {field} est requis')
            
            # Vérifier que la catégorie existe
            category = db.session.get(Category, int(data['category_id']))
            if not category:
                api.abort(400, 'Catégorie non trouvée')
            
            try:
                price = parse_money(data['price'])
            except ValueError as exc:
                api.abort(400, str(exc))

            product = Product(
                name=data['name'],
                price=price,
                category_id=int(data['category_id']),
                color=(data.get('color') or data.get('hex_color') or None),
            )
            db.session.add(product)
            db.session.flush()
            
            if product.id is None:
                db.session.rollback()
                api.abort(500, 'Erreur génération ID')
            
            db.session.commit()
            
            result = {
                'id': int(product.id),
                'name': str(product.name),
                'price': float(product.price),
                'category_id': product.category_id,
                'color': product.color,
            }
            return result, 201
            
        except Exception as e:
            print(f"Erreur RESTX POST product: {str(e)}")
            db.session.rollback()
            api.abort(500, f"Erreur: {str(e)}")

@api.route('/<int:product_id>')
class ProductResource(Resource):
    @api.marshal_with(product_model)
    def get(self, product_id):
        """Récupérer un produit par ID"""
        try:
            product = db.session.get(Product, product_id)
            if not product:
                api.abort(404, 'Produit non trouvé')
            
            result = {
                'id': int(product.id),
                'name': str(product.name),
                'price': float(product.price),
                'category_id': product.category_id,
                'color': product.color,
            }
            return result
        except Exception as e:
            api.abort(500, f"Erreur: {str(e)}")

    @api.expect(product_model)
    @api.marshal_with(product_model)
    @require_admin_token
    def put(self, product_id):
        """Modifier un produit"""
        try:
            data = request.json
            product = db.session.get(Product, product_id)
            if not product:
                api.abort(404, 'Produit non trouvé')
            
            if 'name' in data:
                product.name = str(data['name'])
            if 'price' in data:
                try:
                    product.price = parse_money(data['price'])
                except ValueError as exc:
                    api.abort(400, str(exc))
            if 'category_id' in data:
                category = db.session.get(Category, int(data['category_id']))
                if not category:
                    api.abort(400, 'Catégorie non trouvée')
                product.category_id = int(data['category_id'])
            if 'color' in data or 'hex_color' in data:
                product.color = data.get('color') or data.get('hex_color') or None
            
            # PLUS de stock dans les modifications
            
            db.session.commit()
            
            result = {
                'id': int(product.id),
                'name': str(product.name),
                'price': float(product.price),
                'category_id': product.category_id,
                'color': product.color,
            }
            return result
            
        except Exception as e:
            db.session.rollback()
            api.abort(500, f"Erreur: {str(e)}")

    @require_admin_token
    def delete(self, product_id):
        """Supprimer un produit"""
        try:
            product = db.session.get(Product, product_id)
            if not product:
                api.abort(404, 'Produit non trouvé')
            
            product_name = product.name
            db.session.delete(product)
            db.session.commit()
            
            return {'message': f'Produit "{product_name}" supprimé'}, 200
            
        except Exception as e:
            db.session.rollback()
            api.abort(500, f"Erreur: {str(e)}")
