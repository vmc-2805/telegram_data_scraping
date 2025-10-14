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
from sqlalchemy import asc, desc, or_, func
from PIL import Image
import imagehash
from models.SameProduct import SameProduct
from models.UniqueProduct import UniqueProduct



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
        db: Session,
        page: int = 1,
        per_page: int = 50,
        search_value: str = "",
        order_column: int = 1,
        order_dir: str = "asc",
    ):
        query = db.query(SameProduct)
        if search_value:
            search = f"%{search_value}%"
            query = query.filter(
                or_(
                    SameProduct.product_name.ilike(search),
                    SameProduct.product_description.ilike(search),
                    SameProduct.channel_name.ilike(search),
                    SameProduct.source_type.ilike(search),
                )
            )

        column_map = {
            1: SameProduct.product_name,
            2: SameProduct.product_price,
            3: SameProduct.channel_name,
            4: SameProduct.product_description,
            5: SameProduct.source_type,
            6: SameProduct.created_at,
        }

        sort_column = column_map.get(order_column, SameProduct.product_name)
        if order_dir == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        total_records = db.query(SameProduct).count()
        total_filtered = query.count()

        offset = (page - 1) * per_page
        paged_products = query.offset(offset).limit(per_page).all()

        result = [
            {
                "product_name": p.product_name,
                "product_description": p.product_description,
                "product_price": float(p.product_price) if p.product_price else 0.0,
                "channel_name": p.channel_name,
                "source_type": p.source_type,
                "date": str(p.created_at) if p.created_at else "N/A",
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
        db: Session,
        page=1,
        per_page=50,
        search_value="",
        order_column=1,
        order_dir="asc",
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

        column_map = {
            1: "product_name",
            2: "product_price",
            3: "channel_name",
            4: "product_description",
            5: "source_type",
            6: "created_at",
        }
        sort_attr = column_map.get(order_column, "product_name")
        reverse = order_dir == "desc"

        if sort_attr == "created_at":
            lowest_price_products.sort(
                key=lambda x: x.created_at or datetime.min, reverse=reverse
            )
        else:
            lowest_price_products.sort(
                key=lambda x: getattr(x, sort_attr) or "", reverse=reverse
            )

        start = (page - 1) * per_page
        end = start + per_page
        paged_products = lowest_price_products[start:end]

        result = [
            {
                "product_name": p.product_name,
                "product_description": p.product_description,
                "product_price": float(p.product_price) if p.product_price else 0.0,
                "channel_name": p.channel_name,
                "source_type": p.source_type,
                "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
                "media_url": p.media_url,
            }
            for p in paged_products
        ]

        return {
            "products": result,
            "total": len(lowest_price_products),
            "total_filtered": len(lowest_price_products),
        }

    @staticmethod
    def zero_price_products_data(
        db: Session,
        page: int = 1,
        per_page: int = 50,
        search_value: str = "",
        order_column: int = 1,
        order_dir: str = "asc",
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

        # Map column index to actual column
        column_map = {
            1: Product.product_name,
            2: Product.product_price,
            3: Product.channel_name,
            4: Product.product_description,
            5: Product.source_type,
            6: Product.created_at,
        }

        order_column_attr = column_map.get(order_column, Product.product_name)
        if order_dir == "desc":
            query = query.order_by(order_column_attr.desc())
        else:
            query = query.order_by(order_column_attr.asc())

        total = query.count()
        offset = (page - 1) * per_page
        products = query.offset(offset).limit(per_page).all()

        result = []
        for p in products:
            result.append(
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
                }
            )

        return {"total": total, "total_filtered": total, "products": result}
    
    @staticmethod
    def unique_products_data(
        db: Session,
        page: int = 1,
        per_page: int = 50,
        search_value: str = "",
        order_column: int = 1,
        order_dir: str = "asc",
    ):
        column_map = {
            1: UniqueProduct.product_name,
            2: UniqueProduct.product_price,
            3: UniqueProduct.channel_name,
            4: UniqueProduct.product_description,
            5: UniqueProduct.source_type,
            6: UniqueProduct.created_at,
        }

        sort_column = column_map.get(order_column, UniqueProduct.product_name)
        sort_order = asc if order_dir == "asc" else desc

        query = db.query(UniqueProduct)

        if search_value:
            search = f"%{search_value}%"
            query = query.filter(
                or_(
                    UniqueProduct.product_name.ilike(search),
                    UniqueProduct.product_description.ilike(search),
                    UniqueProduct.channel_name.ilike(search),
                    UniqueProduct.source_type.ilike(search),
                )
            )

        total_filtered = query.count()
        total = db.query(UniqueProduct).count()

        query = query.order_by(sort_order(sort_column))

        offset = (page - 1) * per_page
        products = query.offset(offset).limit(per_page).all()

        result = []
        for p in products:
            result.append({
                "product_name": p.product_name,
                "product_description": p.product_description,
                "product_price": float(p.product_price) if p.product_price else 0.0,
                "channel_name": p.channel_name,
                "source_type": p.source_type,
                "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
                "media_url": p.media_url,
            })

        return {
            "products": result,
            "total": total,
            "total_filtered": total_filtered,
        }