import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .database import get_connection, init_db
from .auth import hash_password, verify_password, create_token, decode_token
from .gemini_utils import generate_recommendations

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

app = FastAPI(title="PocketSmart AI")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")

@app.on_event("startup")
def startup():
    init_db()

def current_user(request: Request):
    uid = request.session.get("user_id")
    if not uid:
        return None
    conn = get_connection()
    user = conn.execute("SELECT id, name, email FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return dict(user) if user else None

def save_history(user_id, planner, data, response):
    conn = get_connection()
    conn.execute(
        "INSERT INTO recommendations(user_id, planner, request_json, response_text) VALUES(?,?,?,?)",
        (user_id, planner, json.dumps(data), response),
    )
    conn.commit()
    conn.close()

def require_user(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return user

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "user": current_user(request)})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "user": current_user(request), "error": None})

@app.post("/register")
def register(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",
            (name.strip(), email, hash_password(password)),
        )
        conn.commit()
    except Exception:
        conn.close()
        return templates.TemplateResponse("register.html", {"request": request, "user": None, "error": "Email already registered."})
    user = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    request.session["user_id"] = user["id"]
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "user": current_user(request), "error": None})

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    conn.close()
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": "Invalid email or password."})
    request.session["user_id"] = user["id"]
    request.session["access_token"] = create_token(user["id"], SECRET_KEY)
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, planner, created_at FROM recommendations WHERE user_id=? ORDER BY id DESC LIMIT 8",
        (user["id"],),
    ).fetchall()
    conn.close()
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "history": [dict(x) for x in rows]})

@app.get("/planner/{planner}", response_class=HTMLResponse)
def planner_page(request: Request, planner: str):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if planner not in {"home", "party", "jewelry"}:
        raise HTTPException(404, "Planner not found")
    return templates.TemplateResponse("planner.html", {"request": request, "user": user, "planner": planner})

@app.post("/generate-home", response_class=HTMLResponse)
async def generate_home(
    request: Request,
    budget: float = Form(...),
    room: str = Form(...),
    style: str = Form(...),
    items: str = Form(""),
):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    data = {"budget": budget, "room": room, "style": style, "items": items}
    result = generate_recommendations("home", data)
    save_history(user["id"], "home", data, result)
    return templates.TemplateResponse("recommendations.html", {"request": request, "user": user, "planner": "Home Interior", "result": result, "data": data})

@app.post("/generate-party", response_class=HTMLResponse)
async def generate_party(
    request: Request,
    budget: float = Form(...),
    guests: int = Form(...),
    event_type: str = Form(...),
    venue: str = Form(...),
    preferences: str = Form(""),
):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    data = {"budget": budget, "guests": guests, "event_type": event_type, "venue": venue, "preferences": preferences}
    result = generate_recommendations("party", data)
    save_history(user["id"], "party", data, result)
    return templates.TemplateResponse("recommendations.html", {"request": request, "user": user, "planner": "Party Planner", "result": result, "data": data})

@app.post("/generate-jewelry", response_class=HTMLResponse)
async def generate_jewelry(
    request: Request,
    budget: float = Form(...),
    occasion: str = Form(...),
    style: str = Form(...),
    preferences: str = Form(""),
    outfit_image: UploadFile | None = File(None),
):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    image_bytes = None
    image_mime = None
    if outfit_image and outfit_image.filename:
        allowed = {"image/jpeg", "image/png", "image/webp"}
        if outfit_image.content_type not in allowed:
            raise HTTPException(400, "Only JPG, PNG, and WEBP images are supported.")
        image_bytes = await outfit_image.read()
        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(400, "Image must be smaller than 10 MB.")
        image_mime = outfit_image.content_type

    data = {"budget": budget, "occasion": occasion, "style": style, "preferences": preferences, "image_uploaded": bool(image_bytes)}
    result = generate_recommendations("jewelry", data, image_bytes, image_mime)
    save_history(user["id"], "jewelry", data, result)
    return templates.TemplateResponse("recommendations.html", {"request": request, "user": user, "planner": "Jewelry Planner", "result": result, "data": data})

@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM recommendations WHERE user_id=? ORDER BY id DESC",
        (user["id"],),
    ).fetchall()
    conn.close()
    return templates.TemplateResponse("history.html", {"request": request, "user": user, "history": [dict(x) for x in rows]})

# API-style routes required by the project specification.
@app.post("/token")
def token_endpoint(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    conn.close()
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": create_token(user["id"], SECRET_KEY), "token_type": "bearer"}

@app.get("/session-info")
def session_info(request: Request):
    user = current_user(request)
    return {"logged_in": bool(user), "user": user}

@app.get("/session-data")
def session_data(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Login required")
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) AS c FROM recommendations WHERE user_id=?", (user["id"],)).fetchone()["c"]
    conn.close()
    return {"user_id": user["id"], "recommendation_count": count}

@app.get("/recommendations-details/{recommendation_id}")
def recommendation_details(request: Request, recommendation_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        raise HTTPException(401, "Login required")
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM recommendations WHERE id=? AND user_id=?",
        (recommendation_id, user["id"]),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Recommendation not found")
    return dict(row)

@app.get("/health")
def health():
    return {"status": "ok", "service": "PocketSmart AI"}
