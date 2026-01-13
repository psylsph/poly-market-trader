#!/usr/bin/env python3
"""
Manual test script to trigger settlement and debug why it's not happening automatically.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from poly_market_trader.services.paper_trader import PaperTrader
from decimal import Decimal


def main():
    print("=" * 70)
    print("MANUAL SETTLEMENT TEST")
    print("=" * 70)
    print()
    
    # Initialize trader
    print("Initializing PaperTrader...")
    trader = PaperTrader(initial_balance=Decimal('10000.00'), auto_load=True)
    
    # Get active bets
    print("\n" + "=" * 70)
    print("ACTIVE BETS")
    print("=" * 70)
    active_bets = trader.get_active_bets()
    print(f"Found {len(active_bets)} active bet(s)")
    print()
    
    if not active_bets:
        print("No active bets to settle.")
        return
    
    current_time = datetime.now(timezone.utc)
    print(f"Current UTC time: {current_time}")
    print()
    
    for i, bet in enumerate(active_bets, 1):
        print(f"Bet {i}:")
        print(f"  ID: {bet.get('bet_id', 'N/A')}")
        print(f"  Market: {bet.get('question', 'N/A')[:60]}")
        print(f"  Outcome: {bet.get('outcome', 'N/A')}")
        print(f"  Cost: ${bet.get('cost', 0):.2f}")
        print(f"  Placed: {bet.get('placed_at', 'N/A')}")
        print(f"  Market End: {bet.get('market_end_time', 'N/A')}")
        
        # Check if ready for settlement
        end_time_str = bet.get('market_end_time')
        if end_time_str:
            try:
                if 'T' in end_time_str:
                    end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                else:
                    end_time = datetime.fromisoformat(end_time_str)
                
                # Add timezone if naive
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                
                settlement_time = end_time + timedelta(minutes=5)
                time_until_settlement = settlement_time - current_time
                
                print(f"  Settlement Time (end + 5min): {settlement_time}")
                print(f"  Time until settlement: {time_until_settlement}")
                
                if current_time > settlement_time:
                    print(f"  ✅ READY TO SETTLE")
                else:
                    minutes_left = int(time_until_settlement.total_seconds() / 60)
                    print(f"  ⏳ NOT READY - wait {minutes_left} more minutes")
            except Exception as e:
                print(f"  ⚠️  Error parsing time: {e}")
        print()
    
    # Get portfolio summary before settlement
    print("\n" + "=" * 70)
    print("PORTFOLIO BEFORE SETTLEMENT")
    print("=" * 70)
    summary = trader.get_portfolio_summary()
    print(f"Balance: ${summary['current_balance']:.2f}")
    print(f"Total Value: ${summary['total_value']:.2f}")
    print(f"P&L: ${summary['pnl']:.2f}")
    print()
    
    # Get bet history before
    print("=" * 70)
    print("BET HISTORY BEFORE SETTLEMENT")
    print("=" * 70)
    history_before = trader.get_bet_history()
    print(f"Found {len(history_before)} settled bet(s)")
    if history_before:
        for bet in history_before[:5]:
            print(f"  {bet.get('question', 'N/A')[:50]} - {bet.get('status', 'N/A')}")
    print()
    
    # Attempt settlement
    print("=" * 70)
    print("ATTEMPTING SETTLEMENT")
    print("=" * 70)
    result = trader.settle_bets()
    print(f"Settlement result: {result}")
    print()
    
    # Get portfolio summary after settlement
    print("=" * 70)
    print("PORTFOLIO AFTER SETTLEMENT")
    print("=" * 70)
    summary_after = trader.get_portfolio_summary()
    print(f"Balance: ${summary_after['current_balance']:.2f}")
    print(f"Total Value: ${summary_after['total_value']:.2f}")
    print(f"P&L: ${summary_after['pnl']:.2f}")
    print()
    
    # Get bet history after
    print("=" * 70)
    print("BET HISTORY AFTER SETTLEMENT")
    print("=" * 70)
    history_after = trader.get_bet_history()
    print(f"Found {len(history_after)} settled bet(s)")
    if history_after:
        wins = sum(1 for b in history_after if b.get('status') == 'won')
        losses = sum(1 for b in history_after if b.get('status') == 'lost')
        print(f"  Wins: {wins}, Losses: {losses}")
        print()
        for bet in history_after[:5]:
            status = bet.get('status', 'N/A')
            pnl = bet.get('profit_loss', 0)
            print(f"  {bet.get('question', 'N/A')[:50]}")
            print(f"    Status: {status}, P&L: ${pnl:.2f}")
    print()
    
    # Get active bets after
    print("=" * 70)
    print("ACTIVE BETS AFTER SETTLEMENT")
    print("=" * 70)
    active_after = trader.get_active_bets()
    print(f"Found {len(active_after)} active bet(s)")
    print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Bets settled: {result['count']}")
    print(f"Active bets before: {len(active_bets)}")
    print(f"Active bets after: {len(active_after)}")
    print(f"History before: {len(history_before)}")
    print(f"History after: {len(history_after)}")
    print(f"Portfolio balance change: ${summary_after['current_balance'] - summary['current_balance']:.2f}")
    print()


if __name__ == '__main__':
    main()
