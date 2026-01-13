"""
Web Routes - API endpoint definitions.
"""

from .portfolio import router as portfolio_router
from .markets import router as markets_router
from .bets import router as bets_router

__all__ = ['portfolio_router', 'markets_router', 'bets_router']
