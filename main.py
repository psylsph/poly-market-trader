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
from datetime import datetime, timedelta, timezone

from poly_market_trader.services.paper_trader import PaperTrader
from poly_market_trader.models.trade import MarketDirection

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
parser.add_argument('--all-history', action='store_true',
                    help='Show all bet history (overrides 24h default)')
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
parser.add_argument('--realtime-monitor', action='store_true',
                    help='Start real-time WebSocket monitoring for arbitrage detection')
parser.add_argument('--stop-realtime', action='store_true',
                    help='Stop real-time WebSocket monitoring')
parser.add_argument('--realtime-status', action='store_true',
                    help='Show real-time WebSocket prices and status')
parser.add_argument('--use-llm', action='store_true',
                    help='Force enable Local LLM integration (overrides settings)')
parser.add_argument('--no-llm', action='store_true',
                    help='Force disable Local LLM integration (overrides settings)')

def main(args=None):
    """Main entry point for the CLI"""
    if args is None:
        args = parser.parse_args()

    # Determine LLM override
    use_llm = None
    if hasattr(args, 'use_llm') and args.use_llm:
        use_llm = True
    elif hasattr(args, 'no_llm') and args.no_llm:
        use_llm = False

    # Initialize paper trader
    trader = PaperTrader(initial_balance=Decimal(str(args.balance)), use_llm=use_llm)

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
        
        # Default to last 24h unless --all-history is specified
        start_time = None
        if not hasattr(args, 'all_history') or not args.all_history:
            start_time = datetime.now(timezone.utc) - timedelta(hours=24)
            print(f"Showing bet history from last 24 hours (use --all-history for full history)...")
            
        history = trader.get_bet_history(limit, status_filter, start_time)
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
            if 'volatility_15min' in indicators:
                print(f"15m Volatility: {indicators.get('volatility_15min', 0):.2f}%")
        else:
            print("Indicators: N/A")

    elif args.place_bet:
        if not args.bet_market or not args.outcome or not args.amount:
            print("Error: --place-bet requires --bet-market, --outcome, and --amount")
            sys.exit(1)
            
        outcome = MarketDirection.YES if args.outcome.upper() == 'YES' else MarketDirection.NO
        success = trader.place_crypto_bet(
            market_title_keyword=args.bet_market,
            outcome=outcome,
            amount=args.amount,
            max_price=args.max_price,
            use_chainlink_analysis=True
        )
        
        if success:
            print("✅ Bet placed successfully!")
        else:
            print("❌ Failed to place bet.")

    elif args.auto_bet:
        # Single auto bet based on analysis
        crypto = args.bet_market if args.bet_market else 'bitcoin'
        amount = args.amount if args.amount else 100.0
        
        print(f"Attempting informed auto-bet on {crypto} with ${amount}...")
        success = trader.place_informed_crypto_bet(
            market_title_keyword=crypto,
            amount=amount,
            confidence_threshold=args.confidence_threshold
        )
        
        if success:
            print("✅ Auto-bet placed successfully!")
        else:
            print("❌ Auto-bet conditions not met or failed.")

    elif args.start_monitoring:
        print(f"Starting auto-betting monitor (Interval: 15m, Confidence: {args.confidence_threshold})...")
        print("Press Ctrl+C to stop.")
        try:
            # This starts a background thread in trader
            trader.start_auto_betting()
            
            # Keep main thread alive to allow monitoring to run
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping monitoring...")
            trader.stop_auto_betting()

    elif args.live_monitor:
        print("Starting live monitor interface...")
        trader.start_live_monitoring()

    elif args.stop_monitoring:
        trader.stop_auto_betting()
        print("Monitoring stopped.")

    elif args.monitor_status:
        status = trader.get_auto_betting_status()
        print("\n📊 Auto-Betting Status:")
        print(f"  Running: {'✅ Yes' if status['is_monitoring'] else '❌ No'}")
        print(f"  Active Bets: {status['active_bets_count']}")
        print(f"  Check Interval: {status['check_interval']}s")

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

    elif args.positions:
        trader.list_positions()

    elif args.portfolio:
        trader.print_portfolio_summary()

    elif args.web:
        print(f"Starting web GUI server on port {args.web_port}...")

        # Auto-start betting monitor
        from poly_market_trader.web.services.trader_service import TraderService
        print("Auto-starting betting monitor (Interval: 15m)...")
        service = TraderService()
        service.start_auto_betting(confidence_threshold=args.confidence_threshold)

        print(f"Open http://localhost:{args.web_port} in your browser")
        print("Press Ctrl+C to stop the server\n")

        import uvicorn
        from poly_market_trader.web.api_server import app

        try:
            uvicorn.run(app, host="0.0.0.0", port=args.web_port)
        finally:
            print("Stopping auto-betting...")
            service.stop_auto_betting()

    elif args.realtime_monitor:
        print("Starting real-time WebSocket monitoring for arbitrage detection...")
        print("Press Ctrl+C to stop.\n")

        success = trader.start_realtime_monitoring()

        if success:
            print("✅ Real-time monitoring active!")
            print("Watching for arbitrage opportunities (YES + NO < 0.99)...\n")

            try:
                # Keep main thread alive
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping real-time monitoring...")
                trader.stop_realtime_monitoring()
        else:
            print("❌ Failed to start real-time monitoring")
            sys.exit(1)

    elif args.stop_realtime:
        trader.stop_realtime_monitoring()
        print("✅ Real-time monitoring stopped")

    elif args.realtime_status:
        status = trader.get_monitoring_status()
        prices = trader.get_realtime_prices()

        print("\n📊 Real-Time WebSocket Status:")
        print(f"  WebSocket Active: {'✅ Yes' if status['websocket_active'] else '❌ No'}")
        print(f"  WebSocket Connected: {'✅ Yes' if status['websocket_connected'] else '❌ No'}")
        print(f"  Polling Active: {'✅ Yes' if status['polling_active'] else '❌ No'}")
        print(f"  Active Bets: {status['active_bets']}")

        if prices:
            print(f"\n💹 Real-Time Prices ({len(prices)} tokens):")
            for token_id, data in list(prices.items())[:10]:
                yes_mid = data.get('yes_mid', 0)
                no_mid = data.get('no_mid', 0)
                print(f"  {token_id[:20]}... YES={yes_mid:.4f}, NO={no_mid:.4f}")
        else:
            print("\n💹 No real-time prices available (WebSocket not connected)")

    else:
        # Default: show portfolio summary and available markets
        print("Welcome to Polymarket Paper Trader!")
        print("Use --help to see available options.\n")
        trader.print_portfolio_summary()
        print("Available crypto markets:")
        trader.list_crypto_markets()

    sys.exit(0)


if __name__ == "__main__":
    main()
