"""
Markets API Routes.

Endpoints for market data and Chainlink analysis.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List

from ..services.trader_service import TraderService

router = APIRouter(prefix="/api/markets", tags=["Markets"])
trader_service = TraderService()


class MarketResponse(BaseModel):
    """Markets response."""
    success: bool
    data: dict
    error: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Chainlink analysis response."""
    success: bool
    data: dict
    error: Optional[str] = None


@router.get("/")
async def get_markets(limit: int = Query(default=20, ge=1, le=100)) -> MarketResponse:
    """Get available crypto markets."""
    result = trader_service.get_markets(limit=limit)
    if result['success']:
        return MarketResponse(success=True, data=result['data'])
    return MarketResponse(success=False, data={}, error=result.get('error'))


@router.get("/analysis/{crypto_name}")
async def get_chainlink_analysis(
    crypto_name: str,
    timeframe: str = Query(default="15min", pattern="^(15min|1h|daily)$")
) -> AnalysisResponse:
    """Get Chainlink analysis for a cryptocurrency."""
    result = trader_service.get_chainlink_analysis(crypto_name, timeframe=timeframe)
    if result['success']:
        return AnalysisResponse(success=True, data=result['data'])
    return AnalysisResponse(success=False, data={}, error=result.get('error'))
