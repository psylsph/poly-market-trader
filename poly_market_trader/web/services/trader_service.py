"""
Trader Service - Bridge between Web API and PaperTrader core.

Provides a clean interface for the web API to access trading functionality
without directly exposing the PaperTrader implementation details.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Any
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from poly_market_trader.models.trade import MarketDirection
from poly_market_trader.services.paper_trader import PaperTrader


class TraderService:
    """
    Service layer that wraps PaperTrader for use by web endpoints.
    
    Handles the lifecycle of the PaperTrader instance and provides
    a clean API for web consumption.
    """
    
    _instance: Optional['TraderService'] = None
    _trader: Optional[PaperTrader] = None
    _last_settlement_time: Optional[datetime] = None
    _last_settlement_count: int = 0
    _last_settlement_error: Optional[str] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._trader is None:
            self._initialize_trader()
    
    def _initialize_trader(self, initial_balance: Decimal = None) -> None:
        """Initialize or reinitialize the PaperTrader instance."""
        if initial_balance is None:
            initial_balance = Decimal(str(10000))
        self._trader = PaperTrader(initial_balance=initial_balance, auto_load=True)
    
    @property
    def trader(self) -> PaperTrader:
        """Get the PaperTrader instance, initializing if necessary."""
        if self._trader is None:
            self._initialize_trader()
        return self._trader
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary including balance, P&L, and statistics."""
        try:
            summary = self.trader.get_portfolio_summary()
            
            bet_history = self.trader.get_bet_history()
            total_bets = len(bet_history)
            wins = sum(1 for b in bet_history if b.get('status') == 'won')
            losses = sum(1 for b in bet_history if b.get('status') == 'lost')
            win_rate = (wins / total_bets * 100) if total_bets > 0 else 0.0
            
            # Also get trade history for overall stats
            trade_history = self.trader.portfolio.trade_history
            total_trades = len(trade_history)
            
            initial_balance = float(self.trader.portfolio.initial_balance)
            current_balance = float(self.trader.portfolio.current_balance)
            invested = initial_balance - current_balance
            
            return {
                'success': True,
                'data': {
                    'current_balance': summary.get('current_balance', 0.0),
                    'total_value': summary.get('total_value', 0.0),
                    'pnl': summary.get('pnl', 0.0),
                    'roi': summary.get('pnl', 0.0) / initial_balance * 100 if initial_balance > 0 else 0.0,
                    'positions_count': summary.get('positions_count', 0),
                    'trades_count': summary.get('trade_count', 0),
                    'initial_balance': initial_balance,
                    'invested': invested,
                    'total_bets': total_bets,
                    'wins': wins,
                    'losses': losses,
                    'win_rate': win_rate,
                    'total_trades': total_trades
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_positions(self) -> Dict[str, Any]:
        """Get all active positions."""
        try:
            positions = []
            for pos in self.trader.portfolio.positions:
                positions.append({
                    'market_id': pos.market_id,
                    'outcome': pos.outcome.value,
                    'quantity': pos.quantity,
                    'avg_price': pos.avg_price,
                    'current_value': pos.quantity * pos.avg_price,
                    'entry_time': pos.entry_time.isoformat() if pos.entry_time else None
                })
            
            return {
                'success': True,
                'data': {
                    'positions': positions,
                    'count': len(positions)
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_active_bets(self) -> Dict[str, Any]:
        """Get all active bets awaiting settlement."""
        try:
            bets = self.trader.get_active_bets()
            return {
                'success': True,
                'data': {
                    'bets': bets,
                    'count': len(bets)
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_bet_history(self, limit: int = 50, status_filter: str = None) -> Dict[str, Any]:
        """Get bet history with optional filtering."""
        try:
            bets = self.trader.get_bet_history(limit=limit, status_filter=status_filter)
            return {
                'success': True,
                'data': {
                    'bets': bets,
                    'count': len(bets)
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_markets(self, limit: int = 20) -> Dict[str, Any]:
        """Get available crypto markets."""
        try:
            markets = self.trader.get_crypto_markets()
            return {
                'success': True,
                'data': {
                    'markets': markets[:limit],
                    'count': len(markets[:limit]),
                    'total_available': len(markets)
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def place_bet(self, market_id: str, outcome: str, amount: float, 
                  max_price: float = 1.0, use_chainlink_analysis: bool = True) -> Dict[str, Any]:
        """
        Place a bet on a market.
        
        Args:
            market_id: The market ID to bet on
            outcome: 'YES' or 'NO'
            amount: Amount to risk in USD
            max_price: Maximum price to pay for outcome token
            use_chainlink_analysis: Whether to use Chainlink data
            
        Returns:
            Dict with success status and result
        """
        try:
            direction = MarketDirection.YES if outcome.upper() == 'YES' else MarketDirection.NO
            
            result = self.trader.place_crypto_bet(
                market_title_keyword=market_id,
                outcome=direction,
                amount=amount,
                max_price=max_price,
                use_chainlink_analysis=use_chainlink_analysis
            )
            
            return {
                'success': result,
                'message': 'Bet placed successfully' if result else 'Bet placement failed',
                'data': {'market_id': market_id, 'outcome': outcome, 'amount': amount}
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def settle_bets(self) -> Dict[str, Any]:
        """Manually trigger settlement of ready bets."""
        try:
            results = self.trader.settle_bets()
            TraderService._last_settlement_time = datetime.now()
            TraderService._last_settlement_count = results.get("count", 0)
            TraderService._last_settlement_error = None
            
            return {
                'success': True,
                'message': f'Settled {results.get("count", 0)} bets',
                'data': results
            }
        except Exception as e:
            TraderService._last_settlement_time = datetime.now()
            TraderService._last_settlement_error = str(e)
            return {'success': False, 'error': str(e)}
    
    def reset_portfolio(self, initial_balance: float = 10000.0) -> Dict[str, Any]:
        """Reset portfolio to fresh state."""
        try:
            self.trader.reset_portfolio(Decimal(str(initial_balance)))
            self._trader = None  # Force reinitialization
            
            return {
                'success': True,
                'message': f'Portfolio reset to ${initial_balance:.2f}',
                'data': {'initial_balance': initial_balance}
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_chainlink_analysis(self, crypto_name: str, timeframe: str = '15min') -> Dict[str, Any]:
        """Get Chainlink analysis for a cryptocurrency."""
        try:
            analysis = self.trader.get_chainlink_analysis(crypto_name, timeframe=timeframe)
            return {
                'success': True,
                'data': {
                    'crypto_name': crypto_name,
                    'timeframe': timeframe,
                    'current_price': analysis.get('current_price'),
                    'trend': analysis.get('trend'),
                    'indicators': analysis.get('indicators', {})
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_token_statistics(self) -> Dict[str, Any]:
        """Get token performance statistics from trades and active bets."""
        try:
            trade_history = self.trader.portfolio.trade_history
            active_bets_result = self.get_active_bets()
            bet_history_result = self.get_bet_history()
            
            active_bets = active_bets_result.get('data', {}).get('bets', [])
            bet_history_bets = bet_history_result.get('data', {}).get('bets', [])
            
            market_crypto_map = {}
            for bet in active_bets:
                mid = bet.get('market_id', '')
                crypto = bet.get('crypto_name', 'unknown')
                if mid and mid not in market_crypto_map:
                    market_crypto_map[mid] = crypto
            
            for bet in bet_history_bets:
                mid = bet.get('market_id', '')
                crypto = bet.get('crypto_name', 'unknown')
                if mid and mid not in market_crypto_map:
                    market_crypto_map[mid] = crypto
            
            settled_bets_by_token = {}
            settled_bet_ids = set()
            
            for settled_bet in bet_history_bets:
                bet_id = settled_bet.get('bet_id')
                if bet_id:
                    settled_bet_ids.add(bet_id)
                    
                market_id = settled_bet.get('market_id', '')
                crypto_name = market_crypto_map.get(market_id, market_id)
                status = settled_bet.get('status', 'pending')
                
                if crypto_name not in settled_bets_by_token:
                    settled_bets_by_token[crypto_name] = {
                        'token': crypto_name,
                        'total_bets': 0,
                        'wins': 0,
                        'losses': 0,
                        'pending': 0,
                        'total_pnl': 0.0,
                        'total_invested': 0.0
                    }
                
                stats = settled_bets_by_token[crypto_name]
                stats['total_bets'] += 1
                
                if status == 'won':
                    stats['wins'] += 1
                elif status == 'lost':
                    stats['losses'] += 1
                else:
                    stats['pending'] += 1
                
                pnl = settled_bet.get('profit_loss', 0) or 0
                cost = settled_bet.get('cost', 0) or 0
                stats['total_pnl'] += float(pnl)
                stats['total_invested'] += float(cost)
            
            for bet in active_bets:
                # Skip if already settled (redundancy check)
                if bet.get('bet_id') in settled_bet_ids:
                    continue
                    
                market_id = bet.get('market_id', '')
                crypto_name = bet.get('crypto_name', 'unknown')
                cost = float(bet.get('cost', 0))
                
                if crypto_name not in settled_bets_by_token:
                    settled_bets_by_token[crypto_name] = {
                        'token': crypto_name,
                        'total_bets': 0,
                        'wins': 0,
                        'losses': 0,
                        'pending': 0,
                        'total_pnl': 0.0,
                        'total_invested': 0.0
                    }
                
                stats = settled_bets_by_token[crypto_name]
                stats['pending'] += 1
                stats['total_invested'] += cost
            
            for stats in settled_bets_by_token.values():
                settled_count = stats['wins'] + stats['losses']
                stats['total_bets'] = settled_count + stats['pending']
                stats['win_rate'] = (stats['wins'] / settled_count * 100) if settled_count > 0 else 0.0
                stats['roi'] = (stats['total_pnl'] / stats['total_invested'] * 100) if stats['total_invested'] > 0 else 0.0
            
            sorted_tokens = sorted(settled_bets_by_token.values(), key=lambda x: x['total_bets'], reverse=True)
            
            return {
                'success': True,
                'data': {
                    'statistics': sorted_tokens,
                    'count': len(sorted_tokens)
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_pending_offers(self) -> Dict[str, Any]:
        """Get pending bet offers."""
        try:
            offers = self.trader.get_pending_offers()
            return {
                'success': True,
                'data': {
                    'offers': offers,
                    'count': len(offers)
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all data needed for the dashboard in a single call."""
        try:
            portfolio = self.get_portfolio_summary()
            positions = self.get_positions()
            active_bets = self.get_active_bets()
            bet_history = self.get_bet_history(limit=10)
            token_stats = self.get_token_statistics()
            markets = self.get_markets(limit=10)
            
            # Add settlement status
            settlement_status = {
                'last_check': TraderService._last_settlement_time.isoformat() if TraderService._last_settlement_time else None,
                'last_count': TraderService._last_settlement_count,
                'last_error': TraderService._last_settlement_error
            }
            
            return {
                'success': True,
                'data': {
                    'portfolio': portfolio.get('data', {}),
                    'positions': positions.get('data', {}),
                    'active_bets': active_bets.get('data', {}),
                    'recent_bets': bet_history.get('data', {}),
                    'token_stats': token_stats.get('data', {}),
                    'markets': markets.get('data', {}),
                    'settlement': settlement_status
                },
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def accept_offer(self, offer_id: str) -> Dict[str, Any]:
        """Accept a bet offer."""
        try:
            self.trader.accept_offer(offer_id)
            return {
                'success': True,
                'message': f'Offer {offer_id} accepted'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def skip_offer(self, offer_id: str) -> Dict[str, Any]:
        """Skip a bet offer."""
        try:
            self.trader.skip_offer(offer_id)
            return {
                'success': True,
                'message': f'Offer {offer_id} skipped'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def skip_all_offers(self) -> Dict[str, Any]:
        """Skip all pending offers."""
        try:
            self.trader.skip_all_offers()
            return {
                'success': True,
                'message': 'All offers skipped'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def start_auto_betting(self, interval_seconds: int = 900, confidence_threshold: float = 0.6) -> Dict[str, Any]:
        """Start auto-betting loop."""
        try:
            self.trader.start_auto_betting(check_interval_seconds=interval_seconds)
            return {
                'success': True,
                'message': f'Auto-betting started (interval: {interval_seconds}s, threshold: {confidence_threshold})',
                'data': {'running': True, 'interval': interval_seconds, 'confidence': confidence_threshold}
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def stop_auto_betting(self) -> Dict[str, Any]:
        """Stop auto-betting loop."""
        try:
            self.trader.stop_auto_betting()
            return {
                'success': True,
                'message': 'Auto-betting stopped',
                'data': {'running': False}
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_auto_betting_status(self) -> Dict[str, Any]:
        """Get auto-betting status."""
        try:
            status = self.trader.get_auto_betting_status()
            return {
                'success': True,
                'data': status
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def place_informed_bet(self, crypto_name: str, amount: float, 
                           confidence_threshold: float = 0.6, timeframe: str = '15min') -> Dict[str, Any]:
        """Place an informed bet based on Chainlink analysis."""
        try:
            result = self.trader.place_informed_crypto_bet(
                market_title_keyword=crypto_name,
                amount=amount,
                max_price=1.0,
                confidence_threshold=confidence_threshold,
                timeframe=timeframe
            )
            return {
                'success': result,
                'message': 'Bet placed' if result else 'Bet not placed (confidence too low or no market)',
                'data': {'crypto': crypto_name, 'amount': amount}
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
