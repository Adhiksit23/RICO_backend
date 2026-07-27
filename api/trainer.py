"""
Trainer API router — placeholder model training endpoint.
"""
import logging

from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/trainer",
    tags=["Trainer"],
)


@router.get("/train")
def train():
    """Trigger model retraining."""
    try:
        # TODO: replace with real training job dispatch
        return {"status": "Training Started"}
    except Exception as exc:
        logger.exception("[/trainer/train] Unexpected error starting training job")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start training. Please try again.",
        ) from exc