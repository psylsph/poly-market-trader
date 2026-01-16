"""UI Formatters - Simple console formatting without rich"""
from typing import List, Dict


class PortfolioDashboard:
    """Simple portfolio dashboard formatting"""
    
    def display_portfolio(self, portfolio_summary: Dict, positions: List[Dict], 
                     active_bets_count: int = 0) -> None:
        """Display portfolio with simple formatting"""
        balance = portfolio_summary.get('current_balance', 0.0)
        total_value = portfolio_summary.get('total_value', 0.0)
        pnl = portfolio_summary.get('pnl', 0.0)
        positions_count = portfolio_summary.get('positions_count', 0)
        trades_count = portfolio_summary.get('trade_count', 0)
        
        # Calculate ROI
        from decimal import Decimal
        initial_balance = portfolio_summary.get('initial_balance', 10000.0)
        roi = ((total_value - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0.0
        
        print("\n" + "=" * 60)
        print("  POLYMARKET PAPER TRADER PORTFOLIO")
        print("=" * 60)
        print(f"  Current Balance:      ${balance:,.2f}")
        print(f"  Total Value:        ${total_value:,.2f}")
        print(f"  Realized P&L:      ${pnl:,.2f}")
        print(f"  ROI:               {roi:+.2f}%")
        print("-" * 60)
        print(f"  Position Stats:  Active Positions: {positions_count} | Active Bets: {active_bets_count} | Trades: {trades_count}")
        print("=" * 60 + "\n")
    
    def display_active_bets(self, active_bets: List[Dict]) -> None:
        """Display active bets table"""
        if not active_bets:
            print("\n📋 No active bets.\n")
            return
        
        print(f"\n📋 Active Bets ({len(active_bets)}):")
        print("=" * 60)
        print(f"  {'Market':<40} {'Outcome':<8} {'Qty':<12} {'Price':<12} {'Cost':<12} {'Status':<10}")
        print("-" * 60)
        
        for i, bet in enumerate(active_bets, 1):
            question = bet.get('question', 'N/A')[:38]
            outcome = bet.get('outcome', 'N/A')
            quantity = bet.get('quantity', 0.0)
            price = bet.get('entry_price', 0.0)
            cost = bet.get('cost', 0.0)
            
            print(f"  {i}. {question:<38} {outcome:<8} {quantity:>12.2f} ${price:<10.2f} ${cost:<10.2f} ⏳ Active")
        
        print("=" * 60 + "\n")


class BetHistoryDashboard:
    """Simple bet history dashboard formatting"""
    
    def display_history(self, bet_history: List[Dict]) -> None:
        """Display bet history with simple formatting"""
        if not bet_history:
            print("\n📜 No bet history found.\n")
            return
        
        # Calculate stats
        total_bets = len(bet_history)
        wins = sum(1 for b in bet_history if b.get('status') == 'won')
        losses = sum(1 for b in bet_history if b.get('status') == 'lost')
        win_rate = (wins / total_bets * 100) if total_bets > 0 else 0.0
        total_pnl = sum(b.get('profit_loss', 0.0) for b in bet_history)
        
        # Display stats
        print("\n" + "=" * 60)
        print("  BET STATISTICS")
        print("=" * 60)
        print(f"  Total Bets:  {total_bets} | Wins: {wins} | Losses: {losses}")
        print(f"  Win Rate:   {win_rate:.1f}%")
        print(f"  Total P&L:   ${total_pnl:+,.2f}")
        print("=" * 60 + "\n")
        
        # Display table
        print(f"  📜 Bet History ({total_bets} bets):")
        print("=" * 60)
        print(f"  {'#':<4} {'Market':<35} {'Outcome':<8} {'Result':<8} {'Payout':<12} {'P&L':<12} {'Date':<19}")
        print("-" * 60)
        
        for i, bet in enumerate(bet_history, 1):
            question = bet.get('question', 'N/A')[:33]
            outcome = bet.get('outcome', 'N/A')
            status = bet.get('status', 'unknown')
            payout = bet.get('payout', 0.0)
            pnl = bet.get('profit_loss', 0.0)
            settled_at = bet.get('settled_at', 'N/A')
            
            # Format result
            result_text = "✅ WON" if status == 'won' else "❌ LOST"
            pnl_color = f"+{pnl:,.2f}" if pnl >= 0 else f"{pnl:,.2f}"
            
            # Format date
            date_str = settled_at.split('T')[0].split('+')[0][:19] if settled_at != 'N/A' else 'N/A'
            
            print(f"  {i}. {question:<33} {outcome:<8} {result_text:<10} ${payout:>10.2f} ${pnl_color:<12} {date_str}")
        
        print("=" * 60 + "\n")


class MonitoringStatusDashboard:
    """Dashboard for monitoring system status"""
    
    def display_status(self, status: Dict) -> None:
        """
        Display monitoring system status
        
        Args:
            status: Dict with keys:
                - polling_active: bool
                - websocket_active: bool
                - websocket_connected: bool
                - active_bets: int
        """
        polling_active = status.get('polling_active', False)
        ws_active = status.get('websocket_active', False)
        ws_connected = status.get('websocket_connected', False)
        active_bets = status.get('active_bets', 0)
        
        # Status indicators
        polling_indicator = "🟢 RUNNING" if polling_active else "🔴 STOPPED"
        ws_indicator = "🟢 CONNECTED" if ws_connected else "🔴 DISCONNECTED"
        ws_status = "🟢 ACTIVE" if ws_active else "🔴 INACTIVE"
        
        print("\n" + "=" * 60)
        print("  MONITORING STATUS")
        print("=" * 60)
        print(f"  ┌─────────────────────────────────────────────────────┐")
        print(f"  │  Polling Monitor:  {polling_indicator:<28}│")
        print(f"  │  WebSocket:        {ws_indicator:<28}│")
        print(f"  │  WS Monitoring:    {ws_status:<28}│")
        print(f"  │  Active Bets:      {active_bets:<28}│")
        print(f"  └─────────────────────────────────────────────────────┘")
        print("=" * 60)
        
        # Show status details
        print("\n  System Details:")
        if polling_active:
            print("    • Polling monitor checks every 15 minutes (market scanning interval)")
        if ws_active and ws_connected:
            print("    • WebSocket provides real-time arbitrage detection")
            print("    • Instant order execution on arbitrage opportunities")
        elif ws_active:
            print("    • WebSocket connecting...")
        else:
            print("    • Run start_realtime_monitoring() to enable WebSocket")
        
        print()
