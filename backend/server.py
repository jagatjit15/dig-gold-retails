"""SwarnaERP backend entrypoint."""
import logging
import os
from fastapi import FastAPI, APIRouter
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
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
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
