import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import get_db
from models.product import Product
from models.ZeroPrice import ZeroPrice
from sqlalchemy.orm import Session

def find_zero_price_products():
    db: Session = next(get_db())

    zero_price_products = db.query(Product).filter(Product.product_price == 0.0).all()

    if not zero_price_products:
        print("✅ No products found with zero price.")
        return

    print(f"🧾 Found {len(zero_price_products)} products with zero price.\n")

    for product in zero_price_products:
        zero_entry = ZeroPrice(
            product_name=product.product_name,
            product_description=product.product_description,
            product_price=product.product_price,
            channel_name=product.channel_name,
            message_id=product.message_id,
            timestamp=product.timestamp,
            media_url=product.media_url,
            source_type=product.source_type,
            created_at=product.created_at,
        )

        existing = db.query(ZeroPrice).filter(ZeroPrice.message_id == product.message_id).first()
        if not existing:
            db.add(zero_entry)
            print(f"➕ Added: {product.product_name} | Channel: {product.channel_name}")
        else:
            print(f"⚠️ Skipped duplicate: {product.product_name} (message_id: {product.message_id})")

    db.commit()
    print("\n✅ All zero-price products have been stored in 'zero_price_products' table.")


if __name__ == "__main__":
    find_zero_price_products()
