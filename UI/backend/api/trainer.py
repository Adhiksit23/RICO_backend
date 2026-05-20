from fastapi import APIRouter

router = APIRouter(
    prefix="/api/trainer",
    tags=["Trainer"]
)

@router.get("/train")
def train():

    return {
        "status": "Training Started"
    }