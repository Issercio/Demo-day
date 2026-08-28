from flask_restx import Resource, fields, Namespace
from flask import request
# CORRECTION : import direct depuis models
from app.models import Product, Category
from app import db

api = Namespace('products', description='Gestion des produits')

# Modèle SANS stock
product_model = api.model('Product', {
    'id': fields.Integer(required=True, description='ID du produit'),
    'name': fields.String(required=True, description='Nom du produit'),
    'price': fields.Float(required=True, description='Prix du produit'),
    'category_id': fields.Integer(description='ID de la catégorie')
})

@api.route('')
class ProductList(Resource):
    @api.marshal_list_with(product_model)
    def get(self):
        """Récupérer tous les produits"""
        try:
            print("=== GET PRODUCTS RESTX ===")
            products = Product.query.all()
            result = []
            
            for prod in products:
                if prod.id is not None:
                    product_dict = {
                        'id': int(prod.id),
                        'name': str(prod.name),
                        'price': float(prod.price),
                        'category_id': prod.category_id
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
            category = Category.query.get(int(data['category_id']))
            if not category:
                api.abort(400, 'Catégorie non trouvée')
            
            # PLUS de stock dans la création
            product = Product(
                name=data['name'],
                price=float(data['price']),
                category_id=int(data['category_id'])
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
                'category_id': product.category_id
            }
            print(f"Produit créé RESTX: {result}")
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
            product = Product.query.get(product_id)
            if not product:
                api.abort(404, 'Produit non trouvé')
            
            result = {
                'id': int(product.id),
                'name': str(product.name),
                'price': float(product.price),
                'category_id': product.category_id
            }
            return result
        except Exception as e:
            api.abort(500, f"Erreur: {str(e)}")

    @api.expect(product_model)
    @api.marshal_with(product_model)
    def put(self, product_id):
        """Modifier un produit"""
        try:
            data = request.json
            product = Product.query.get(product_id)
            if not product:
                api.abort(404, 'Produit non trouvé')
            
            if 'name' in data:
                product.name = str(data['name'])
            if 'price' in data:
                product.price = float(data['price'])
            if 'category_id' in data:
                category = Category.query.get(int(data['category_id']))
                if not category:
                    api.abort(400, 'Catégorie non trouvée')
                product.category_id = int(data['category_id'])
            
            # PLUS de stock dans les modifications
            
            db.session.commit()
            
            result = {
                'id': int(product.id),
                'name': str(product.name),
                'price': float(product.price),
                'category_id': product.category_id
            }
            return result
            
        except Exception as e:
            db.session.rollback()
            api.abort(500, f"Erreur: {str(e)}")

    def delete(self, product_id):
        """Supprimer un produit"""
        try:
            product = Product.query.get(product_id)
            if not product:
                api.abort(404, 'Produit non trouvé')
            
            product_name = product.name
            db.session.delete(product)
            db.session.commit()
            
            return {'message': f'Produit "{product_name}" supprimé'}, 200
            
        except Exception as e:
            db.session.rollback()
            api.abort(500, f"Erreur: {str(e)}")
        except Exception as e:
            db.session.rollback()
            api.abort(500, f"Erreur: {str(e)}")
        except Exception as e:
            db.session.rollback()
            api.abort(500, f"Erreur: {str(e)}")
        except Exception as e:
            db.session.rollback()
            api.abort(500, f"Erreur: {str(e)}")
