from fastapi import Depends, HTTPException
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
    def all_product(db: Session):
        return db.query(Product).all()