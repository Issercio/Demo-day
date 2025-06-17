from ..persistence import (
    UserRepository,
    ProductRepository,
    CategoryRepository,
    ReviewRepository,
    PriceRepository
)

class Facade:
    def __init__(self):
        self.users = UserRepository()
        self.products = ProductRepository()
        self.categories = CategoryRepository()
        self.reviews = ReviewRepository()
        self.prices = PriceRepository()
