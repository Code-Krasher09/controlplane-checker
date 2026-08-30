"""ControlPlane Gateway Inspect API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import GatewayInspectRequest, GatewayInspectResponse
from app.gateway.service import GatewayService
from app.persistence.database import get_db_session

router = APIRouter()


@router.post("/inspect", response_model=GatewayInspectResponse)
async def inspect_request(
    request: GatewayInspectRequest,
    db: AsyncSession = Depends(get_db_session),
) -> GatewayInspectResponse:
    """Execute end-to-end ControlPlane runtime inspection and intervention pipeline."""
    gateway = GatewayService()
    return await gateway.inspect(request, db)
