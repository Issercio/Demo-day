from flask_restx import Resource, fields, Namespace
from flask import request
from werkzeug.exceptions import HTTPException
from app.models import Category
from app import db
from sqlalchemy import text
from app.api.v1.auth_utils import require_admin_token

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
            categories = Category.query.all()
            result = []
            
            for cat in categories:
                if cat.id is not None:  # Validation ID
                    category_dict = {
                        'id': int(cat.id),
                        'name': str(cat.name)
                    }
                    result.append(category_dict)
            
            return result
        except HTTPException:
            raise
        except Exception:
            api.abort(500, 'Erreur interne du serveur')

    @api.expect(category_model)
    @api.marshal_with(category_model, code=201)
    @require_admin_token
    def post(self):
        """Créer une nouvelle catégorie"""
        try:
            data = request.json
            
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
            return result, 201
            
        except HTTPException:
            raise
        except Exception:
            db.session.rollback()
            api.abort(500, 'Erreur interne du serveur')

@api.route('/<int:category_id>')
class CategoryResource(Resource):
    @api.marshal_with(category_model)
    def get(self, category_id):
        """Récupérer une catégorie par ID"""
        try:
            category = db.session.get(Category, category_id)
            if not category:
                api.abort(404, 'Catégorie non trouvée')
            
            if category.id is None:
                api.abort(500, 'Catégorie corrompue')
            
            result = {
                'id': int(category.id),
                'name': str(category.name)
            }
            return result
        except HTTPException:
            raise
        except Exception:
            api.abort(500, 'Erreur interne du serveur')

    @api.expect(category_model)
    @api.marshal_with(category_model)
    @require_admin_token
    def put(self, category_id):
        """Modifier une catégorie"""
        try:
            data = request.json
            
            if not data or not data.get('name'):
                api.abort(400, 'Le nom est requis')
            
            category = db.session.get(Category, category_id)
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
            return result
            
        except HTTPException:
            raise
        except Exception:
            db.session.rollback()
            api.abort(500, 'Erreur interne du serveur')

    @require_admin_token
    def delete(self, category_id):
        """Supprimer une catégorie"""
        try:
            category = db.session.get(Category, category_id)
            if not category:
                api.abort(404, 'Catégorie non trouvée')
            
            if category.id is None:
                api.abort(500, 'Catégorie corrompue')
            
            # SUPPRESSION DIRECTE SQL pour éviter les problèmes avec is_on_sale
            result = db.session.execute(
                text("DELETE FROM products WHERE category_id = :cat_id"), 
                {"cat_id": category_id}
            )
            products_deleted = result.rowcount
            
            # Supprimer la catégorie
            category_name = category.name
            db.session.delete(category)
            db.session.commit()
            
            return {'message': f'Catégorie "{category_name}" et {products_deleted} produits supprimés'}, 200
            
        except HTTPException:
            raise
        except Exception:
            db.session.rollback()
            api.abort(500, 'Erreur interne du serveur')
