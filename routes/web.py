from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from controllers.adminController import UserLogin
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi import Request, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
import os
from dotenv import load_dotenv
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError
from database import get_db
from models.admin import Admin

router = APIRouter()
templates = Jinja2Templates(directory="templates")

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)

@router.get("/")
def read_root(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")  
        user_name = None

       
        db = next(get_db())
        user = db.query(Admin).filter(Admin.email == email).first()
        if user:
            user_name = user.name
        else:
            user_name = email  

    except JWTError:
        return RedirectResponse(url="/login")

    response = templates.TemplateResponse("index.html", {"request": request, "user_name": user_name})
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login_submit(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    try:
        result = UserLogin.login(form_data, db)
        return JSONResponse({
            "success": True,
            "access_token": result["access_token"],
            "token_type": result["token_type"]
        })
    except HTTPException as e:
        return JSONResponse({
            "success": False,
            "detail": e.detail
        }, status_code=e.status_code)



@router.get("/profile")
def profile(token: str, db: Session = Depends(get_db)):
    return UserLogin.profile(token, db)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

@router.post("/logout")
def logout_endpoint(token: str = Depends(oauth2_scheme)):
    return UserLogin.logout(token)

