import logging
import base64
import hashlib
import hmac
import secrets
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.models.database import init_db, init_chroma
from app.scheduler import start_scheduler, shutdown_scheduler
from app.routers import sources, articles, reports, qa, collect
from app.config import WEB_AUTH_PASSWORD, WEB_AUTH_USERNAME

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    logger.info("Initializing ChromaDB...")
    init_chroma()
    logger.info("Starting scheduler...")
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="AI Infra 决策情报", version="0.1.0", lifespan=lifespan)

AUTH_COOKIE = "ai_infra_session"
AUTH_MAX_AGE = 7 * 24 * 60 * 60
PUBLIC_PATHS = {"/login", "/api/auth/login", "/api/health", "/favicon.ico"}


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if not WEB_AUTH_USERNAME or not WEB_AUTH_PASSWORD:
        return await call_next(request)

    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    if _request_is_authenticated(request):
        return await call_next(request)

    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    return RedirectResponse(url="/login", status_code=303)


def _request_is_authenticated(request: Request) -> bool:
    token = request.cookies.get(AUTH_COOKIE)
    if token and _verify_auth_token(token):
        return True
    return _check_basic_auth(request.headers.get("Authorization", ""))


def _check_basic_auth(auth_header: str) -> bool:
    if not auth_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header.removeprefix("Basic ").strip()).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return False
    return _valid_credentials(username, password)


def _valid_credentials(username: str, password: str) -> bool:
    return (
        secrets.compare_digest(username, WEB_AUTH_USERNAME)
        and secrets.compare_digest(password, WEB_AUTH_PASSWORD)
    )


def _make_auth_token(username: str) -> str:
    expires = str(int(time.time()) + AUTH_MAX_AGE)
    payload = f"{username}|{expires}"
    signature = hmac.new(WEB_AUTH_PASSWORD.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{signature}".encode("utf-8")).decode("utf-8")


def _verify_auth_token(token: str) -> bool:
    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        username, expires, signature = decoded.split("|", 2)
        if int(expires) < int(time.time()):
            return False
        payload = f"{username}|{expires}"
        expected = hmac.new(WEB_AUTH_PASSWORD.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    except Exception:
        return False
    return secrets.compare_digest(username, WEB_AUTH_USERNAME) and secrets.compare_digest(signature, expected)


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/login")
def login_page():
    if not WEB_AUTH_USERNAME or not WEB_AUTH_PASSWORD:
        return RedirectResponse(url="/", status_code=303)
    return FileResponse("static/login.html")


@app.post("/api/auth/login")
async def login(request: Request):
    if not WEB_AUTH_USERNAME or not WEB_AUTH_PASSWORD:
        return {"ok": True, "auth_enabled": False}

    body = await request.json()
    username = str(body.get("username", ""))
    password = str(body.get("password", ""))
    if not _valid_credentials(username, password):
        return JSONResponse({"detail": "用户名或密码错误"}, status_code=401)

    response = JSONResponse({"ok": True})
    response.set_cookie(
        AUTH_COOKIE,
        _make_auth_token(username),
        max_age=AUTH_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@app.post("/api/auth/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(AUTH_COOKIE)
    return response


@app.get("/api/auth/status")
def auth_status():
    return {"auth_enabled": bool(WEB_AUTH_USERNAME and WEB_AUTH_PASSWORD)}


app.include_router(sources.router)
app.include_router(articles.router)
app.include_router(reports.router)
app.include_router(qa.router)
app.include_router(collect.router)


@app.get("/api/health")
def health():
    from app.models.database import get_chroma
    from app.config import DEEPSEEK_API_KEY

    chroma_ok = "ok"
    try:
        get_chroma().list_collections()
    except Exception:
        chroma_ok = "error"

    llm_ok = "ok" if DEEPSEEK_API_KEY else "missing_key"

    return {"status": "ok", "chroma": chroma_ok, "llm": llm_ok}
