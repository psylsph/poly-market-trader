"""Live monitoring dashboard for real-time updates"""
import time
import sys
from typing import List, Dict, Callable, Optional
from datetime import datetime, timezone, timedelta


class LiveMonitor:
    """Real-time monitoring dashboard with keyboard controls"""
    
    def __init__(self, interval_seconds: int = 900):
        self.interval_seconds = interval_seconds
        self.is_running = False
        self.refresh_flag = False
        self.last_update = datetime.now()
        self.cycle_count = 0
    
    def _print_header(self) -> None:
        """Print monitoring header"""
        print("\n" + "=" * 70)
        print("  🟢 AUTO-BETTING MONITOR - RUNNING")
        print("=" * 70)
    
    def _print_controls(self) -> None:
        """Print keyboard controls"""
        print("\n  🎮 CONTROLS: [r] Refresh Now  | [q] Quit\n")
        print("=" * 70)
    
    def _print_portfolio_summary(self, portfolio_summary: Dict) -> None:
        """Print portfolio summary inline"""
        balance = portfolio_summary.get('current_balance', 0.0)
        total_value = portfolio_summary.get('total_value', 0.0)
        pnl = portfolio_summary.get('pnl', 0.0)
        
        # Calculate ROI
        from decimal import Decimal
        initial_balance = portfolio_summary.get('initial_balance', 10000.0)
        roi = ((total_value - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0.0
        
        # Color based on P&L
        pnl_color = "🟢 +" if pnl >= 0 else "🔴 "
        pnl_text = f"{pnl_color}${pnl:+.2f}"
        
        print(f"  💰 Portfolio: ${total_value:,.2f} | P&L: {pnl_text} | ROI: {roi:+.2f}%")
    
    def _print_active_bets(self, active_bets: List[Dict], cycle_count: int, 
                        time_until_check: int) -> None:
        """Print active bets with countdown"""
        if not active_bets:
            print(f"\n  📋 ACTIVE BETS: None (Cycle: {cycle_count})")
            return
        
        print(f"\n  📋 ACTIVE BETS ({len(active_bets)}) - Cycle: {cycle_count}")
        print("-" * 70)
        
        for i, bet in enumerate(active_bets, 1):
            market_id = bet.get('market_id', 'N/A')
            question = bet.get('question', 'N/A')[:38]
            outcome = bet.get('outcome', 'N/A')
            quantity = bet.get('quantity', 0.0)
            cost = bet.get('cost', 0.0)
            
            # Calculate time remaining
            end_time_str = bet.get('market_end_time', '')
            if end_time_str:
                try:
                    end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                    now = datetime.now()
                    remaining = end_time - now
                    
                    if remaining.total_seconds() > 0:
                        minutes = int(remaining.total_seconds() // 60)
                        seconds = int(remaining.total_seconds() % 60)
                        time_str = f"⏰ {minutes:02d}:{seconds:02d}"
                    else:
                        time_str = "⏰ Expired"
                except:
                    time_str = "❓ Unknown"
            else:
                time_str = "❓ No end time"
            
            print(f"  {i}. {question}")
            print(f"     {outcome} | {quantity:.2f} @ ${cost/quantity:.2f} | ${cost:.2f} | {time_str}")
        
        print("-" * 70)
    
    def _print_next_check(self, time_until_check: int) -> None:
        """Print time until next check"""
        if time_until_check > 0:
            minutes = int(time_until_check // 60)
            seconds = int(time_until_check % 60)
            print(f"  ⏱️  Next check in: {minutes:02d}:{seconds:02d}")
        else:
            print(f"  ⏱️  Next check in: Starting now...")
    
    def _print_activity_log(self, recent_activity: List[str]) -> None:
        """Print recent activity log"""
        if not recent_activity:
            print(f"\n  📜 RECENT ACTIVITY (last 5):")
            print("  (No recent activity)")
            return
        
        print(f"\n  📜 RECENT ACTIVITY (last 5):")
        print("-" * 70)
        
        for activity in recent_activity[-5:]:
            print(f"  {activity}")
        
        print("-" * 70)
    
    def _check_keyboard(self) -> str:
        """Check for keyboard input (non-blocking)"""
        import select
        import termios
        
        # Check if there's input available
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            # Input available, check it
            line = sys.stdin.readline()
            if line and line[0].lower() == 'q':
                return 'quit'
            elif line and line[0].lower() == 'r':
                return 'refresh'
        
        return None
    
    def start_monitoring(self, portfolio_summary_callback: Callable,
                         active_bets_callback: Callable,
                         activity_log_callback: Callable) -> None:
        """
        Start monitoring loop with keyboard controls
        :param portfolio_summary_callback: Function to get portfolio summary
        :param active_bets_callback: Function to get active bets
        :param activity_log_callback: Function to get recent activity
        """
        self.is_running = True
        self.cycle_count = 0
        
        import select
        
        print("\n" + "=" * 70)
        print("  🚀 STARTING LIVE MONITORING")
        print("  Press [q] to quit, [r] to refresh now")
        print("=" * 70 + "\n")
        
        try:
            while self.is_running:
                self.cycle_count += 1
                cycle_start = time.time()
                
                # Clear screen (simple approach)
                print("\n" * 50)
                
                # Print header
                self._print_header()
                
                # Get data from callbacks
                portfolio_summary = portfolio_summary_callback()
                active_bets = active_bets_callback()
                activity_log = activity_log_callback()
                
                # Print portfolio
                self._print_portfolio_summary(portfolio_summary)
                
                # Print active bets
                time_until_check = self.interval_seconds
                self._print_active_bets(active_bets, self.cycle_count, time_until_check)
                
                # Print next check
                self._print_next_check(time_until_check)
                
                # Print activity log
                self._print_activity_log(activity_log)
                
                # Wait with keyboard checking
                self._wait_with_keyboard_check(cycle_start)
        
        except KeyboardInterrupt:
            print("\n\n" + "=" * 70)
            print("  🛑 MONITORING STOPPED")
            print("=" * 70)
            self.is_running = False
    
    def _wait_with_keyboard_check(self, cycle_start: float) -> None:
        """Wait for interval while checking for keyboard input"""
        import select
        
        elapsed = 0
        wait_time = self.interval_seconds
        
        while elapsed < wait_time and self.is_running:
            # Check for keyboard input every 0.1 seconds
            if self._check_keyboard():
                break
            time.sleep(0.1)
            elapsed = time.time() - cycle_start
            
            # Check if refresh was requested
            if self.refresh_flag:
                self.refresh_flag = False
                break
    
    def stop_monitoring(self) -> None:
        """Stop monitoring"""
        self.is_running = False
        print("\n  🛑 Stopping monitoring...")
