from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_device_id, verify_device_id
from app.services.report_service import ReportPermissionDeniedError, ReportService


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/activity.xlsx", summary="Export the chief activity report as Excel")
async def download_activity_report(
    requester_device_id: UUID,
    db: AsyncSession = Depends(get_db),
    authenticated_device_id: UUID | None = Depends(get_current_device_id),
) -> StreamingResponse:
    verify_device_id(authenticated_device_id, requester_device_id)
    try:
        content = await ReportService.generate_activity_report(db, requester_device_id)
    except ReportPermissionDeniedError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(error)
        ) from error
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="gibdd-report.xlsx"'},
    )
