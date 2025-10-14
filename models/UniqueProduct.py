from sqlalchemy import Column, Integer, String, DECIMAL, Text, BigInteger, DateTime
from database import Base


class UniqueProduct(Base):
    __tablename__ = "unique_products"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    product_name = Column(String(500))
    product_description = Column(Text)
    product_price = Column(DECIMAL(10, 2))
    channel_name = Column(String(255))
    message_id = Column(BigInteger)
    timestamp = Column(DateTime)
    media_url = Column(Text)
    source_type = Column(String(50))
    created_at = Column(DateTime)
