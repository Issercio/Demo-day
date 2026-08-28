from .sqlalchemy_repository import SQLAlchemyRepository
from ..models import Product

class ProductRepository(SQLAlchemyRepository):
    model = Product
