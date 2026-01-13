"""
Bets API Routes.

Endpoints for bet management, history, and actions.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from ..services.trader_service import TraderService

router = APIRouter(prefix="/api/bets", tags=["Bets"])
trader_service = TraderService()


class BetResponse(BaseModel):
    """Bets response."""
    success: bool
    data: dict
    message: Optional[str] = None
    error: Optional[str] = None


class PlaceBetRequest(BaseModel):
    """Request body for placing a bet."""
    market_id: str = Field(..., description="Market ID or keyword to identify the market")
    outcome: str = Field(..., pattern="^(YES|NO)$", description="Bet outcome")
    amount: float = Field(..., gt=0, le=10000, description="Amount to risk in USD")
    max_price: float = Field(default=1.0, ge=0.01, le=1.0, description="Maximum price to pay")
    use_chainlink_analysis: bool = Field(default=True, description="Use Chainlink data for analysis")


class OfferActionRequest(BaseModel):
    """Request body for offer actions."""
    offer_id: str = Field(..., description="Offer ID to action")


@router.get("/active")
async def get_active_bets() -> BetResponse:
    """Get all active bets awaiting settlement."""
    result = trader_service.get_active_bets()
    if result['success']:
        return BetResponse(success=True, data=result['data'])
    return BetResponse(success=False, data={}, error=result.get('error'))


@router.get("/history")
async def get_bet_history(
    limit: int = Query(default=50, ge=1, le=500),
    status: Optional[str] = Query(default=None, pattern="^(won|lost|active)$")
) -> BetResponse:
    """Get bet history with optional filtering."""
    result = trader_service.get_bet_history(limit=limit, status_filter=status)
    if result['success']:
        return BetResponse(success=True, data=result['data'])
    return BetResponse(success=False, data={}, error=result.get('error'))


@router.post("/place")
async def place_bet(request: PlaceBetRequest) -> BetResponse:
    """Place a new bet on a market."""
    result = trader_service.place_bet(
        market_id=request.market_id,
        outcome=request.outcome,
        amount=request.amount,
        max_price=request.max_price,
        use_chainlink_analysis=request.use_chainlink_analysis
    )
    if result['success']:
        return BetResponse(success=True, data=result.get('data', {}), message=result.get('message'))
    return BetResponse(success=False, data={}, error=result.get('error'))


@router.post("/settle")
async def settle_bets() -> BetResponse:
    """Manually trigger settlement of ready bets."""
    result = trader_service.settle_bets()
    if result['success']:
        return BetResponse(success=True, data=result.get('data', {}), message=result.get('message'))
    return BetResponse(success=False, data={}, error=result.get('error'))


@router.get("/offers")
async def get_offers() -> BetResponse:
    """Get pending bet offers."""
    result = trader_service.get_pending_offers()
    if result['success']:
        return BetResponse(success=True, data=result['data'])
    return BetResponse(success=False, data={}, error=result.get('error'))


@router.post("/offers/{offer_id}/accept")
async def accept_offer(offer_id: str) -> BetResponse:
    """Accept a bet offer."""
    result = trader_service.accept_offer(offer_id)
    if result['success']:
        return BetResponse(success=True, data={}, message=result.get('message'))
    return BetResponse(success=False, data={}, error=result.get('error'))


@router.post("/offers/{offer_id}/skip")
async def skip_offer(offer_id: str) -> BetResponse:
    """Skip a bet offer."""
    result = trader_service.skip_offer(offer_id)
    if result['success']:
        return BetResponse(success=True, data={}, message=result.get('message'))
    return BetResponse(success=False, data={}, error=result.get('error'))


@router.post("/offers/skip-all")
async def skip_all_offers() -> BetResponse:
    """Skip all pending offers."""
    result = trader_service.skip_all_offers()
    if result['success']:
        return BetResponse(success=True, data={}, message=result.get('message'))
    return BetResponse(success=False, data={}, error=result.get('error'))


class AutoBetRequest(BaseModel):
    """Request body for auto-bet settings."""
    crypto_name: str = Field(..., description="Cryptocurrency to bet on (e.g., bitcoin)")
    amount: float = Field(default=100, gt=1, le=10000, description="Amount per bet")
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="Minimum confidence to bet")
    timeframe: str = Field(default="15min", pattern="^(15min|1h|daily)$", description="Analysis timeframe")


class AutoBetStatusResponse(BaseModel):
    """Auto-bet status response."""
    success: bool
    data: dict
    error: Optional[str] = None


@router.get("/auto/status")
async def get_auto_bet_status() -> AutoBetStatusResponse:
    """Get auto-betting status."""
    result = trader_service.get_auto_betting_status()
    if result['success']:
        return AutoBetStatusResponse(success=True, data=result['data'])
    return AutoBetStatusResponse(success=False, data={}, error=result.get('error'))


@router.post("/auto/start")
async def start_auto_bet(request: AutoBetRequest = None) -> BetResponse:
    """Start auto-betting with specified settings."""
    crypto = request.crypto_name if request else 'bitcoin'
    amount = request.amount if request else 100
    confidence = request.confidence_threshold if request else 0.6
    timeframe = request.timeframe if request else '15min'
    
    result = trader_service.start_auto_betting(
        interval_seconds=900,
        confidence_threshold=confidence
    )
    if result['success']:
        return BetResponse(success=True, data=result.get('data', {}), message=result.get('message'))
    return BetResponse(success=False, data={}, error=result.get('error'))


@router.post("/auto/stop")
async def stop_auto_bet() -> BetResponse:
    """Stop auto-betting."""
    result = trader_service.stop_auto_betting()
    if result['success']:
        return BetResponse(success=True, data=result.get('data', {}), message=result.get('message'))
    return BetResponse(success=False, data={}, error=result.get('error'))


@router.post("/auto/place")
async def place_informed_bet(request: AutoBetRequest) -> BetResponse:
    """Place a single informed bet based on Chainlink analysis."""
    result = trader_service.place_informed_bet(
        crypto_name=request.crypto_name,
        amount=request.amount,
        confidence_threshold=request.confidence_threshold,
        timeframe=request.timeframe
    )
    if result['success']:
        return BetResponse(success=True, data=result.get('data', {}), message=result.get('message'))
    return BetResponse(success=False, data={}, error=result.get('error'))
