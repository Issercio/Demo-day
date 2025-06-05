from .base_model import BaseModel
from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship

class Category(BaseModel):
    __tablename__ = 'categories'
    
    name = Column(String(100), nullable=False)
    description = Column(Text)
    products = relationship("Product", back_populates="category")
