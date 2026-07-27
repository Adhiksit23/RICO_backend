"""
Dashboard API router — placeholder summary endpoint.
Will eventually query the database for real-time stats.
"""
import logging

from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get("/summary")
def get_summary():
    """Return high-level production and defect summary statistics."""
    try:
        # TODO: replace with a real DB query when live data is wired up
        return {
            "total_parts": 28664,
            "defective_parts": 6476,
            "defect_rate": 22.59,
        }
    except Exception as exc:
        logger.exception("[/dashboard/summary] Unexpected error building summary")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard summary. Please try again.",
        ) from exc