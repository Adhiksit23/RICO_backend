from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dashboard import router as dashboard_router
from api.predictor import router as predictor_router
from api.calibrator import router as calibrator_router
from api.trainer import router as trainer_router
from api.calibration_api import router as calibration_router

app = FastAPI(
    title="Machine AI Platform",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register APIs
app.include_router(dashboard_router)
app.include_router(predictor_router)
app.include_router(calibrator_router)
app.include_router(trainer_router)
app.include_router(calibration_router)

@app.get("/")
def home():
    return {
        "message": "Machine AI Backend Running"
    }