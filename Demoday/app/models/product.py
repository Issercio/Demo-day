from .base_model import BaseModel
from sqlalchemy import Column, String, Text, Numeric, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app import db

class Product(BaseModel, db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    category_id = Column(ForeignKey('categories.id'), nullable=False)
    name = Column(String(255), nullable=False)
    price = Column(Numeric(10,2), nullable=False)
    description = Column(Text)
    image_url = Column(String(255))
    stock = Column(Integer, nullable=False, default=0)
    delivery_available = Column(Boolean, default=True)
    click_collect_available = Column(Boolean, default=True)
    
    category = relationship("Category", back_populates="products")
    reviews = relationship("Review", back_populates="product")
