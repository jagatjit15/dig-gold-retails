"""SwarnaERP backend entrypoint."""
import logging
import os
from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from db import db, get_client  # noqa: E402
from routers.auth_router import router as auth_router  # noqa: E402
from routers.masters_router import router as masters_router  # noqa: E402
from routers.inventory_router import router as inventory_router  # noqa: E402
from routers.files_router import router as files_router  # noqa: E402
from routers.billing_router import router as billing_router  # noqa: E402
from routers.whatsapp_router import router as whatsapp_router  # noqa: E402
from routers.transfers_router import router as transfers_router  # noqa: E402
from routers.lookbook_router import router as lookbook_router  # noqa: E402
from seed import seed_if_empty  # noqa: E402
from storage import init_storage  # noqa: E402

app = FastAPI(title="SwarnaERP API")

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"service": "SwarnaERP", "status": "ok"}


@api_router.get("/health")
async def health():
    return {"status": "ok"}


api_router.include_router(auth_router)
api_router.include_router(masters_router)
api_router.include_router(inventory_router)
api_router.include_router(files_router)
api_router.include_router(billing_router)
api_router.include_router(whatsapp_router)
api_router.include_router(transfers_router)
api_router.include_router(lookbook_router)
app.include_router(api_router)

ALLOWED_ORIGINS = os.environ["CORS_ORIGINS"].split(",")


UNSAFE = ("POST", "PUT", "PATCH", "DELETE")


def _origin_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin:
        return origin in ALLOWED_ORIGINS
    referer = request.headers.get("referer")
    if referer:
        return any(referer == o or referer.startswith(o + "/") for o in ALLOWED_ORIGINS)
    # Non-browser clients without cookies (e.g. login from scripts) carry no CSRF risk
    return not (request.cookies.get("swarna_access") or request.cookies.get("swarna_refresh"))


@app.middleware("http")
async def check_origin(request: Request, call_next):
    if request.method in UNSAFE and not _origin_allowed(request):
        return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("swarnaerp")


@app.on_event("startup")
async def _startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.login_attempts.create_index("identifier")
        await db.files.create_index([("owner_type", 1), ("owner_id", 1)])
        await seed_if_empty()
        logger.info("Seed check complete.")
    except Exception as e:
        logger.exception("Seed error: %s", e)
    try:
        init_storage()
        logger.info("Storage initialized.")
    except Exception as e:
        logger.error("Storage init failed: %s", e)


@app.on_event("shutdown")
async def _shutdown():
    get_client().close()
