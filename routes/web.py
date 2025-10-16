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
from fastapi import  Depends
from fastapi.responses import JSONResponse, HTMLResponse
from models.product import Product


router = APIRouter()
templates = Jinja2Templates(directory="templates")

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)


@router.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        db = next(get_db())
        user = db.query(Admin).filter(Admin.email == email).first()
        user_name = user.name if user else email

    except JWTError:
        return RedirectResponse(url="/login")

    response = templates.TemplateResponse(
        "index.html",
        {"request": request, "user_name": user_name},
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@router.get("/dashboard_counts")
def dashboard_counts(db: Session = Depends(get_db)):
    total_products = db.query(Product).count()

    same_products_data = UserLogin.SameProductsData(
        db=db, page=1, per_page=10_000, search_value=""
    )
    total_same_products = same_products_data.get(
        "total", len(same_products_data.get("products", []))
    )

    total_channels = db.query(Product.channel_name).distinct().count()

    low_price_data = UserLogin.low_price_products_data(
        db=db, page=1, per_page=10_000, search_value=""
    )
    total_low_price = low_price_data.get(
        "total", len(low_price_data.get("products", []))
    )

    return {
        "total_products": total_products,
        "same_products": total_same_products,
        "total_channels": total_channels,
        "low_price_products": total_low_price,
    }


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login_submit(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    try:
        result = UserLogin.login(form_data, db)
        return JSONResponse(
            {
                "success": True,
                "access_token": result["access_token"],
                "token_type": result["token_type"],
            }
        )
    except HTTPException as e:
        return JSONResponse(
            {"success": False, "detail": e.detail}, status_code=e.status_code
        )


@router.get("/profile")
def profile(token: str, db: Session = Depends(get_db)):
    return UserLogin.profile(token, db)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


@router.post("/logout")
def logout_endpoint(token: str = Depends(oauth2_scheme)):
    return UserLogin.logout(token)


@router.post("/all_product")
async def all_product(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    page = int(form.get("page", 1))
    per_page = int(form.get("per_page", 50))
    draw = int(form.get("draw", 1))
    search_value = form.get("search_value", "")

    order_column_index = int(form.get("order_column", 1))
    order_dir = form.get("order_dir", "asc")

    data = UserLogin.all_product(
        db, page, per_page, search_value, order_column_index, order_dir
    )

    return JSONResponse(
        {
            "draw": draw,
            "recordsTotal": data["total"],
            "recordsFiltered": data["total_filtered"],
            "data": data["products"],
        }
    )


@router.get("/same_products")
def same_products(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        db = next(get_db())
        user = db.query(Admin).filter(Admin.email == email).first()
        user_name = user.name if user else email

    except JWTError:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "same_products.html",
        {"request": request, "user_name": user_name},
    )


@router.post("/same_products_data")
async def same_products_data(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    page = int(form.get("page", 1))
    per_page = int(form.get("per_page", 50))
    draw = int(form.get("draw", 1))
    search_value = form.get("search_value", "")
    order_column = int(form.get("order_column", 1))
    order_dir = form.get("order_dir", "asc")

    products_data = UserLogin.SameProductsData(
        db, page=page, per_page=per_page, search_value=search_value,
        order_column=order_column, order_dir=order_dir
    )

    return JSONResponse({
        "draw": draw,
        "recordsTotal": products_data["total"],
        "recordsFiltered": products_data["total_filtered"],
        "data": products_data["products"],
    })


@router.get("/low_price_products")
def low_price_products(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        db = next(get_db())
        user = db.query(Admin).filter(Admin.email == email).first()
        if user:
            user_name = user.name
        else:
            user_name = email

    except JWTError:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "low_price_products.html",
        {"request": request, "user_name": user_name},
    )


@router.post("/low_price_products_data")
async def low_price_products_data(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    page = int(form.get("page", 1))
    per_page = int(form.get("per_page", 50))
    draw = int(form.get("draw", 1))
    search_value = form.get("search_value", "")
    order_column = int(form.get("order_column", 1))
    order_dir = form.get("order_dir", "asc")

    products_data = UserLogin.low_price_products_data(
        db, page=page, per_page=per_page, search_value=search_value,
        order_column=order_column, order_dir=order_dir
    )

    return JSONResponse({
        "draw": draw,
        "recordsTotal": products_data["total"],
        "recordsFiltered": products_data["total_filtered"],
        "data": products_data["products"]
    })



@router.get("/zero_price_products")
def zero_price_products(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        db = next(get_db())
        user = db.query(Admin).filter(Admin.email == email).first()
        if user:
            user_name = user.name
        else:
            user_name = email

    except JWTError:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "zero_price_products.html",
        {"request": request, "user_name": user_name},
    )


@router.post("/zero_price_products_data")
async def zero_price_products_data(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    page = int(form.get("page", 1))
    per_page = int(form.get("per_page", 50))
    draw = int(form.get("draw", 1))
    search_value = form.get("search_value", "")
    order_column = int(form.get("order_column", 1))
    order_dir = form.get("order_dir", "asc")

    products_data = UserLogin.zero_price_products_data(
        db, page=page, per_page=per_page, search_value=search_value,
        order_column=order_column, order_dir=order_dir
    )

    return JSONResponse({
        "draw": draw,
        "recordsTotal": products_data["total"],
        "recordsFiltered": products_data["total_filtered"],
        "data": products_data["products"],
    })


@router.get("/unique_products")
def unique_products(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        db = next(get_db())
        user = db.query(Admin).filter(Admin.email == email).first()
        if user:
            user_name = user.name
        else:
            user_name = email

    except JWTError:
        return RedirectResponse(url="/login")

    return templates.TemplateResponse(
        "unique_products.html",
        {"request": request, "user_name": user_name},
    )

@router.post("/unique_products_data")
async def unique_products_data(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    page = int(form.get("page", 1))
    per_page = int(form.get("per_page", 50))
    draw = int(form.get("draw", 1))
    search_value = form.get("search_value", "")
    order_column = int(form.get("order_column", 1))
    order_dir = form.get("order_dir", "asc")

    products_data = UserLogin.unique_products_data(
        db,
        page=page,
        per_page=per_page,
        search_value=search_value,
        order_column=order_column,
        order_dir=order_dir
    )

    return JSONResponse({
        "draw": draw,
        "recordsTotal": products_data["total"],
        "recordsFiltered": products_data["total_filtered"],
        "data": products_data["products"],
    })
