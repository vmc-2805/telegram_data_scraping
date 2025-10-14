from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta
from database import get_db
from models.admin import Admin
import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from models.product import Product
from sqlalchemy import func, or_
from PIL import Image
import imagehash


load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="admin/login")

blacklisted_tokens = set()


def verify_password(plain_password, hashed_password):
    truncated = plain_password[:72]
    return pwd_context.verify(truncated, hashed_password)


def get_password_hash(password):
    truncated = password[:72]
    return pwd_context.hash(truncated)


def create_access_token(data: dict, expires_delta=None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_admin_by_email(db: Session, email: str):
    return db.query(Admin).filter(Admin.email == email).first()


class UserLogin:
    @staticmethod
    def login(form_data: OAuth2PasswordRequestForm, db: Session):
        admin = get_admin_by_email(db, form_data.username)

        if not admin:
            raise HTTPException(status_code=404, detail="Email not registered")

        if not verify_password(form_data.password, admin.password):
            raise HTTPException(status_code=401, detail="Incorrect password")

        expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        token = create_access_token({"sub": admin.email}, expires)

        return {"access_token": token, "token_type": "bearer"}

    @staticmethod
    def profile(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            admin = get_admin_by_email(db, email)
            if not admin:
                raise HTTPException(status_code=404, detail="Admin not found")
            return {"id": admin.id, "name": admin.name, "email": admin.email}
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

    @staticmethod
    def logout(token: str = Depends(oauth2_scheme)):
        blacklisted_tokens.add(token)
        return {"message": "Logged out successfully"}

    @staticmethod
    async def check_blacklist(request, call_next):
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            if token in blacklisted_tokens:
                raise HTTPException(status_code=401, detail="Token revoked")
        return await call_next(request)

    @staticmethod
    def all_product(
        db: Session,
        page: int = 1,
        per_page: int = 50,
        search_value: str = "",
        order_column: int = None,
        order_dir: str = None,
    ):
        column_map = [
            "media_url",
            "product_name",
            "product_description",
            "product_price",
            "channel_name",
            "source_type",
            "created_at",
            "id",
        ]

        if order_column is None or order_dir is None:
            order_field = "id"
            order_dir = "desc"
        else:
            order_field = (
                column_map[order_column]
                if 0 <= order_column < len(column_map)
                else "id"
            )

        query = db.query(Product).filter(
            Product.product_name.isnot(None), Product.product_name != ""
        )

        if search_value:
            query = query.filter(
                or_(
                    Product.product_name.ilike(f"%{search_value}%"),
                    Product.product_description.ilike(f"%{search_value}%"),
                    Product.channel_name.ilike(f"%{search_value}%"),
                    Product.source_type.ilike(f"%{search_value}%"),
                )
            )

        if order_dir.lower() == "asc":
            query = query.order_by(getattr(Product, order_field).asc())
        else:
            query = query.order_by(getattr(Product, order_field).desc())

        total = db.query(Product).count()
        total_filtered = query.count()
        products = query.offset((page - 1) * per_page).limit(per_page).all()

        result = [
            {
                "product_name": p.product_name,
                "product_description": p.product_description,
                "product_price": (
                    float(p.product_price) if p.product_price is not None else 0.0
                ),
                "channel_name": p.channel_name,
                "source_type": p.source_type,
                "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
                "media_url": p.media_url,
                "id": p.id,
            }
            for p in products
        ]

        return {
            "products": result,
            "total": total,
            "total_filtered": total_filtered,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_filtered + per_page - 1) // per_page,
        }

    @staticmethod
    def SameProductsData(
        db: Session, page: int = 1, per_page: int = 50, search_value: str = ""
    ):
        duplicate_names_query = (
            db.query(Product.product_name)
            .group_by(Product.product_name)
            .having(func.count(Product.product_name) > 1)
            .all()
        )
        duplicate_names = [n[0] for n in duplicate_names_query]

        same_name_products = (
            db.query(Product).filter(Product.product_name.in_(duplicate_names)).all()
        )

        products_with_images = (
            db.query(Product).filter(Product.media_url.isnot(None)).all()
        )
        image_hash_map = {}
        duplicate_image_ids = set()

        for p in products_with_images:
            if not p.media_url or p.media_url.strip() == "":
                continue
            image_path = os.path.normpath(p.media_url)
            if not os.path.isfile(image_path):
                continue
            try:
                img = Image.open(image_path).convert("L")
                img_hash = imagehash.phash(img)
                if img_hash in image_hash_map:
                    duplicate_image_ids.add(image_hash_map[img_hash])
                    duplicate_image_ids.add(p.id)
                else:
                    image_hash_map[img_hash] = p.id
            except Exception:
                continue

        same_image_products = (
            db.query(Product).filter(Product.id.in_(duplicate_image_ids)).all()
        )

        all_products = same_name_products + same_image_products
        seen_names = set()
        unique_products = []
        for p in all_products:
            normalized_name = p.product_name.strip().lower()
            if normalized_name not in seen_names:
                seen_names.add(normalized_name)
                unique_products.append(p)

        if search_value:
            filtered_products = [
                p
                for p in unique_products
                if search_value.lower() in (p.product_name or "").lower()
                or search_value.lower() in (p.product_description or "").lower()
                or search_value.lower() in (p.channel_name or "").lower()
                or search_value.lower() in (p.source_type or "").lower()
            ]
        else:
            filtered_products = unique_products

        total_records = len(unique_products)
        total_filtered = len(filtered_products)
        start = (page - 1) * per_page
        end = start + per_page
        paged_products = filtered_products[start:end]

        result = [
            {
                "product_name": p.product_name,
                "product_description": p.product_description,
                "product_price": p.product_price,
                "channel_name": p.channel_name,
                "source_type": p.source_type,
                "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "N/A",
                "media_url": p.media_url,
            }
            for p in paged_products
        ]

        return {
            "products": result,
            "total": total_records,
            "total_filtered": total_filtered,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_filtered + per_page - 1) // per_page,
        }

    @staticmethod
    def low_price_products_data(
        db: Session, page: int = 1, per_page: int = 50, search_value: str = ""
    ):

        duplicate_names_query = (
            db.query(Product.product_name)
            .group_by(Product.product_name)
            .having(func.count(Product.product_name) > 1)
            .all()
        )
        duplicate_names = [n[0] for n in duplicate_names_query]

        products_with_images = (
            db.query(Product).filter(Product.media_url.isnot(None)).all()
        )
        image_hash_map = {}
        image_groups = {}
        group_index = 0

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

        name_groups = []
        for name in duplicate_names:
            products = db.query(Product).filter(Product.product_name == name).all()
            if len(products) > 1:
                name_groups.append(products)

        lowest_price_products = []

        def get_lowest(group):
            valid = [p for p in group if p.product_price is not None]
            if not valid:
                return None
            if all(p.product_price == 0.0 for p in valid):
                return None
            valid_non_zero = [p for p in valid if p.product_price > 0.0]
            if valid_non_zero:
                return min(valid_non_zero, key=lambda x: x.product_price)
            else:
                return min(valid, key=lambda x: x.product_price)

        for group in name_groups + duplicate_image_groups:
            product = get_lowest(group)
            if product and product not in lowest_price_products:
                lowest_price_products.append(product)

        if search_value:
            search = search_value.lower()
            lowest_price_products = [
                p
                for p in lowest_price_products
                if search in (p.product_name or "").lower()
                or search in (p.product_description or "").lower()
                or search in (p.channel_name or "").lower()
                or search in (p.source_type or "").lower()
            ]

        total_records = len(lowest_price_products)
        start = (page - 1) * per_page
        end = start + per_page
        paged_products = lowest_price_products[start:end]

        result = [
            {
                "product_name": p.product_name,
                "product_description": p.product_description,
                "product_price": p.product_price,
                "channel_name": p.channel_name,
                "source_type": p.source_type,
                "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
                "media_url": p.media_url,
            }
            for p in paged_products
        ]

        return {
            "products": result,
            "total": total_records,
            "total_filtered": total_records,
        }

    @staticmethod
    def zero_price_products_data(
        db: Session, page: int = 1, per_page: int = 50, search_value: str = ""
    ):
        query = db.query(Product).filter(Product.product_price == 0)

        if search_value:
            query = query.filter(
                or_(
                    Product.product_name.ilike(f"%{search_value}%"),
                    Product.channel_name.ilike(f"%{search_value}%"),
                    Product.source_type.ilike(f"%{search_value}%"),
                )
            )

        total = query.count()

        offset = (page - 1) * per_page
        products = query.offset(offset).limit(per_page).all()

        result = []
        for p in products:
            result.append(
                {
                    "product_name": p.product_name,
                    "product_description": p.product_description,
                    "product_price": p.product_price,
                    "channel_name": p.channel_name,
                    "source_type": p.source_type,
                    "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
                    "media_url": p.media_url,
                }
            )

        return {
            "total": total,
            "total_filtered": total,
            "products": result,
        }
