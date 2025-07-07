from .sqlalchemy_repository import SQLAlchemyRepository
from ..models.price import Price

class PriceRepository(SQLAlchemyRepository):
    model = Price
    
    def get_current_price(self, product_id):
        return self.session.query(self.model)\
            .filter_by(product_id=product_id, is_active=True)\
            .order_by(self.model.effective_date.desc())\
            .first()
