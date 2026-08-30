"""Pre-flight Gate API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import PreflightRequest, PreflightResponse
from app.persistence.database import get_db_session
from app.preflight.service import PreflightService

router = APIRouter()


@router.post("/preflight", response_model=PreflightResponse)
async def evaluate_preflight(
    request: PreflightRequest,
    db: AsyncSession = Depends(get_db_session),
) -> PreflightResponse:
    """Evaluate pre-flight eligibility and budgets before model invocation."""
    service = PreflightService()
    resp, _, _ = await service.evaluate(request, db)
    return resp
