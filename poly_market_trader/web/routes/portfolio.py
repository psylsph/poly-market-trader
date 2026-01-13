"""
Portfolio API Routes.

Endpoints for portfolio management and statistics.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal

from ..services.trader_service import TraderService

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])
trader_service = TraderService()


class ResetPortfolioRequest(BaseModel):
    """Request body for resetting portfolio."""
    initial_balance: float = Field(default=10000.0, ge=100, le=1000000)


class PortfolioResponse(BaseModel):
    """Portfolio summary response."""
    success: bool
    data: dict
    error: Optional[str] = None


@router.get("/")
async def get_portfolio() -> PortfolioResponse:
    """Get portfolio summary including balance, P&L, and statistics."""
    result = trader_service.get_portfolio_summary()
    if result['success']:
        return PortfolioResponse(success=True, data=result['data'])
    return PortfolioResponse(success=False, data={}, error=result.get('error'))


@router.get("/positions")
async def get_positions() -> PortfolioResponse:
    """Get all active positions."""
    result = trader_service.get_positions()
    if result['success']:
        return PortfolioResponse(success=True, data=result['data'])
    return PortfolioResponse(success=False, data={}, error=result.get('error'))


@router.get("/statistics")
async def get_statistics() -> PortfolioResponse:
    """Get token performance statistics."""
    result = trader_service.get_token_statistics()
    if result['success']:
        return PortfolioResponse(success=True, data=result['data'])
    return PortfolioResponse(success=False, data={}, error=result.get('error'))


@router.post("/reset")
async def reset_portfolio(request: ResetPortfolioRequest = None) -> PortfolioResponse:
    """Reset portfolio to fresh state."""
    initial_balance = request.initial_balance if request else 10000.0
    result = trader_service.reset_portfolio(initial_balance)
    if result['success']:
        return PortfolioResponse(success=True, data=result['data'])
    return PortfolioResponse(success=False, data={}, error=result.get('error'))
