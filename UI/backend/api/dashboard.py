from fastapi import APIRouter

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"]
)

@router.get("/summary")
def get_summary():

    return {
        "total_parts": 28664,
        "defective_parts": 6476,
        "defect_rate": 22.59
    }