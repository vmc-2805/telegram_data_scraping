from sqlalchemy import Column, Integer, String
from database import Base

class SameProduct(Base):
    __tablename__ = "same_products"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(255))
    product_description = Column(String(255))
    product_price = Column(Integer)
    channel_name = Column(String(255))
    message_id = Column(String(255))
    timestamp = Column(Integer)
    media_url = Column(String(255))
    source_type = Column(Integer)
    created_at = Column(String(255))
