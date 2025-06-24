from flask_restx import Namespace, Resource, fields
from app.extensions import db
from app.models.review import Review

api = Namespace('reviews', description='Gestion des avis')

review_model = api.model('Review', {
    'id': fields.Integer(readOnly=True),
    'product_id': fields.Integer(required=True, description='ID du produit concerné'),
    'user_id': fields.Integer(required=True, description='ID de l\'utilisateur'),
    'rating': fields.Integer(required=True, description='Note donnée', min=1, max=5),
    'comment': fields.String(description='Commentaire')
})

@api.route('')
class ReviewList(Resource):
    @api.marshal_list_with(review_model)
    def get(self):
        """Liste tous les avis"""
        return Review.query.all()

    @api.expect(review_model)
    def post(self):
        """Crée un nouvel avis"""
        data = api.payload
        review = Review(
            product_id=data['product_id'],
            user_id=data['user_id'],
            rating=data['rating'],
            comment=data.get('comment')
        )
        db.session.add(review)
        db.session.commit()
        return {'id': review.id}, 201

@api.route('/<int:review_id>')
class ReviewResource(Resource):
    @api.marshal_with(review_model)
    def get(self, review_id):
        """Affiche un avis"""
        return Review.query.get_or_404(review_id)

    @api.expect(review_model)
    def patch(self, review_id):
        """Modifie un avis"""
        review = Review.query.get_or_404(review_id)
        data = api.payload
        for key, value in data.items():
            setattr(review, key, value)
        db.session.commit()
        return {'message': 'Review updated'}

    def delete(self, review_id):
        """Supprime un avis"""
        review = Review.query.get_or_404(review_id)
        db.session.delete(review)
        db.session.commit()
        return {'message': 'Review deleted'}
