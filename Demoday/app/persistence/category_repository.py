from .sqlalchemy_repository import SQLAlchemyRepository
from ..models.category import Category

class CategoryRepository(SQLAlchemyRepository):
    model = Category
