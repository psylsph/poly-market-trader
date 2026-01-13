from typing import Dict, List, Optional
from collections import defaultdict


class StatisticsAggregator:
    """Aggregates bet history statistics by token"""
    
    def __init__(self):
        pass
    
    def get_token_statistics(self, bet_history: List[Dict]) -> Dict[str, Dict]:
        """
        Calculate statistics for each token
        :param bet_history: List of settled bets
        :return: Dictionary keyed by token name with statistics
        """
        token_stats = defaultdict(lambda: {
            'token': '',
            'total_bets': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'total_invested': 0.0,
            'roi': 0.0
        })
        
        for bet in bet_history:
            token = bet.get('crypto_name', 'unknown')
            status = bet.get('status', 'unknown')
            profit_loss = bet.get('profit_loss', 0.0)
            cost = bet.get('cost', 0.0)
            payout = bet.get('payout', 0.0)
            
            stats = token_stats[token]
            stats['token'] = token
            stats['total_bets'] += 1
            stats['total_invested'] += cost
            
            if status == 'won':
                stats['wins'] += 1
                stats['total_pnl'] += profit_loss
            elif status == 'lost':
                stats['losses'] += 1
                stats['total_pnl'] += profit_loss
        
        # Calculate percentages and ROI for each token
        for token, stats in token_stats.items():
            if stats['total_bets'] > 0:
                stats['win_rate'] = (stats['wins'] / stats['total_bets']) * 100
            if stats['total_invested'] > 0:
                stats['roi'] = (stats['total_pnl'] / stats['total_invested']) * 100
        
        return dict(token_stats)
    
    def sort_tokens_by_bets(self, token_stats: Dict[str, Dict]) -> List[Dict]:
        """Sort tokens by total number of bets (descending)"""
        return sorted(token_stats.values(), key=lambda x: x['total_bets'], reverse=True)
    
    def sort_tokens_by_pnl(self, token_stats: Dict[str, Dict]) -> List[Dict]:
        """Sort tokens by total P&L (descending)"""
        return sorted(token_stats.values(), key=lambda x: x['total_pnl'], reverse=True)
    
    def get_top_tokens(self, token_stats: Dict[str, Dict], 
                    limit: int = 10, sort_by: str = 'bets') -> List[Dict]:
        """
        Get top N tokens by specified metric
        :param token_stats: Dictionary of token statistics
        :param limit: Maximum number of tokens to return
        :param sort_by: 'bets' or 'pnl'
        :return: List of top N tokens
        """
        if sort_by == 'bets':
            sorted_tokens = self.sort_tokens_by_bets(token_stats)
        elif sort_by == 'pnl':
            sorted_tokens = self.sort_tokens_by_pnl(token_stats)
        else:
            sorted_tokens = list(token_stats.values())
        
        return sorted_tokens[:limit]
    
    def print_token_table(self, tokens: List[Dict]) -> None:
        """Print formatted token statistics table"""
        if not tokens:
            print("\n📊 No token statistics available.\n")
            return
        
        print("\n📊 TOKEN PERFORMANCE (All Time)")
        print("┌────────────────────────────────────────────────────────────────────────┐")
        print("│ Token   │ Bets │ Wins │ Losses │ Win Rate │ P&L      │ ROI      │")
        print("├───────────┼──────┼──────┼───────┼──────────┼──────────┼──────────┤")
        
        for token in tokens:
            token_name = token['token'][:7].ljust(7)
            bets = f"{token['total_bets']:>5}"
            wins = f"{token['wins']:>5}"
            losses = f"{token['losses']:>7}"
            win_rate = f"{token['win_rate']:>6.1f}%"
            pnl = f"${token['total_pnl']:>+8.2f}"
            roi = f"{token['roi']:>+6.1f}%"
            
            print(f"│ {token_name} │ {bets} │ {wins} │ {losses} │ {win_rate} │ {pnl} │ {roi}   │")
        
        print("└───────────┴──────┴──────┴───────┴──────────┴──────────┴──────────┘\n")
