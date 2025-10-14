import sys
import os

# Add project root to sys.path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import func
from PIL import Image
import imagehash

from database import get_db
from models.product import Product
from models.SameProduct import SameProduct


def find_and_store_same_products():
    """Detect products with duplicate names or duplicate images and store them in same_products table."""
    db: Session = next(get_db())

    all_products_count = db.query(Product).count()
    print(f"Found {all_products_count} products")

    duplicate_names = [
        name[0]
        for name in db.query(Product.product_name)
                      .group_by(Product.product_name)
                      .having(func.count(Product.product_name) > 1)
                      .all()
    ]
    same_name_products = db.query(Product).filter(Product.product_name.in_(duplicate_names)).all()
    print(f"Found {len(same_name_products)} products with duplicate names")

    products_with_images = db.query(Product).filter(Product.media_url.isnot(None)).all()
    image_hash_map = {}
    duplicate_image_ids = set()

    for product in products_with_images:
        image_path = product.media_url
        if not image_path or not os.path.isfile(os.path.normpath(image_path)):
            continue

        try:
            img = Image.open(os.path.normpath(image_path)).convert("L")
            img_hash = imagehash.phash(img)

            if img_hash in image_hash_map:
                # Add both the first occurrence and current product IDs
                duplicate_image_ids.add(image_hash_map[img_hash])
                duplicate_image_ids.add(product.id)
            else:
                image_hash_map[img_hash] = product.id

        except Exception as e:
            print(f"Error processing image {image_path}: {e}")
            continue

    same_image_products = db.query(Product).filter(Product.id.in_(duplicate_image_ids)).all()
    print(f"Found {len(same_image_products)} products with duplicate images")

    all_same_products = {p.id: p for p in same_name_products + same_image_products}.values()
    print(f"Total duplicates to store: {len(all_same_products)}")

    db.query(SameProduct).delete()
    db.commit()

    for prod in all_same_products:
        new_entry = SameProduct(
            id=prod.id,
            product_name=prod.product_name,
            product_description=prod.product_description,
            product_price=prod.product_price,
            channel_name=prod.channel_name,
            message_id=prod.message_id,
            timestamp=prod.timestamp,
            media_url=prod.media_url,
            source_type=prod.source_type,
            created_at=prod.created_at,
        )
        db.add(new_entry)

    db.commit()
    db.close()
    print("✅ Duplicates stored in same_products table successfully.")


if __name__ == "__main__":
    find_and_store_same_products()
