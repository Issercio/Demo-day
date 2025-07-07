from flask_restx import Namespace, Resource, fields
from app.models.category import Category
from app.extensions import db

api = Namespace('categories', description='CRUD des catégories (par nom uniquement)')

# Modèle pour l'entrée (POST/PATCH)
category_input_model = api.model('CategoryInput', {
    'name': fields.String(required=True, description='Nom de la catégorie')
})

# Modèle pour la sortie (GET)
category_output_model = api.model('CategoryOutput', {
    'name': fields.String(required=True, description='Nom de la catégorie')
})

@api.route('')
class CategoryList(Resource):
    @api.marshal_list_with(category_output_model)
    def get(self):
        """Liste toutes les catégories (nom uniquement)"""
        return Category.query.all()

    @api.expect(category_input_model, validate=True)
    @api.marshal_with(category_output_model, code=201)
    def post(self):
        """Crée une nouvelle catégorie (nom uniquement)"""
        data = api.payload
        # Vérifie si la catégorie existe déjà
        if Category.query.filter_by(name=data['name']).first():
            api.abort(409, "Une catégorie avec ce nom existe déjà.")
        category = Category(name=data['name'])
        db.session.add(category)
        db.session.commit()
        return category, 201

@api.route('/<string:name>')
class CategoryResource(Resource):
    @api.marshal_with(category_output_model)
    def get(self, name):
        """Récupère une catégorie par son nom"""
        category = Category.query.filter_by(name=name).first_or_404()
        return category

    @api.expect(category_input_model, validate=True)
    @api.marshal_with(category_output_model)
    def patch(self, name):
        """Modifie le nom d'une catégorie"""
        category = Category.query.filter_by(name=name).first_or_404()
        data = api.payload
        # Vérifie si le nouveau nom existe déjà
        if 'name' in data and data['name'] != name:
            if Category.query.filter_by(name=data['name']).first():
                api.abort(409, "Une catégorie avec ce nom existe déjà.")
            category.name = data['name']
            db.session.commit()
        return category

    def delete(self, name):
        """Supprime une catégorie par son nom"""
        category = Category.query.filter_by(name=name).first_or_404()
        db.session.delete(category)
        db.session.commit()
        return {'message': 'Catégorie supprimée'}
