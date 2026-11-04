"""
API router for Quality & Prescription Report Generation and Export.
Completely decoupled from existing dashboard and calibration routes.
"""
from datetime import datetime
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from services.report_service import (
    ReportPreviewResponse,
    generate_report_excel_workbook,
    get_report_preview_data,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/reports",
    tags=["Reports & Export"],
)


def _clean_str(val: Any, default: str = "All") -> str:
    if val is None:
        return default
    if hasattr(val, "default"):
        d = getattr(val, "default")
        return str(d) if d is not ... and d is not None else default
    return str(val)


def _clean_opt(val: Any) -> Optional[str]:
    if val is None:
        return None
    if hasattr(val, "default"):
        d = getattr(val, "default")
        return str(d) if d is not ... and d is not None else None
    return str(val)


@router.get("/preview", response_model=ReportPreviewResponse)
def get_report_preview(
    client: str = Query("All", description="Target client name or 'All'"),
    machine: str = Query("All", description="Target machine name/id or 'All'"),
    die: str = Query("All", description="Target die name (e.g. S17) or 'All'"),
    period: str = Query("all", description="Period filter: all, today, last_7_days, last_month, ytd, custom"),
    start_date: Optional[str] = Query(None, description="Custom period start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Custom period end date (YYYY-MM-DD)"),
):
    """
    Get paginated/structured report preview data (JSON) for tabular UI viewing.
    Contains both 'Prescribed Parameter - Bellurbi' and 'Bellurbis' datasets.
    """
    c = _clean_str(client, "All")
    m = _clean_str(machine, "All")
    d = _clean_str(die, "All")
    p = _clean_str(period, "all")
    s = _clean_opt(start_date)
    e = _clean_opt(end_date)

    try:
        data = get_report_preview_data(
            client=c,
            machine=m,
            die=d,
            period=p,
            start_date=s,
            end_date=e,
        )
        return data
    except Exception as exc:
        logger.exception("[/api/reports/preview] Failed to assemble preview: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report preview: {str(exc)}",
        ) from exc


@router.get("/export")
def export_report_excel(
    client: str = Query("All", description="Target client name or 'All'"),
    machine: str = Query("All", description="Target machine name/id or 'All'"),
    die: str = Query("All", description="Target die name or 'All'"),
    period: str = Query("all", description="Period filter: all, today, last_7_days, last_month, ytd, custom"),
    start_date: Optional[str] = Query(None, description="Custom period start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Custom period end date (YYYY-MM-DD)"),
):
    """
    Generate and stream a 2-sheet Excel spreadsheet (.xlsx) matching Report_Structure_v6:
      - Sheet 1: Prescribed Parameter - Bellurbi
      - Sheet 2: Bellurbis (Predicted vs Actual Defects)
    """
    c = _clean_str(client, "All")
    m = _clean_str(machine, "All")
    d = _clean_str(die, "All")
    p = _clean_str(period, "all")
    s = _clean_opt(start_date)
    e = _clean_opt(end_date)

    try:
        excel_stream = generate_report_excel_workbook(
            client=c,
            machine=m,
            die=d,
            period=p,
            start_date=s,
            end_date=e,
        )

        date_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_die = d if d and d != "All" else "Summary"
        filename = f"RICO_Quality_Report_{safe_die}_{date_tag}.xlsx"

        return StreamingResponse(
            excel_stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except Exception as exc:
        logger.exception("[/api/reports/export] Failed to generate Excel report: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export Excel report: {str(exc)}",
        ) from exc

