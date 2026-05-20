from fastapi import APIRouter

router = APIRouter(
    prefix="/api/predictor",
    tags=["Predictor"]
)

@router.get("/predict")
def predict():

    return {
        "non_filling": 85.4,
        "blowhole": 9.2,
        "porosity": 47.4
    }