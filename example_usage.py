"""
Example usage of the Polymarket Paper Trader for Crypto Betting
"""

from decimal import Decimal
from poly_market_trader.services.paper_trader import PaperTrader
from poly_market_trader.models.trade import MarketDirection


def demo_paper_trading():
    print("=== Polymarket Paper Trader Demo ===\n")

    # Initialize the paper trader with $10,000 virtual balance
    trader = PaperTrader(initial_balance=Decimal('10000.00'))

    # Show initial portfolio
    print("Initial Portfolio:")
    trader.print_portfolio_summary()

    # List some available crypto markets
    print("Available Crypto Markets:")
    trader.list_crypto_markets(limit=3)

    # Perform Chainlink analysis on Bitcoin
    print("\nPerforming Chainlink analysis on Bitcoin...")
    analysis = trader.get_chainlink_analysis("bitcoin")
    print(f"Current price: ${analysis['current_price']:.2f}" if analysis['current_price'] else "Current price: N/A")
    print(f"Trend: {analysis['trend']}")
    if analysis['indicators']:
        indicators = analysis['indicators']
        print(f"SMA: ${indicators.get('sma', 0):.2f}")
        print(f"Volatility: {indicators.get('volatility', 0):.2f}")
        print(f"Current vs SMA: {indicators.get('price_sma_ratio', 0):.2f}")

    # Place a sample bet with 15-minute Chainlink analysis
    print("\nPlacing a bet on Bitcoin market with 15-minute Chainlink analysis...")
    success = trader.place_crypto_bet(
        market_title_keyword="bitcoin",
        outcome=MarketDirection.YES,  # Betting that the event will happen
        amount=500.0,  # Risk $500 on this bet
        max_price=0.6,  # Will buy at most $0.60 per token
        timeframe='15min'  # Use 15-minute analysis
    )

    if success:
        print("Bet placed successfully!")
    else:
        print("Failed to place bet. Trying with different parameters...")
        # Try with a more generic keyword
        success = trader.place_crypto_bet(
            market_title_keyword="crypto",
            outcome=MarketDirection.YES,
            amount=500.0,
            max_price=0.6
        )
        if success:
            print("Bet placed successfully!")

    # Place an auto bet based on 15-minute Chainlink analysis
    print("\nPlacing an auto bet based on 15-minute Chainlink analysis...")
    auto_success = trader.place_informed_crypto_bet(
        market_title_keyword="ethereum",
        amount=300.0,
        max_price=0.7,
        confidence_threshold=0.5,
        timeframe='15min'  # Use 15-minute analysis
    )

    if auto_success:
        print("Auto bet placed successfully based on Chainlink analysis!")
    else:
        print("Auto bet not placed (either no matching market or low confidence)")

    # Show updated portfolio
    print("\nPortfolio after placing bets:")
    trader.print_portfolio_summary()

    # Show active positions
    print("Active positions:")
    trader.list_positions()

    print("\nDemo completed!")


if __name__ == "__main__":
    demo_paper_trading()