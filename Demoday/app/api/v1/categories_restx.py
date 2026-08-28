from flask_restx import Resource, fields, Namespace
from flask import request
# CORRECTION : import direct depuis models
from app.models import Category
from app import db
from sqlalchemy import text

api = Namespace('categories', description='Gestion des catégories')

# Modèle pour la documentation
category_model = api.model('Category', {
    'id': fields.Integer(required=True, description='ID de la catégorie'),
    'name': fields.String(required=True, description='Nom de la catégorie')
})

@api.route('')
class CategoryList(Resource):
    @api.marshal_list_with(category_model)
    def get(self):
        """Récupérer toutes les catégories"""
        try:
            print("=== GET CATEGORIES RESTX ===")
            categories = Category.query.all()
            result = []
            
            for cat in categories:
                if cat.id is not None:  # Validation ID
                    category_dict = {
                        'id': int(cat.id),
                        'name': str(cat.name)
                    }
                    print(f"Catégorie RESTX: {category_dict}")
                    result.append(category_dict)
            
            print(f"Total catégories RESTX: {len(result)}")
            return result
        except Exception as e:
            print(f"Erreur RESTX GET categories: {str(e)}")
            api.abort(500, f"Erreur serveur: {str(e)}")

    @api.expect(category_model)
    @api.marshal_with(category_model, code=201)
    def post(self):
        """Créer une nouvelle catégorie"""
        try:
            print("=== POST CATEGORY RESTX ===")
            data = request.json
            print(f"Données reçues RESTX: {data}")
            
            if not data or not data.get('name'):
                api.abort(400, 'Le nom de la catégorie est requis')
            
            # Vérifier unicité
            existing = Category.query.filter_by(name=data['name']).first()
            if existing:
                api.abort(400, 'Une catégorie avec ce nom existe déjà')
            
            category = Category(name=data['name'])
            db.session.add(category)
            db.session.flush()  # Obtenir l'ID
            
            if category.id is None:
                db.session.rollback()
                api.abort(500, 'Erreur génération ID')
            
            db.session.commit()
            
            result = {
                'id': int(category.id),
                'name': str(category.name)
            }
            print(f"Catégorie créée RESTX: {result}")
            return result, 201
            
        except Exception as e:
            print(f"Erreur RESTX POST: {str(e)}")
            db.session.rollback()
            api.abort(500, f"Erreur: {str(e)}")

@api.route('/<int:category_id>')
class CategoryResource(Resource):
    @api.marshal_with(category_model)
    def get(self, category_id):
        """Récupérer une catégorie par ID"""
        try:
            print(f"=== GET CATEGORY {category_id} RESTX ===")
            category = Category.query.get(category_id)
            if not category:
                api.abort(404, 'Catégorie non trouvée')
            
            if category.id is None:
                api.abort(500, 'Catégorie corrompue')
            
            result = {
                'id': int(category.id),
                'name': str(category.name)
            }
            print(f"Catégorie trouvée RESTX: {result}")
            return result
        except Exception as e:
            print(f"Erreur RESTX GET category: {str(e)}")
            api.abort(500, f"Erreur: {str(e)}")

    @api.expect(category_model)
    @api.marshal_with(category_model)
    def put(self, category_id):
        """Modifier une catégorie"""
        try:
            print(f"=== PUT CATEGORY {category_id} RESTX ===")
            data = request.json
            print(f"Nouvelles données RESTX: {data}")
            
            if not data or not data.get('name'):
                api.abort(400, 'Le nom est requis')
            
            category = Category.query.get(category_id)
            if not category:
                api.abort(404, 'Catégorie non trouvée')
            
            if category.id is None:
                api.abort(500, 'Catégorie corrompue')
            
            # Vérifier unicité
            existing = Category.query.filter(
                Category.name == data['name'], 
                Category.id != category_id
            ).first()
            if existing:
                api.abort(400, 'Nom déjà utilisé')
            
            category.name = data['name']
            db.session.commit()
            
            result = {
                'id': int(category.id),
                'name': str(category.name)
            }
            print(f"Catégorie modifiée RESTX: {result}")
            return result
            
        except Exception as e:
            print(f"Erreur RESTX PUT: {str(e)}")
            db.session.rollback()
            api.abort(500, f"Erreur: {str(e)}")

    def delete(self, category_id):
        """Supprimer une catégorie"""
        try:
            print(f"=== DELETE CATEGORY {category_id} RESTX ===")
            category = Category.query.get(category_id)
            if not category:
                api.abort(404, 'Catégorie non trouvée')
            
            if category.id is None:
                api.abort(500, 'Catégorie corrompue')
            
            # SUPPRESSION DIRECTE SQL pour éviter les problèmes avec is_on_sale
            print(f"Suppression des produits avec SQL direct...")
            result = db.session.execute(
                text("DELETE FROM products WHERE category_id = :cat_id"), 
                {"cat_id": category_id}
            )
            products_deleted = result.rowcount
            print(f"Produits supprimés via SQL: {products_deleted}")
            
            # Supprimer la catégorie
            category_name = category.name
            db.session.delete(category)
            db.session.commit()
            
            print(f"Catégorie supprimée RESTX: {category_name}")
            return {'message': f'Catégorie "{category_name}" et {products_deleted} produits supprimés'}, 200
            
        except Exception as e:
            print(f"Erreur RESTX DELETE: {str(e)}")
            db.session.rollback()
            api.abort(500, f"Erreur: {str(e)}")
