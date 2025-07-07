from flask_restx import Namespace, Resource, fields
from app.models.review import Review
from app.models.user import User
from app.extensions import db

api = Namespace('reviews', description='CRUD des avis globaux du site')

# Modèle d'entrée
review_input_model = api.model('ReviewInput', {
    'content': fields.String(required=True, description='Contenu de l\'avis'),
    'rating': fields.Integer(required=True, description='Note'),
    'user_id': fields.Integer(required=True, description='ID utilisateur')
})

# Modèle de sortie
review_output_model = api.model('ReviewOutput', {
    'content': fields.String(required=True),
    'rating': fields.Integer(required=True),
    'user': fields.String(attribute=lambda r: r.user.first_name + " " + r.user.last_name)
})

@api.route('')
class ReviewList(Resource):
    @api.marshal_list_with(review_output_model)
    def get(self):
        """Liste tous les avis globaux"""
        return Review.query.all()

    @api.expect(review_input_model, validate=True)
    @api.marshal_with(review_output_model, code=201)
    def post(self):
        """Créer un avis global"""
        data = api.payload
        user = User.query.get_or_404(data['user_id'])
        review = Review(
            content=data['content'],
            rating=data['rating'],
            user=user
        )
        db.session.add(review)
        db.session.commit()
        return review, 201

@api.route('/<int:review_id>')
class ReviewResource(Resource):
    @api.marshal_with(review_output_model)
    def get(self, review_id):
        """Récupère un avis global par son id"""
        return Review.query.get_or_404(review_id)

    @api.expect(review_input_model, validate=False)
    @api.marshal_with(review_output_model)
    def patch(self, review_id):
        """Modifie un avis global"""
        review = Review.query.get_or_404(review_id)
        data = api.payload
        if 'content' in data:
            review.content = data['content']
        if 'rating' in data:
            review.rating = data['rating']
        if 'user_id' in data:
            review.user = User.query.get_or_404(data['user_id'])
        db.session.commit()
        return review

    def delete(self, review_id):
        """Supprime un avis global"""
        review = Review.query.get_or_404(review_id)
        db.session.delete(review)
        db.session.commit()
        return {'message': 'Avis supprimé'}
