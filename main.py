#!/usr/bin/env python3
"""
Polymarket Paper Trader - Crypto Betting Application

This application allows you to simulate betting on crypto-related markets
on Polymarket without risking real money. It uses real market data to
simulate trades and track your virtual portfolio performance.
"""

import argparse
import sys
import time
from decimal import Decimal

from poly_market_trader.services.paper_trader import PaperTrader

parser = argparse.ArgumentParser(description='Polymarket Paper Trader for Crypto Betting')

parser.add_argument('--balance', type=float, default=10000.0,
                    help='Initial virtual balance (default: 10000)')
parser.add_argument('--list-markets', action='store_true',
                    help='List available crypto markets')
parser.add_argument('--place-bet', action='store_true',
                    help='Place a bet on a crypto market')
parser.add_argument('--bet-market', type=str,
                    help='Keyword to identify the market (e.g., bitcoin, ethereum)')
parser.add_argument('--outcome', type=str, choices=['YES', 'NO'],
                    help='Outcome to bet on (YES or NO)')
parser.add_argument('--amount', type=float,
                    help='Amount to bet in USD')
parser.add_argument('--max-price', type=float, default=1.0,
                    help='Maximum price to pay for outcome token (default: 1.0)')
parser.add_argument('--portfolio', action='store_true',
                    help='Show portfolio summary')
parser.add_argument('--positions', action='store_true',
                    help='List active positions')
parser.add_argument('--analyze', type=str,
                    help='Analyze a cryptocurrency using Chainlink data (e.g., bitcoin, ethereum)')
parser.add_argument('--auto-bet', action='store_true',
                    help='Place an auto bet based on Chainlink analysis')
parser.add_argument('--start-monitoring', action='store_true',
                    help='Start continuous auto-betting monitoring (15-minute intervals)')
parser.add_argument('--live-monitor', action='store_true',
                    help='Start live monitoring with real-time updates and keyboard controls (q=quit, r=refresh)')
parser.add_argument('--stop-monitoring', action='store_true',
                    help='Stop continuous auto-betting monitoring')
parser.add_argument('--dashboard', action='store_true',
                    help='Start combined dashboard with token statistics, bet history, and new bet offers')
parser.add_argument('--reset-portfolio', action='store_true',
                    help='Reset portfolio to fresh state (wipes all data)')
parser.add_argument('--settle-bets', action='store_true',
                    help='Manually settle all ready bets')
parser.add_argument('--bet-history', action='store_true',
                    help='Show bet history')
parser.add_argument('--history-limit', type=int, default=10,
                    help='Limit number of bets to show in history (default: 10)')
parser.add_argument('--history-filter', type=str, choices=['won', 'lost'],
                    help='Filter history by status')
parser.add_argument('--monitor-status', action='store_true',
                    help='Show auto-betting monitoring status')
parser.add_argument('--active-bets', action='store_true',
                    help='Show active bets from auto-betting system')
parser.add_argument('--confidence-threshold', type=float, default=0.6,
                    help='Minimum confidence level to place auto bet (default: 0.6)')
parser.add_argument('--web', action='store_true',
                    help='Start the web GUI server (default port: 8000)')
parser.add_argument('--web-port', type=int, default=8000,
                    help='Port for web GUI server (default: 8000)')

args = parser.parse_args()

# Initialize paper trader
trader = PaperTrader(initial_balance=Decimal(str(args.balance)))

# Handle different commands
if args.reset_portfolio:
    print("Resetting portfolio to fresh state...")
    trader.reset_portfolio()
    print("Portfolio has been reset. All data wiped and fresh portfolio created.")

elif args.settle_bets:
    results = trader.settle_bets()
    print(f"✅ Settlement complete! Processed {results['count']} bets.")

elif args.bet_history:
    limit = args.history_limit if hasattr(args, 'history_limit') else None
    status_filter = args.history_filter if hasattr(args, 'history_filter') else None
    history = trader.get_bet_history(limit, status_filter)
    trader.bet_history_dashboard.display_history(history)

elif args.list_markets:
    trader.list_crypto_markets()

elif args.analyze:
    print(f"Performing Chainlink analysis for {args.analyze}...")
    analysis = trader.get_chainlink_analysis(args.analyze)
    
    print(f"Current price: ${analysis['current_price']:.2f}" if analysis['current_price'] else "Current price: N/A")
    print(f"Trend: {analysis['trend']}")
    
    if analysis['indicators']:
        indicators = analysis['indicators']
        print(f"SMA: ${indicators.get('sma', 0):.2f}")
        print(f"Volatility: {indicators.get('volatility', 0):.2f}")
        print(f"Current vs SMA: {indicators.get('price_sma_ratio', 0):.2f}")
    else:
        print("Indicators: N/A")

elif args.dashboard:
    print("Starting combined dashboard...")
    trader.start_dashboard()

elif args.active_bets:
    active_bets = trader.get_active_bets()
    if active_bets:
        print(f"\n📋 Active Bets ({len(active_bets)}):")
        for i, bet in enumerate(active_bets, 1):
            print(f"{i}. {bet.get('question', 'N/A')[:50]}")
            print(f"   Outcome: {bet.get('outcome')} | Quantity: {bet.get('quantity', 0):.2f} | Cost: ${bet.get('cost', 0):.2f}")
    else:
        print("\n📋 No active bets.")

elif args.web:
    print(f"Starting web GUI server on port {args.web_port}...")
    print(f"Open http://localhost:{args.web_port} in your browser")
    print("Press Ctrl+C to stop the server\n")
    
    import uvicorn
    from poly_market_trader.web.api_server import app
    uvicorn.run(app, host="0.0.0.0", port=args.web_port)

else:
    # Default: show portfolio summary and available markets
    print("Welcome to Polymarket Paper Trader!")
    print("Use --help to see available options.\n")
    trader.print_portfolio_summary()
    print("Available crypto markets:")
    trader.list_crypto_markets()

# Don't execute any actual trading without user command
sys.exit(0)
