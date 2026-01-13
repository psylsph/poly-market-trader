from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from typing import List, Dict, Optional
from decimal import Decimal


class PortfolioDashboard:
    """Beautiful terminal formatting for portfolio display"""
    
    def __init__(self, console: Console = None):
        self.console = console or Console()
    
    def display_portfolio(self, portfolio_summary: Dict, positions: List[Dict], 
                     active_bets_count: int = 0) -> None:
        """
        Display portfolio with rich formatting
        :param portfolio_summary: Portfolio summary data
        :param positions: List of position dictionaries
        :param active_bets_count: Number of active bets
        """
        balance = portfolio_summary.get('current_balance', 0.0)
        total_value = portfolio_summary.get('total_value', 0.0)
        pnl = portfolio_summary.get('pnl', 0.0)
        positions_count = portfolio_summary.get('positions_count', 0)
        trades_count = portfolio_summary.get('trade_count', 0)
        
        # Calculate ROI
        from decimal import Decimal
        initial_balance = portfolio_summary.get('initial_balance', 10000.0)
        roi = ((total_value - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0.0
        
        # Create main panel
        panel = Panel(
            self._create_portfolio_content(
                balance, total_value, pnl, roi, 
                positions_count, trades_count, active_bets_count
            ),
            title="[bold blue]POLYMARKET PAPER TRADER PORTFOLIO[/bold blue]",
            border_style="blue",
            padding=(1, 1)
        )
        
        self.console.print(panel)
    
    def _create_portfolio_content(self, balance: float, total_value: float, pnl: float, 
                                roi: float, positions_count: int, 
                                trades_count: int, active_bets_count: int):
        """Create the content for portfolio panel"""
        # Color based on P&L
        pnl_color = "green" if pnl >= 0 else "red"
        pnl_text = f"[{pnl_color}]${pnl:,.2f}[/{pnl_color}]"
        roi_color = "green" if roi >= 0 else "red"
        roi_text = f"[{roi_color}]{roi:+.2f}%[/{roi_color}]"
        
        content = f"""
[balance]Current Balance:[/balance] ${balance:,.2f}
[balance]Total Value:[/balance] ${total_value:,.2f}
[balance]Realized P&L:[/balance] {pnl_text}
[balance]ROI:[/balance] {roi_text}

[bold]Position Stats:[/bold] Active Positions: {positions_count} | Active Bets: {active_bets_count} | Trades: {trades_count}
"""
        return content
    
    def display_active_bets(self, active_bets: List[Dict]) -> None:
        """
        Display active bets table with rich formatting
        :param active_bets: List of active bet dictionaries
        """
        if not active_bets:
            self.console.print("\n[yellow]📋 No active bets.[/yellow]\n")
            return
        
        table = Table(
            title="[bold cyan]📋 Active Bets[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
            border_style="cyan"
        )
        
        table.add_column("Market", style="cyan", width=40)
        table.add_column("Outcome", style="magenta", width=8)
        table.add_column("Qty", justify="right", width=10)
        table.add_column("Price", justify="right", width=10)
        table.add_column("Cost", justify="right", width=10)
        table.add_column("Status", justify="center", width=10)
        
        for bet in active_bets:
            question = bet.get('question', 'N/A')[:38]
            outcome = bet.get('outcome', 'N/A')
            quantity = bet.get('quantity', 0.0)
            price = bet.get('entry_price', 0.0)
            cost = bet.get('cost', 0.0)
            
            table.add_row(
                question,
                f"[cyan]{outcome}[/cyan]",
                f"{quantity:.2f}",
                f"${price:.2f}",
                f"${cost:.2f}",
                "[blue]⏳ Active[/blue]"
            )
        
        self.console.print(table)
        self.console.print()


class BetHistoryDashboard:
    """Beautiful terminal formatting for bet history display"""
    
    def __init__(self, console: Console = None):
        self.console = console or Console()
    
    def display_history(self, bet_history: List[Dict]) -> None:
        """
        Display bet history table with rich formatting
        :param bet_history: List of settled bet dictionaries
        """
        if not bet_history:
            self.console.print("\n[yellow]📜 No bet history found.[/yellow]\n")
            return
        
        # Calculate stats
        total_bets = len(bet_history)
        wins = sum(1 for b in bet_history if b.get('status') == 'won')
        losses = sum(1 for b in bet_history if b.get('status') == 'lost')
        win_rate = (wins / total_bets * 100) if total_bets > 0 else 0.0
        total_pnl = sum(b.get('profit_loss', 0.0) for b in bet_history)
        
        # Display stats panel
        stats_panel = Panel(
            self._create_stats_content(total_bets, wins, losses, win_rate, total_pnl),
            title="[bold magenta]📊 Bet Statistics[/bold magenta]",
            border_style="magenta",
            padding=(0, 1)
        )
        
        self.console.print(stats_panel)
        self.console.print()
        
        # Create table
        table = Table(
            title=f"[bold cyan]📜 Bet History ({total_bets} bets)[/bold cyan]",
            show_header=True,
            header_style="bold magenta",
            border_style="cyan"
        )
        
        table.add_column("#", style="grey50", width=4)
        table.add_column("Market", style="cyan", width=35)
        table.add_column("Outcome", style="magenta", width=8)
        table.add_column("Result", style="bold", width=6)
        table.add_column("Payout", justify="right", width=10)
        table.add_column("P&L", justify="right", width=10)
        table.add_column("Date", style="grey50", width=19)
        
        for i, bet in enumerate(bet_history, 1):
            question = bet.get('question', 'N/A')[:33]
            outcome = bet.get('outcome', 'N/A')
            status = bet.get('status', 'unknown')
            payout = bet.get('payout', 0.0)
            pnl = bet.get('profit_loss', 0.0)
            settled_at = bet.get('settled_at', 'N/A')
            
            # Color based on win/loss
            result_color = "green" if status == 'won' else "red"
            result_text = f"[{result_color}]✅ WON[/{result_color}]" if status == 'won' else f"[{result_color}]❌ LOST[/{result_color}]"
            pnl_color = "green" if pnl >= 0 else "red"
            pnl_text = f"[{pnl_color}]${pnl:+.2f}[/{pnl_color}]"
            
            table.add_row(
                f"{i}",
                question,
                f"[cyan]{outcome}[/cyan]",
                result_text,
                f"${payout:.2f}",
                pnl_text,
                settled_at.split('T')[0].split('+')[0][:19] if settled_at != 'N/A' else 'N/A'
            )
        
        self.console.print(table)
        self.console.print()
    
    def _create_stats_content(self, total_bets: int, wins: int, losses: int, 
                             win_rate: float, total_pnl: float) -> str:
        """Create statistics content for panel"""
        win_rate_color = "green" if win_rate >= 50 else "red"
        pnl_color = "green" if total_pnl >= 0 else "red"
        
        return f"""
Total Bets: {total_bets} | Wins: [green]{wins}[/green] | Losses: [red]{losses}[/red]
Win Rate: [{win_rate_color}]{win_rate:.1f}%[/{win_rate_color}]
Total P&L: [{pnl_color}]${total_pnl:+,.2f}[/{pnl_color}]
"""
