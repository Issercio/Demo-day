from flask_restx import Namespace, Resource, fields
from app.extensions import db
from app.models.category import Category

api = Namespace('categories', description='Gestion des catégories')

category_model = api.model('Category', {
    'id': fields.Integer(readOnly=True),
    'name': fields.String(required=True, description='Nom de la catégorie')
})

@api.route('')
class CategoryList(Resource):
    @api.marshal_list_with(category_model)
    def get(self):
        """Liste toutes les catégories"""
        return Category.query.all()

    @api.expect(category_model)
    def post(self):
        """Crée une nouvelle catégorie"""
        data = api.payload
        category = Category(name=data['name'])
        db.session.add(category)
        db.session.commit()
        return {'id': category.id}, 201

@api.route('/<int:category_id>')
class CategoryResource(Resource):
    @api.marshal_with(category_model)
    def get(self, category_id):
        """Affiche une catégorie"""
        return Category.query.get_or_404(category_id)

    @api.expect(category_model)
    def patch(self, category_id):
        """Modifie une catégorie"""
        category = Category.query.get_or_404(category_id)
        data = api.payload
        if 'name' in data:
            category.name = data['name']
        db.session.commit()
        return {'message': 'Category updated'}

    def delete(self, category_id):
        """Supprime une catégorie"""
        category = Category.query.get_or_404(category_id)
        db.session.delete(category)
        db.session.commit()
        return {'message': 'Category deleted'}
