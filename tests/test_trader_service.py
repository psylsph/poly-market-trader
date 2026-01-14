import unittest
from unittest.mock import patch, MagicMock
import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.append(os.getcwd())

from poly_market_trader.web.services.trader_service import TraderService
from poly_market_trader.services.paper_trader import PaperTrader

class TestTraderService(unittest.TestCase):
    def setUp(self):
        # Patch PaperTrader to avoid real initialization
        with patch('poly_market_trader.web.services.trader_service.PaperTrader') as mock_trader_cls:
            self.mock_trader = MagicMock(spec=PaperTrader)
            mock_trader_cls.return_value = self.mock_trader
            
            # Re-initialize the service (it's a singleton, so reset instance)
            TraderService._instance = None
            self.service = TraderService()

    def test_get_portfolio_summary(self):
        """Test getting portfolio summary"""
        mock_summary = {
            "current_balance": 10000.0,
            "total_value": 10000.0,
            "pnl": 0.0,
            "roi": 0.0,
            "positions_count": 0,
            "trade_count": 0
        }
        self.mock_trader.get_portfolio_summary.return_value = mock_summary
        self.mock_trader.get_bet_history.return_value = []
        
        # Setup mock portfolio attributes needed
        self.mock_trader.portfolio = MagicMock()
        self.mock_trader.portfolio.trade_history = []
        self.mock_trader.portfolio.initial_balance = Decimal('10000.0')
        self.mock_trader.portfolio.current_balance = Decimal('10000.0')
        
        result = self.service.get_portfolio_summary()
        
        # If failure, print error
        if not result['success']:
            print(f"Error in test: {result.get('error')}")
            
        self.assertTrue(result['success'])
        # Compare data fields (excluding those we didn't mock perfectly like timestamps)
        self.assertEqual(result['data']['current_balance'], 10000.0)
        self.assertEqual(result['data']['initial_balance'], 10000.0)
        self.mock_trader.get_portfolio_summary.assert_called_once()

    def test_get_active_bets(self):
        """Test getting active bets"""
        mock_bets = [{"bet_id": "123", "market_id": "m1"}]
        self.mock_trader.get_active_bets.return_value = mock_bets
        
        result = self.service.get_active_bets()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['bets'], mock_bets)
        self.assertEqual(result['data']['count'], 1)

    def test_place_bet_success(self):
        """Test placing a bet successfully"""
        self.mock_trader.place_crypto_bet.return_value = True
        
        result = self.service.place_bet(
            market_id="test_market",
            outcome="YES",
            amount=100.0,
            max_price=0.99
        )
        
        self.assertTrue(result['success'])
        self.mock_trader.place_crypto_bet.assert_called_once()

    def test_place_bet_failure(self):
        """Test placing a bet failure"""
        self.mock_trader.place_crypto_bet.return_value = False
        
        result = self.service.place_bet(
            market_id="test_market",
            outcome="YES",
            amount=100.0,
            max_price=0.99
        )
        
        self.assertFalse(result['success'])
        
    def test_settle_bets(self):
        """Test settling bets"""
        mock_settle_result = {"count": 2, "settled": ["bet1", "bet2"]}
        self.mock_trader.settle_bets.return_value = mock_settle_result
        
        result = self.service.settle_bets()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['count'], 2)
        # Verify static tracking variables were updated (we can't easily check private class vars, but we trust the code)

if __name__ == '__main__':
    unittest.main()
