from typing import Dict, List, Callable, Optional
from datetime import datetime, timezone, timedelta
import time
import sys

from .statistics_aggregator import StatisticsAggregator
from .offer_tracker import OfferTracker


class CombinedDashboard:
    """Single-screen dashboard with top/bottom split view"""
    
    def __init__(self, portfolio_summary_callback: Callable,
                 active_bets_callback: Callable,
                 bet_history_callback: Callable,
                 market_monitor_callback: Callable):
        self.portfolio_summary_callback = portfolio_summary_callback
        self.active_bets_callback = active_bets_callback
        self.bet_history_callback = bet_history_callback
        self.market_monitor_callback = market_monitor_callback
        
        self.statistics_aggregator = StatisticsAggregator()
        self.offer_tracker = OfferTracker()
        
        self.is_running = False
        self.refresh_interval = 15  # seconds
        self.last_refresh = datetime.now()
        self.cycle_count = 0
    
    def start_dashboard(self) -> None:
        """Start the combined dashboard"""
        self.is_running = True
        self.cycle_count = 0
        
        print("\n" + "=" * 70)
        print("  🚀 STARTING COMBINED DASHBOARD")
        print("  Controls: [q] Quit | [r] Refresh Now | [1-9] Accept Offer N | [s] Skip All | [a] Accept All")
        print("=" * 70 + "\n")
        
        try:
            while self.is_running:
                self.cycle_count += 1
                cycle_start = time.time()
                
                # Clear screen (simple approach)
                print("\n" * 100)
                
                # Render complete dashboard
                self._render_full_dashboard()
                
                # Wait with keyboard checking
                self._wait_with_keyboard_check(cycle_start)
        
        except KeyboardInterrupt:
            self.stop_dashboard()
    
    def stop_dashboard(self) -> None:
        """Stop the dashboard"""
        self.is_running = False
        print("\n" + "=" * 70)
        print("  🛑 DASHBOARD STOPPED")
        print("=" * 70 + "\n")
    
    def _render_full_dashboard(self) -> None:
        """Render the complete dashboard"""
        # Top half: Token statistics + Recent history
        self._render_top_half()
        
        # Middle: Separator
        print("├" + "─" * 68 + "┤")
        
        # Bottom half: Portfolio + Active bets + New offers
        self._render_bottom_half()
    
    def _render_top_half(self) -> None:
        """Render top half of dashboard (stats + history)"""
        # Get bet history and calculate token stats
        bet_history = self.bet_history_callback()
        token_stats = self.statistics_aggregator.get_token_statistics(bet_history)
        top_tokens = self.statistics_aggregator.get_top_tokens(token_stats, limit=8, sort_by='bets')
        
        # Section 1: Token Performance
        print("\n📊 TOKEN PERFORMANCE (All Time)")
        self.statistics_aggregator.print_token_table(top_tokens)
        
        # Section 2: Recent Bet History (Last 10)
        print("📜 RECENT BET HISTORY (Last 10)")
        self._print_bet_history_table(bet_history[:10])
    
    def _render_bottom_half(self) -> None:
        """Render bottom half of dashboard (portfolio + active bets + offers)"""
        # Get data
        portfolio_summary = self.portfolio_summary_callback()
        active_bets = self.active_bets_callback()
        
        # Get offers from market monitor (simulated)
        offers = self.market_monitor_callback()
        
        # Section 1: Portfolio Summary
        self._print_portfolio_summary(portfolio_summary)
        
        # Section 2: Active Bets
        self._print_active_bets(active_bets)
        
        # Section 3: New Offers
        self.offer_tracker.print_offers_table(offers, title="NEW BET OFFERS")
    
    def _print_bet_history_table(self, bets: List[Dict]) -> None:
        """Print bet history table"""
        if not bets:
            print("\n📜 No bet history found.\n")
            return
        
        print("┌────────────────────────────────────────────────────────────────────────┐")
        print("│ #  │ Market              │ Token │ Outcome │ Result   │ Payout   │ P&L      │")
        print("├────┼────────────────────┼──────┼─────────┼──────────┼──────────┼──────────┤")
        
        for i, bet in enumerate(bets, 1):
            num = f"{i:2d}"
            market = bet.get('question', 'N/A')[:18]
            token = bet.get('crypto_name', 'N/A')[:7]
            outcome = bet.get('outcome', 'N/A')[:6]
            status = bet.get('status', 'unknown')
            payout = bet.get('payout', 0.0)
            pnl = bet.get('profit_loss', 0.0)
            
            result_text = "✅ WIN" if status == 'won' else "❌ LOSS" if status == 'lost' else "⏳ PENDING"
            payout_str = f"${payout:>8.2f}"
            pnl_str = f"${pnl:+8.2f}"
            
            print(f"│ {num} │ {market}│ {token}│ {outcome}│ {result_text:8s} │ {payout_str} │ {pnl_str} │")
        
        print("└────┴────────────────────┴──────┴─────────┴──────────┴──────────┴──────────┘")
    
    def _print_portfolio_summary(self, portfolio_summary: Dict) -> None:
        """Print portfolio summary"""
        balance = portfolio_summary.get('current_balance', 0.0)
        total_value = portfolio_summary.get('total_value', 0.0)
        pnl = portfolio_summary.get('pnl', 0.0)
        positions_count = portfolio_summary.get('positions_count', 0)
        trades_count = portfolio_summary.get('trade_count', 0)
        
        # Calculate ROI
        from decimal import Decimal
        initial_balance = portfolio_summary.get('initial_balance', 10000.0)
        invested = initial_balance - balance
        roi = ((total_value - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0.0
        
        # Get total bets from history
        bet_history = self.bet_history_callback()
        total_bets = len(bet_history)
        wins = sum(1 for b in bet_history if b.get('status') == 'won')
        losses = sum(1 for b in bet_history if b.get('status') == 'lost')
        win_rate = (wins / total_bets * 100) if total_bets > 0 else 0.0
        
        print("\n💰 PORTFOLIO SUMMARY")
        print("┌────────────────────────────────────────────────────────────────────────┐")
        print(f"│ Balance: ${balance:>10.2f} │ Invested: ${invested:>9.2f} │ P&L: ${pnl:>+9.2f} │ ROI: {roi:>+6.1f}%   │")
        print("├────────────────────────────────────────────────────────────────────────┤")
        print(f"│ Active: {positions_count} bets  │ Total: {total_bets} bets  │ Wins: {wins}  │ Losses: {losses}   │")
        print(f"│ Win Rate: {win_rate:>6.1f}%                                                        │")
        print("└────────────────────────────────────────────────────────────────────────┘\n")
    
    def _print_active_bets(self, active_bets: List[Dict]) -> None:
        """Print active bets table"""
        if not active_bets:
            print("\n📋 No active bets.\n")
            return
        
        now = datetime.now()
        
        print("📋 ACTIVE BETS (Waiting Settlement)")
        print("┌────────────────────────────────────────────────────────────────────────┐")
        print("│ Market                    │ Token │ Outcome │ Qty   │ Price │ Cost   │ Time Left │")
        print("├─────────────────────────────┼──────┼─────────┼──────┼──────┼──────┼───────────┤")
        
        for bet in active_bets:
            market = bet.get('question', 'N/A')[:24]
            token = bet.get('crypto_name', 'N/A')[:7]
            outcome = bet.get('outcome', 'N/A')[:6]
            quantity = f"{bet.get('quantity', 0.0):>7.2f}"
            price = f"${bet.get('entry_price', 0.0):>6.2f}"
            cost = f"${bet.get('cost', 0.0):>7.2f}"
            
            # Calculate time remaining
            end_time_str = bet.get('market_end_time', '')
            if end_time_str:
                try:
                    end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                    remaining = end_time - now
                    if remaining.total_seconds() > 0:
                        minutes = int(remaining.total_seconds() // 60)
                        time_left = f"{minutes:2d}m"
                    else:
                        time_left = "EXP"
                except:
                    time_left = "ERR"
            else:
                time_left = "N/A"
            
            print(f"│ {market:25}│ {token:7}│ {outcome:6}│ {quantity}│ {price}│ {cost}│ {time_left:>9s} │")
        
        print("└─────────────────────────────────┴──────┴─────────┴──────┴──────┴──────┴───────────┘\n")
    
    def _wait_with_keyboard_check(self, cycle_start: float) -> None:
        """Wait for refresh interval while checking for keyboard input"""
        elapsed = 0
        wait_time = self.refresh_interval
        
        while elapsed < wait_time and self.is_running:
            # Check for keyboard input every 0.1 seconds
            key = self._check_keyboard()
            if key:
                self._handle_key_input(key)
                break
            time.sleep(0.1)
            elapsed = time.time() - cycle_start
    
    def _check_keyboard(self) -> Optional[str]:
        """Check for keyboard input"""
        import select
        
        try:
            if select.select([sys.stdin], [], [], 0.01) == ([sys.stdin], [], []):
                line = sys.stdin.readline().strip()
                if line:
                    char = line[0].lower()
                    if char == 'q':
                        return 'quit'
                    elif char == 'r':
                        return 'refresh'
                    elif char.isdigit() and 1 <= int(char) <= 9:
                        return f'accept_{char}'
                    elif char == 's':
                        return 'skip_all'
                    elif char == 'a':
                        return 'accept_all'
        except:
            return None
        
        return None
    
    def _handle_key_input(self, key: str) -> None:
        """Handle keyboard input"""
        if key == 'quit':
            self.stop_dashboard()
        elif key == 'refresh':
            self.last_refresh = datetime.now()
            print("\n  🔄 Refreshing...")
        elif key.startswith('accept_'):
            offer_num = int(key.split('_')[1])
            offers = self.offer_tracker.get_pending_offers()
            if len(offers) >= offer_num:
                offer = offers[offer_num - 1]
                self.offer_tracker.update_offer_action(offer.get('offer_id'), 'accepted')
                print(f"\n  ✅ Accepted offer {offer_num}: {offer.get('question', 'N/A')[:30]}")
        elif key == 'skip_all':
            offers = self.offer_tracker.get_pending_offers()
            for offer in offers:
                self.offer_tracker.update_offer_action(offer.get('offer_id'), 'skipped')
            print(f"\n  ⏭️  Skipped all {len(offers)} offers")
        elif key == 'accept_all':
            offers = self.offer_tracker.get_pending_offers()
            for i, offer in enumerate(offers):
                self.offer_tracker.update_offer_action(offer.get('offer_id'), 'accepted')
            print(f"\n  ✅ Accepted all {len(offers)} offers")
    
    def cleanup_expired_offers(self) -> None:
        """Remove expired offers from the tracker"""
        self.offer_tracker.cleanup_expired_offers()
