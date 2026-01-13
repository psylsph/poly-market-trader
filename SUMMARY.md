# Polymarket Paper Trader - Crypto Betting Application

## Overview

This application allows you to simulate betting on crypto-related markets on Polymarket without risking real money. It uses real market data from both Polymarket and Chainlink-compatible sources to simulate trades and track your virtual portfolio performance.

## Key Features

1. **Paper Trading**: Simulate trades without using real money
2. **Real Market Data**: Uses live Polymarket API data for accurate simulations
3. **Chainlink Integration**: Incorporates Chainlink-compatible price feeds for informed decision-making
4. **Technical Analysis**: Provides trend analysis, moving averages, and volatility metrics
5. **Crypto Focus**: Automatically filters and identifies crypto-related markets
6. **Portfolio Tracking**: Track your virtual balance, positions, and P&L
7. **Risk Management**: Built-in risk controls to prevent overexposure
8. **Automated Betting**: Auto-place bets based on Chainlink analysis and confidence thresholds
9. **15-Minute Analysis**: Short-term technical analysis for quick trading decisions
10. **Continuous Monitoring**: Automatic market monitoring and betting in 15-minute intervals
11. **Data Persistence**: Portfolio and bet history saved between sessions
12. **Live Dashboard**: Real-time terminal dashboard with combined views

## Architecture

The application consists of several key components:

- **PaperTrader**: Main class that orchestrates the trading functionality
- **MarketDataProvider**: Fetches real market data from Polymarket APIs
- **ChainlinkDataProvider**: Retrieves cryptocurrency price data from Chainlink-compatible sources
- **OrderExecutor**: Simulates order execution without real money
- **Portfolio**: Manages virtual funds and tracks positions
- **Trade Models**: Defines trade and position structures

## API Integration

The application integrates with multiple APIs:

- **Polymarket APIs**:
  - Gamma API (`https://gamma-api.polymarket.com`): For market discovery
  - CLOB API (`https://clob.polymarket.com`): For price and order book data
  - Data API (`https://data-api.polymarket.com`): For user activity data

- **Chainlink-Compatible APIs**:
  - CoinGecko API: For cryptocurrency price data and historical analysis
  - Alternative exchanges: As backup data sources

## Usage Examples

### Command Line Interface
```bash
# Check portfolio status
python main.py --portfolio

# List available crypto markets
python main.py --list-markets

# Perform Chainlink analysis
python main.py --analyze bitcoin

# Place a manual bet
python main.py --place-bet --bet-market bitcoin --outcome YES --amount 500 --max-price 0.6

# Place an auto-bet based on Chainlink analysis
python main.py --auto-bet --bet-market ethereum --amount 300 --confidence-threshold 0.5

# View active positions
python main.py --positions
```

### Python API
```python
from decimal import Decimal
from poly_market_trader.services.paper_trader import PaperTrader
from poly_market_trader.models.trade import MarketDirection

# Initialize the paper trader
trader = PaperTrader(initial_balance=Decimal('10000.00'))

# Perform Chainlink analysis
analysis = trader.get_chainlink_analysis("bitcoin")
print(f"Current price: ${analysis['current_price']:.2f}")
print(f"Trend: {analysis['trend']}")

# Place a bet on a Bitcoin market with Chainlink analysis
success = trader.place_crypto_bet(
    market_title_keyword="bitcoin",
    outcome=MarketDirection.YES,
    amount=500.0,
    max_price=0.6
)

# Or place an auto-bet based on Chainlink analysis
auto_success = trader.place_informed_crypto_bet(
    market_title_keyword="ethereum",
    amount=300.0,
    max_price=0.7,
    confidence_threshold=0.5
)
```

## Configuration

The application can be configured by modifying `poly_market_trader/config/settings.py`:

- `DEFAULT_INITIAL_BALANCE`: Starting virtual balance
- `CACHE_DURATION`: Cache duration for market data
- `CRYPTO_KEYWORDS`: Keywords to identify crypto-related markets
- Risk management parameters

## Testing

The application has been tested and verified to work correctly. The test suite confirms:

- ✓ Proper initialization of trader with virtual balance
- ✓ Correct identification of crypto-related markets
- ✓ Successful placement of simulated bets
- ✓ Accurate portfolio state updates
- ✓ Proper position tracking
- ✓ Chainlink data integration and analysis
- ✓ Automated betting based on technical indicators

## Risk Disclaimer

This is a simulation tool for educational purposes only. Past performance does not guarantee future results. Cryptocurrency and prediction market trading involve substantial risk and may not be suitable for all investors.

## Conclusion

The Polymarket Paper Trader provides a safe environment to practice crypto market betting strategies without financial risk. It combines real market conditions from Polymarket with technical analysis from Chainlink-compatible data sources, allowing users to make more informed betting decisions while maintaining complete separation from real money transactions.

---

## Recent Updates (January 12, 2026)

### Phase 1-4 Completed
- ✅ Data persistence (JSON storage)
- ✅ Bet tracking and automatic settlement
- ✅ Enhanced UI with Rich library
- ✅ Live monitoring dashboard

### In Progress
- 🔄 Phase 5: Web GUI (FastAPI + Vue.js SPA)
- ⏳ Phase 6: Docker containerization

### New Commands

```bash
# Persistence commands
python main.py --reset-portfolio        # Reset to $10,000
python main.py --settle-bets            # Manually settle bets
python main.py --bet-history            # Show settled bets
python main.py --active-bets            # Show active bets

# Dashboard commands
python main.py --dashboard              # Combined live dashboard
python main.py --live-monitor           # Live monitoring
```

### Data Files
Portfolio, active bets, and bet history are now saved to `data/` directory and persist between sessions.

### Documentation
- See `IMPLEMENTATION_PLAN.md` for detailed roadmap
- See `AGENTS.md` for developer commands