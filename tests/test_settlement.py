"""
Comprehensive settlement testing to verify all 6 reported problems are fixed.

Tests the complete settlement flow from bet placement to history tracking.
"""

import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock, Mock
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from pathlib import Path

from poly_market_trader.storage.bet_tracker import BetTracker
from poly_market_trader.services.paper_trader import PaperTrader
from poly_market_trader.services.order_executor import OrderExecutor
from poly_market_trader.models.portfolio import Portfolio
from poly_market_trader.models.trade import MarketDirection, TradeType
from poly_market_trader.api.chainlink_data_provider import ChainlinkDataProvider


class TestBetSettlement(unittest.TestCase):
    """Test bet settlement fixes all 6 reported problems"""
    
    def setUp(self):
        """Set up test fixtures before each test"""
        # Create temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        self.storage_dir = os.path.join(self.test_dir, 'data')
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Initialize components
        self.portfolio = Portfolio(initial_balance=Decimal('10000.00'))
        self.order_executor = OrderExecutor(self.portfolio)
        self.bet_tracker = BetTracker(storage_dir=self.storage_dir)
        
        # Mock ChainlinkDataProvider
        self.mock_chainlink = MagicMock(spec=ChainlinkDataProvider)
        
    def tearDown(self):
        """Clean up after each test"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_problem_6_bet_history_empty(self):
        """
        PROBLEM 6: Bet History table stays empty - no bets ever appear in history
        
        This test verifies that bet_history.json is created and populated when bets settle.
        """
        print("\n=== Testing PROBLEM 6: Bet History Empty ===")
        
        # Verify bet_history.json exists (auto-created by BetTracker) and is empty initially
        bet_history_file = os.path.join(self.storage_dir, 'bet_history.json')
        self.assertTrue(os.path.exists(bet_history_file),
                       "bet_history.json should exist (auto-created by BetTracker)")
        
        # Verify file is empty initially
        with open(bet_history_file, 'r') as f:
            data = json.load(f)
        self.assertEqual(len(data.get('bets', [])), 0,
                        "bet_history.json should have 0 bets initially")
        
        # Create a bet that ended 10 minutes ago (ready for settlement)
        past_time = datetime.now(timezone.utc) - timedelta(minutes=15)
        end_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        bet_info = {
            'market_id': 'test_market_1',
            'question': 'Bitcoin Up or Down - Test',
            'crypto_name': 'bitcoin',
            'outcome': 'YES',
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': past_time.isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 50000.0
        }
        
        # Add bet to active bets
        bet_id = self.bet_tracker.add_active_bet(bet_info)
        print(f"Created bet: {bet_id}")
        
        # Verify bet is in active_bets
        active_bets = self.bet_tracker.get_active_bets()
        self.assertEqual(len(active_bets), 1, "Should have 1 active bet")
        
        # Mock price data - price went up (winning bet)
        self.mock_chainlink.get_price_at_time.side_effect = [50000.0, 51000.0]
        
        # Settle the bet
        print("Settling bet...")
        result = self.bet_tracker.settle_bet(
            bet_id=bet_id,
            chainlink_data=self.mock_chainlink,
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )
        
        print(f"Settlement result: {result}")
        
        # FIX PROBLEM 6: Verify bet_history.json was created
        self.assertTrue(os.path.exists(bet_history_file), 
                       "bet_history.json should be created after settlement")
        
        # Verify bet moved to history
        history = self.bet_tracker.get_bet_history()
        self.assertEqual(len(history), 1, "Should have 1 bet in history")
        self.assertEqual(history[0]['status'], 'won', "Bet should be marked as won")
        
        # Verify bet removed from active
        active_bets = self.bet_tracker.get_active_bets()
        self.assertEqual(len(active_bets), 0, "Should have 0 active bets after settlement")
        
        print("✅ PROBLEM 6 FIXED: Bet history is populated")
    
    def test_problem_2_active_bets_not_settling(self):
        """
        PROBLEM 2: Active Bets table - shows 'Settled' status but bets never actually settle
        
        This test verifies bets are removed from active_bets.json after settlement.
        """
        print("\n=== Testing PROBLEM 2: Active Bets Not Settling ===")
        
        # Create bet that ended 10 minutes ago
        end_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        bet_info = {
            'market_id': 'test_market_2',
            'question': 'Ethereum Up or Down - Test',
            'crypto_name': 'ethereum',
            'outcome': 'NO',
            'quantity': 200.0,
            'entry_price': 0.60,
            'cost': 120.0,
            'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 3000.0
        }
        
        bet_id = self.bet_tracker.add_active_bet(bet_info)
        
        # Mock price decrease (winning bet for NO)
        self.mock_chainlink.get_price_at_time.side_effect = [3000.0, 2900.0]
        
        # Settle using settle_all_ready_bets
        print("Calling settle_all_ready_bets...")
        results = self.bet_tracker.settle_all_ready_bets(
            chainlink_data=self.mock_chainlink,
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )
        
        print(f"Settled {len(results)} bets")
        
        # FIX PROBLEM 2: Verify bet was actually settled
        self.assertEqual(len(results), 1, "Should settle 1 bet")
        self.assertTrue(results[0]['success'], "Settlement should succeed")
        
        # Verify active bets is now empty
        active_bets = self.bet_tracker.get_active_bets()
        self.assertEqual(len(active_bets), 0, 
                        "Active bets should be empty after settlement")
        
        print("✅ PROBLEM 2 FIXED: Active bets settle properly")
    
    def test_problem_3_portfolio_value(self):
        """
        PROBLEM 3: Portfolio value going down and down - never recovers when won
        
        This test verifies portfolio balance increases when winning bets settle.
        """
        print("\n=== Testing PROBLEM 3: Portfolio Value ===")
        
        initial_balance = self.portfolio.current_balance
        print(f"Initial balance: ${initial_balance}")
        
        # Place a bet (balance should decrease)
        trade = self.order_executor.execute_trade(
            market_id='test_market_3',
            outcome=MarketDirection.YES,
            quantity=100.0,
            price=0.50,
            trade_type=TradeType.BUY
        )
        
        balance_after_bet = self.portfolio.current_balance
        print(f"Balance after bet: ${balance_after_bet}")
        self.assertEqual(balance_after_bet, initial_balance - Decimal('50.0'),
                        "Balance should decrease by bet cost")
        
        # Create bet record with past end time
        end_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        bet_info = {
            'market_id': 'test_market_3',
            'question': 'Solana Up or Down - Test',
            'crypto_name': 'solana',
            'outcome': 'YES',
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 100.0
        }
        
        bet_id = self.bet_tracker.add_active_bet(bet_info)
        
        # Mock price increase (winning bet)
        self.mock_chainlink.get_price_at_time.side_effect = [100.0, 110.0]
        
        # Settle the winning bet
        print("Settling winning bet...")
        result = self.bet_tracker.settle_bet(
            bet_id=bet_id,
            chainlink_data=self.mock_chainlink,
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )
        
        final_balance = self.portfolio.current_balance
        print(f"Final balance: ${final_balance}")
        
        # FIX PROBLEM 3: Verify balance increased (won $100 payout)
        expected_balance = initial_balance - Decimal('50.0') + Decimal('100.0')
        self.assertEqual(final_balance, expected_balance,
                        f"Balance should be {expected_balance} after winning bet")
        
        print(f"✅ PROBLEM 3 FIXED: Portfolio recovered to ${final_balance}")
    
    def test_problem_1_and_4_token_stats_and_win_loss(self):
        """
        PROBLEM 1: Token Performance table - all bets stay in 'pending'
        PROBLEM 4: Statistics show 0 wins 0 losses
        
        This test verifies wins/losses are tracked correctly in bet_history.
        """
        print("\n=== Testing PROBLEM 1 & 4: Token Stats and Win/Loss ===")
        
        # Create 2 bets: 1 winner, 1 loser
        end_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        # Bet 1: Winner
        bet1_info = {
            'market_id': 'test_market_4',
            'question': 'Bitcoin Up or Down - Test',
            'crypto_name': 'bitcoin',
            'outcome': 'YES',
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 50000.0
        }
        bet1_id = self.bet_tracker.add_active_bet(bet1_info)
        
        # Bet 2: Loser
        bet2_info = {
            'market_id': 'test_market_5',
            'question': 'Ethereum Up or Down - Test',
            'crypto_name': 'ethereum',
            'outcome': 'YES',
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 3000.0
        }
        bet2_id = self.bet_tracker.add_active_bet(bet2_info)
        
        # Settle bet 1 - price went up (WIN)
        self.mock_chainlink.get_price_at_time.side_effect = [50000.0, 51000.0]
        result1 = self.bet_tracker.settle_bet(bet1_id, self.mock_chainlink, 
                                             self.portfolio, self.order_executor)
        
        # Settle bet 2 - price went down (LOSS)
        self.mock_chainlink.get_price_at_time.side_effect = [3000.0, 2900.0]
        result2 = self.bet_tracker.settle_bet(bet2_id, self.mock_chainlink,
                                             self.portfolio, self.order_executor)
        
        # Check history
        history = self.bet_tracker.get_bet_history()
        print(f"Total bets in history: {len(history)}")
        
        # FIX PROBLEM 1 & 4: Verify wins and losses are recorded
        self.assertEqual(len(history), 2, "Should have 2 bets in history")
        
        wins = [b for b in history if b['status'] == 'won']
        losses = [b for b in history if b['status'] == 'lost']
        
        self.assertEqual(len(wins), 1, "Should have 1 win")
        self.assertEqual(len(losses), 1, "Should have 1 loss")
        
        print(f"✅ PROBLEM 1 & 4 FIXED: Tracked 1 win, 1 loss (not pending)")
    
    def test_problem_5_win_rate_calculation(self):
        """
        PROBLEM 5: Win Rate is not being calculated or displayed
        
        This test verifies win rate calculation from bet history.
        """
        print("\n=== Testing PROBLEM 5: Win Rate Calculation ===")
        
        # Create and settle 3 bets: 2 wins, 1 loss
        end_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        bets = [
            ('YES', [50000.0, 51000.0]),  # Win
            ('YES', [3000.0, 3100.0]),    # Win
            ('YES', [100.0, 90.0]),       # Loss
        ]
        
        for i, (outcome, prices) in enumerate(bets):
            bet_info = {
                'market_id': f'test_market_{i+10}',
                'question': f'Test Market {i}',
                'crypto_name': 'bitcoin',
                'outcome': outcome,
                'quantity': 100.0,
                'entry_price': 0.50,
                'cost': 50.0,
                'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
                'market_end_time': end_time.isoformat(),
                'entry_crypto_price': prices[0]
            }
            bet_id = self.bet_tracker.add_active_bet(bet_info)
            
            self.mock_chainlink.get_price_at_time.side_effect = prices
            self.bet_tracker.settle_bet(bet_id, self.mock_chainlink,
                                       self.portfolio, self.order_executor)
        
        # Get history and calculate win rate
        history = self.bet_tracker.get_bet_history()
        wins = sum(1 for b in history if b.get('status') == 'won')
        losses = sum(1 for b in history if b.get('status') == 'lost')
        total = wins + losses
        
        # FIX PROBLEM 5: Verify win rate calculation
        win_rate = (wins / total * 100) if total > 0 else 0.0
        
        print(f"Wins: {wins}, Losses: {losses}, Total: {total}")
        print(f"Win Rate: {win_rate:.1f}%")
        
        self.assertEqual(wins, 2, "Should have 2 wins")
        self.assertEqual(losses, 1, "Should have 1 loss")
        self.assertAlmostEqual(win_rate, 66.7, places=1, 
                              msg="Win rate should be 66.7%")
        
        print("✅ PROBLEM 5 FIXED: Win rate calculates correctly")
    
    def test_timezone_handling(self):
        """
        Test that timezone handling works correctly for settlement timing.
        
        This addresses the root cause of why settlements weren't happening.
        """
        print("\n=== Testing Timezone Handling ===")
        
        # Create bet with timezone-aware datetime
        end_time_utc = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        bet_info = {
            'market_id': 'test_tz',
            'question': 'Timezone Test',
            'crypto_name': 'bitcoin',
            'outcome': 'YES',
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': (end_time_utc - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time_utc.isoformat(),  # ISO format with timezone
            'entry_crypto_price': 50000.0
        }
        
        bet_id = self.bet_tracker.add_active_bet(bet_info)
        
        # Mock price data
        self.mock_chainlink.get_price_at_time.side_effect = [50000.0, 51000.0]
        
        # Try to settle - should work because bet is past settlement buffer
        results = self.bet_tracker.settle_all_ready_bets(
            chainlink_data=self.mock_chainlink,
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )
        
        print(f"Settlement results: {results}")
        
        self.assertEqual(len(results), 1, "Should settle the bet")
        self.assertTrue(results[0]['success'], "Settlement should succeed")
        
        print("✅ Timezone handling works correctly")


class TestBetSettlementTimings(unittest.TestCase):
    """Test settlement buffer timing logic"""
    
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
    
    def test_settlement_buffer_not_ready(self):
        """Test that bets don't settle before buffer period expires"""
        print("\n=== Testing Settlement Buffer (Not Ready) ===")
        
        # Create bet that ended 3 minutes ago (not past 5min buffer)
        end_time = datetime.now(timezone.utc) - timedelta(minutes=3)
        
        bet_info = {
            'market_id': 'test_buffer',
            'question': 'Buffer Test',
            'crypto_name': 'bitcoin',
            'outcome': 'YES',
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 50000.0
        }
        
        self.bet_tracker.add_active_bet(bet_info)
        
        # Try to settle - should not settle yet
        results = self.bet_tracker.settle_all_ready_bets(
            chainlink_data=self.mock_chainlink,
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )
        
        self.assertEqual(len(results), 0, 
                        "Should not settle bets before 5min buffer expires")
        
        # Verify bet still in active
        active = self.bet_tracker.get_active_bets()
        self.assertEqual(len(active), 1, "Bet should still be active")
        
        print("✅ Settlement buffer prevents premature settlement")
    
    def test_settlement_buffer_ready(self):
        """Test that bets settle after buffer period expires"""
        print("\n=== Testing Settlement Buffer (Ready) ===")
        
        # Create bet that ended 6 minutes ago (past 5min buffer)
        end_time = datetime.now(timezone.utc) - timedelta(minutes=6)
        
        bet_info = {
            'market_id': 'test_buffer_ready',
            'question': 'Buffer Ready Test',
            'crypto_name': 'bitcoin',
            'outcome': 'YES',
            'quantity': 100.0,
            'entry_price': 0.50,
            'cost': 50.0,
            'market_start_time': (end_time - timedelta(minutes=15)).isoformat(),
            'market_end_time': end_time.isoformat(),
            'entry_crypto_price': 50000.0
        }
        
        self.bet_tracker.add_active_bet(bet_info)
        
        # Mock price data
        self.mock_chainlink.get_price_at_time.side_effect = [50000.0, 51000.0]
        
        # Try to settle - should settle now
        results = self.bet_tracker.settle_all_ready_bets(
            chainlink_data=self.mock_chainlink,
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )
        
        self.assertEqual(len(results), 1, "Should settle bet after buffer expires")
        self.assertTrue(results[0]['success'], "Settlement should succeed")
        
        print("✅ Settlement buffer allows settlement after expiration")


if __name__ == '__main__':
    unittest.main(verbosity=2)
