from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from routes.web import router as web_router
from controllers.adminController import UserLogin
import uvicorn
import os

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
downloads_dir = os.path.join(os.path.dirname(__file__), "downloads")
app.mount("/downloads", StaticFiles(directory=downloads_dir), name="downloads")
templates = Jinja2Templates(directory="templates")
app.state.templates = templates

app.include_router(web_router)

app.middleware("http")(UserLogin.check_blacklist)

if __name__ == "__main__":
    uvicorn.run("index:app", host="192.168.1.12", port=8000, reload=True)

