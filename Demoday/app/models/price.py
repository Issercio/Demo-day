from .base_model import BaseModel
from sqlalchemy import Column, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

class Price(BaseModel):
    __tablename__ = 'prices'
    
    product_id = Column(ForeignKey('products.id'), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    effective_date = Column(DateTime, default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True)
    
    product = relationship("Product", back_populates="prices")
