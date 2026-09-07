from contextlib import asynccontextmanager
import logging

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import router as auth_router
from api.dashboard import router as dashboard_router
from api.predictor import router as predictor_router
from api.calibrator import router as calibrator_router
from api.trainer import router as trainer_router
from api.calibration_api import router as calibration_router
from api.iot import router as iot_router
from services.iot_scheduler import start_iot_scheduler_on_boot, shutdown_iot_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("rico")


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_iot_scheduler_on_boot()
    try:
        yield
    finally:
        shutdown_iot_scheduler()


app = FastAPI(
    title="RICO — Industrial AI Platform",
    version="2.0.0",
    description="AI-powered die casting quality control backend.",
    lifespan=lifespan,
)

# CORS — restrict to known origins with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://rico-496016.web.app",
        "https://rico-496016.firebaseapp.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Auth (must come first for dependency ordering) ──────────────────
app.include_router(auth_router)

# ─── Existing APIs ───────────────────────────────────────────────────
app.include_router(dashboard_router)
app.include_router(predictor_router)
app.include_router(calibrator_router)
app.include_router(trainer_router)
app.include_router(calibration_router)
app.include_router(iot_router)


@app.get("/")
def home():
    return {"message": "RICO Industrial AI Backend Running", "version": "2.0.0"}
