# app/models/review.py

from app.extensions import db

class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Relations (optionnel, selon tes besoins)
    # product = db.relationship('Product', back_populates='reviews')
    # user = db.relationship('User', back_populates='reviews')

    def __repr__(self):
        return f"<Review {self.id} - {self.rating} stars>"
