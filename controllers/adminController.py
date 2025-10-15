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
from models.ZeroPrice import ZeroPrice
from models.LowPrice import LowPrice



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
        query = db.query(LowPrice)

        if search_value:
            search = f"%{search_value.lower()}%"
            query = query.filter(
                func.lower(LowPrice.product_name).like(search)
                | func.lower(LowPrice.product_description).like(search)
                | func.lower(LowPrice.channel_name).like(search)
                | func.lower(LowPrice.source_type).like(search)
            )

        column_map = {
            1: LowPrice.product_name,
            2: LowPrice.product_price,
            3: LowPrice.channel_name,
            4: LowPrice.product_description,
            5: LowPrice.source_type,
            6: LowPrice.created_at,
        }

        sort_column = column_map.get(order_column, LowPrice.product_name)

        if order_dir == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        total_filtered = query.count()

        start = (page - 1) * per_page
        paged_data = query.offset(start).limit(per_page).all()

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
            for p in paged_data
        ]

        return {
            "products": result,
            "total": total_filtered,
            "total_filtered": total_filtered,
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

        query = db.query(ZeroPrice)

        if search_value:
            query = query.filter(
                or_(
                    ZeroPrice.product_name.ilike(f"%{search_value}%"),
                    ZeroPrice.channel_name.ilike(f"%{search_value}%"),
                    ZeroPrice.source_type.ilike(f"%{search_value}%"),
                )
            )

        column_map = {
            1: ZeroPrice.product_name,
            2: ZeroPrice.product_price,
            3: ZeroPrice.channel_name,
            4: ZeroPrice.product_description,
            5: ZeroPrice.source_type,
            6: ZeroPrice.created_at,
        }

        order_column_attr = column_map.get(order_column, ZeroPrice.product_name)
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
                    "date": (
                        p.created_at.strftime("%Y-%m-%d")
                        if hasattr(p.created_at, "strftime")
                        else str(p.created_at)
                    ),
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
            result.append(
                {
                    "product_name": p.product_name,
                    "product_description": p.product_description,
                    "product_price": float(p.product_price) if p.product_price else 0.0,
                    "channel_name": p.channel_name,
                    "source_type": p.source_type,
                    "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
                    "media_url": p.media_url,
                }
            )

        return {
            "products": result,
            "total": total,
            "total_filtered": total_filtered,
        }
