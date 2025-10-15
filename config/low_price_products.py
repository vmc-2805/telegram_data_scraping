import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import get_db
from models.product import Product
from models.LowPrice import LowPrice
from sqlalchemy.orm import Session
from sqlalchemy import func
from PIL import Image
import imagehash
from datetime import datetime


def find_low_price_products():
    db: Session = next(get_db())

    print("🔍 Finding lowest price products...\n")

    duplicate_names_query = (
        db.query(Product.product_name)
        .group_by(Product.product_name)
        .having(func.count(Product.product_name) > 1)
        .all()
    )
    duplicate_names = [n[0] for n in duplicate_names_query]

    print(f"🧩 Found {len(duplicate_names)} duplicate names.\n")

    products_with_images = db.query(Product).filter(Product.media_url.isnot(None)).all()
    image_hash_map = {}
    image_groups = {}
    group_index = 0

    print("🖼️ Checking duplicate images...\n")

    for p in products_with_images:
        img_path = os.path.normpath(p.media_url)
        if not os.path.exists(img_path):
            continue
        try:
            img = Image.open(img_path).convert("L")
            img_hash = imagehash.phash(img)

            matched_group = None
            for existing_hash, group_id in image_hash_map.items():
                if img_hash - existing_hash <= 5:
                    matched_group = group_id
                    break

            if matched_group is not None:
                image_groups[matched_group].append(p)
            else:
                image_hash_map[img_hash] = group_index
                image_groups[group_index] = [p]
                group_index += 1

        except Exception:
            continue

    duplicate_image_groups = [g for g in image_groups.values() if len(g) > 1]
    print(f"🖼️ Found {len(duplicate_image_groups)} groups of similar images.\n")

    name_groups = []
    for name in duplicate_names:
        products = db.query(Product).filter(Product.product_name == name).all()
        if len(products) > 1:
            name_groups.append(products)

    lowest_price_products = []

    def get_lowest(group):
        valid = [p for p in group if p.product_price is not None and p.product_price > 0]
        if not valid:
            return None
        return min(valid, key=lambda x: x.product_price)

    print("📦 Comparing duplicate-name groups...\n")
    for group in name_groups:
        product = get_lowest(group)
        if product and product not in lowest_price_products:
            lowest_price_products.append(product)
            print(f"🟢 [BY NAME] {product.product_name} → ₹{product.product_price}")

    print("\n🖼️ Comparing duplicate-image groups...\n")
    for group in duplicate_image_groups:
        product = get_lowest(group)
        if product and product not in lowest_price_products:
            lowest_price_products.append(product)
            print(f"🟣 [BY IMAGE] {product.product_name} → ₹{product.product_price}")

    print(f"\n🧾 Found {len(lowest_price_products)} unique lowest-price products.\n")

    for product in lowest_price_products:
        existing = (
            db.query(LowPrice).filter(LowPrice.message_id == product.message_id).first()
        )
        if existing:
            print(f"⚠️ Skipped duplicate: {product.product_name} ({product.message_id})")
            continue

        entry = LowPrice(
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

        db.add(entry)
        print(f"✅ Stored: {product.product_name} | ₹{product.product_price}")

    db.commit()
    print("\n🎯 All low-price products stored successfully in 'low_price_products' table.\n")


if __name__ == "__main__":
    find_low_price_products()
