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
from seed import seed_if_empty  # noqa: E402

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
        await seed_if_empty()
        logger.info("Seed check complete.")
    except Exception as e:
        logger.exception("Seed error: %s", e)


@app.on_event("shutdown")
async def _shutdown():
    get_client().close()
