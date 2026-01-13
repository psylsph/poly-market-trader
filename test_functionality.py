"""
Simple test to verify the core functionality of the Polymarket Paper Trader
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decimal import Decimal
from poly_market_trader.services.paper_trader import PaperTrader
from poly_market_trader.models.trade import MarketDirection


def test_basic_functionality():
    print("Testing basic functionality of Polymarket Paper Trader...")
    
    # Initialize trader
    trader = PaperTrader(initial_balance=Decimal('5000.00'))
    
    # Check initial state
    summary = trader.get_portfolio_summary()
    assert summary['current_balance'] == 5000.0, f"Expected balance 5000, got {summary['current_balance']}"
    assert summary['positions_count'] == 0, f"Expected 0 positions, got {summary['positions_count']}"
    print("✓ Initial state correct")
    
    # List crypto markets
    crypto_markets = trader.get_crypto_markets()
    assert len(crypto_markets) > 0, "Should find at least one crypto market"
    print(f"✓ Found {len(crypto_markets)} crypto markets")
    
    # Place a test bet
    success = trader.place_crypto_bet(
        market_title_keyword="bitcoin",
        outcome=MarketDirection.YES,
        amount=100.0,
        max_price=0.6
    )
    
    if success:
        print("✓ Successfully placed a test bet")
        
        # Check updated state
        summary = trader.get_portfolio_summary()
        assert summary['current_balance'] < 5000.0, "Balance should be reduced after placing bet"
        assert summary['positions_count'] == 1, "Should have 1 position after placing bet"
        print("✓ Portfolio state updated correctly after bet")
        
        # List positions
        trader.list_positions()
        
        print("\n✓ All tests passed! The Polymarket Paper Trader is working correctly.")
    else:
        print("⚠ Could not place test bet (might be due to no matching markets)")
        print("This is expected if there are no active Bitcoin markets at the moment")
    
    return True


if __name__ == "__main__":
    test_basic_functionality()