"""
Test to verify settlement logic correctness for "Up or Down" markets.

This test ensures that our settlement logic correctly interprets Polymarket's
"Up or Down" questions where:
  - YES = Price went UP
  - NO = Price went DOWN (or stayed same)
"""

import unittest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import tempfile
import shutil
import os

from poly_market_trader.storage.bet_tracker import BetTracker
from poly_market_trader.models.portfolio import Portfolio
from poly_market_trader.services.order_executor import OrderExecutor
from poly_market_trader.api.chainlink_data_provider import ChainlinkDataProvider


class TestUpOrDownLogic(unittest.TestCase):
    """Verify that 'Up or Down' market logic is correct"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.storage_dir = os.path.join(self.test_dir, 'data')
        os.makedirs(self.storage_dir, exist_ok=True)
        
        self.portfolio = Portfolio(initial_balance=Decimal('10000.00'))
        self.order_executor = OrderExecutor(self.portfolio)
        self.bet_tracker = BetTracker(storage_dir=self.storage_dir)
        self.mock_chainlink = MagicMock(spec=ChainlinkDataProvider)
        
    def tearDown(self):
        """Clean up"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_price_went_up_yes_wins(self):
        """
        Market: 'Bitcoin Up or Down'
        User bets: YES (betting price will go UP)
        Price goes: UP (50000 -> 51000)
        Expected: User WINS
        """
        print("\n=== Test: Price UP, User bets YES ===")
        
        end_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        bet_info = {
            'market_id': 'test_up_yes',
            'question': 'Bitcoin Up or Down - Test',
            'crypto_name': 'bitcoin',
            'outcome': 'YES',  # User betting price will go UP
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 50000.0
        }
        
        bet_id = self.bet_tracker.add_active_bet(bet_info)
        
        # Mock: Price went UP (50000 -> 51000)
        self.mock_chainlink.get_price_at_time.side_effect = [50000.0, 51000.0]
        
        result = self.bet_tracker.settle_bet(
            bet_id=bet_id,
            chainlink_data=self.mock_chainlink,
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )
        
        # Verify user WON
        self.assertTrue(result['success'], "Settlement should succeed")
        self.assertEqual(result['status'], 'won', "User should WIN (bet YES, price went UP)")
        self.assertEqual(result['payout'], 100.0, "Payout should be $100 (100 shares * $1)")
        self.assertEqual(result['profit_loss'], 50.0, "Profit should be $50 ($100 payout - $50 cost)")
        
        print("✅ CORRECT: User bet YES, price went UP → User WON")
    
    def test_price_went_up_no_loses(self):
        """
        Market: 'Bitcoin Up or Down'
        User bets: NO (betting price will go DOWN)
        Price goes: UP (50000 -> 51000)
        Expected: User LOSES
        """
        print("\n=== Test: Price UP, User bets NO ===")
        
        end_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        bet_info = {
            'market_id': 'test_up_no',
            'question': 'Bitcoin Up or Down - Test',
            'crypto_name': 'bitcoin',
            'outcome': 'NO',  # User betting price will go DOWN
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 50000.0
        }
        
        bet_id = self.bet_tracker.add_active_bet(bet_info)
        
        # Mock: Price went UP (50000 -> 51000)
        self.mock_chainlink.get_price_at_time.side_effect = [50000.0, 51000.0]
        
        result = self.bet_tracker.settle_bet(
            bet_id=bet_id,
            chainlink_data=self.mock_chainlink,
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )
        
        # Verify user LOST
        self.assertTrue(result['success'], "Settlement should succeed")
        self.assertEqual(result['status'], 'lost', "User should LOSE (bet NO, price went UP)")
        self.assertEqual(result['payout'], 0.0, "Payout should be $0 (lost bet)")
        self.assertEqual(result['profit_loss'], -50.0, "Loss should be -$50 (lost entire cost)")
        
        print("✅ CORRECT: User bet NO, price went UP → User LOST")
    
    def test_price_went_down_no_wins(self):
        """
        Market: 'Bitcoin Up or Down'
        User bets: NO (betting price will go DOWN)
        Price goes: DOWN (50000 -> 49000)
        Expected: User WINS
        """
        print("\n=== Test: Price DOWN, User bets NO ===")
        
        end_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        bet_info = {
            'market_id': 'test_down_no',
            'question': 'Bitcoin Up or Down - Test',
            'crypto_name': 'bitcoin',
            'outcome': 'NO',  # User betting price will go DOWN
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 50000.0
        }
        
        bet_id = self.bet_tracker.add_active_bet(bet_info)
        
        # Mock: Price went DOWN (50000 -> 49000)
        self.mock_chainlink.get_price_at_time.side_effect = [50000.0, 49000.0]
        
        result = self.bet_tracker.settle_bet(
            bet_id=bet_id,
            chainlink_data=self.mock_chainlink,
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )
        
        # Verify user WON
        self.assertTrue(result['success'], "Settlement should succeed")
        self.assertEqual(result['status'], 'won', "User should WIN (bet NO, price went DOWN)")
        self.assertEqual(result['payout'], 100.0, "Payout should be $100")
        self.assertEqual(result['profit_loss'], 50.0, "Profit should be $50")
        
        print("✅ CORRECT: User bet NO, price went DOWN → User WON")
    
    def test_price_went_down_yes_loses(self):
        """
        Market: 'Bitcoin Up or Down'
        User bets: YES (betting price will go UP)
        Price goes: DOWN (50000 -> 49000)
        Expected: User LOSES
        """
        print("\n=== Test: Price DOWN, User bets YES ===")
        
        end_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        bet_info = {
            'market_id': 'test_down_yes',
            'question': 'Bitcoin Up or Down - Test',
            'crypto_name': 'bitcoin',
            'outcome': 'YES',  # User betting price will go UP
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 50000.0
        }
        
        bet_id = self.bet_tracker.add_active_bet(bet_info)
        
        # Mock: Price went DOWN (50000 -> 49000)
        self.mock_chainlink.get_price_at_time.side_effect = [50000.0, 49000.0]
        
        result = self.bet_tracker.settle_bet(
            bet_id=bet_id,
            chainlink_data=self.mock_chainlink,
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )
        
        # Verify user LOST
        self.assertTrue(result['success'], "Settlement should succeed")
        self.assertEqual(result['status'], 'lost', "User should LOSE (bet YES, price went DOWN)")
        self.assertEqual(result['payout'], 0.0, "Payout should be $0")
        self.assertEqual(result['profit_loss'], -50.0, "Loss should be -$50")
        
        print("✅ CORRECT: User bet YES, price went DOWN → User LOST")
    
    def test_price_stayed_same_no_wins(self):
        """
        Market: 'Bitcoin Up or Down'
        User bets: NO (betting price will go DOWN/SAME)
        Price: STAYS SAME (50000 -> 50000)
        Expected: User WINS (because NO includes 'or stayed same')
        """
        print("\n=== Test: Price SAME, User bets NO ===")
        
        end_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        bet_info = {
            'market_id': 'test_same_no',
            'question': 'Bitcoin Up or Down - Test',
            'crypto_name': 'bitcoin',
            'outcome': 'NO',  # User betting price will NOT go up
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 50000.0
        }
        
        bet_id = self.bet_tracker.add_active_bet(bet_info)
        
        # Mock: Price STAYED SAME (50000 -> 50000)
        self.mock_chainlink.get_price_at_time.side_effect = [50000.0, 50000.0]
        
        result = self.bet_tracker.settle_bet(
            bet_id=bet_id,
            chainlink_data=self.mock_chainlink,
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )
        
        # Verify user WON (NO wins when price doesn't go up)
        self.assertTrue(result['success'], "Settlement should succeed")
        self.assertEqual(result['status'], 'won', "User should WIN (bet NO, price stayed same)")
        self.assertEqual(result['payout'], 100.0, "Payout should be $100")
        self.assertEqual(result['profit_loss'], 50.0, "Profit should be $50")
        
        print("✅ CORRECT: User bet NO, price stayed SAME → User WON")


if __name__ == '__main__':
    unittest.main(verbosity=2)
