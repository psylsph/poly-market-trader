# Polymarket Paper Trader - Crypto Betting Application

This application allows you to simulate betting on crypto-related markets on Polymarket without risking real money. It uses real market data from both Polymarket and Chainlink-compatible sources to simulate trades and track your virtual portfolio performance.

## Features

- **Paper Trading**: Simulate trades without using real money
- **Real Market Data**: Uses live Polymarket API data for accurate simulations
- **Chainlink Integration**: Incorporates Chainlink-compatible price feeds for informed decision-making
- **Technical Analysis**: Provides trend analysis, moving averages, and volatility metrics
- **Crypto Focus**: Automatically filters and identifies crypto-related markets
- **Portfolio Tracking**: Track your virtual balance, positions, and P&L
- **Risk Management**: Built-in risk controls to prevent overexposure
- **Automated Betting**: Auto-place bets based on Chainlink analysis and confidence thresholds
- **15-Minute Analysis**: Short-term technical analysis for quick trading decisions
- **Continuous Monitoring**: Automatic market monitoring and betting in 15-minute intervals

## Prerequisites

- Python 3.7+
- pip package manager

## Installation

1. Clone or download this repository
2. Navigate to the project directory
3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Command Line Interface

The application provides a command-line interface for various operations:

#### Check Portfolio Status
```bash
python main.py --portfolio
```

#### List Available Crypto Markets
```bash
python main.py --list-markets
```

#### Place a Manual Bet
```bash
python main.py --place-bet --bet-market bitcoin --outcome YES --amount 500 --max-price 0.6
```

#### Perform 15-Minute Chainlink Analysis
```bash
python main.py --analyze bitcoin
```

#### Place an Auto-Bet Based on 15-Minute Chainlink Analysis
```bash
python main.py --auto-bet --bet-market ethereum --amount 300 --confidence-threshold 0.5
```

#### Start Continuous Auto-Betting Monitoring
```bash
python main.py --start-monitoring
```

#### Stop Auto-Betting Monitoring
```bash
python main.py --stop-monitoring
```

#### Check Monitoring Status
```bash
python main.py --monitor-status
```

#### View Active Bets from Monitoring System
```bash
python main.py --active-bets
```

#### Python API with 15-Minute Analysis and Monitoring
```python
# Perform 15-minute Chainlink analysis
analysis = trader.get_chainlink_analysis("bitcoin", timeframe='15min')
print(f"Current price: ${analysis['current_price']:.2f}")
print(f"15-min trend: {analysis['trend']}")

# Place a bet with 15-minute analysis
success = trader.place_crypto_bet(
    market_title_keyword="bitcoin",
    outcome=MarketDirection.YES,
    amount=500.0,
    max_price=0.6,
    timeframe='15min'  # Use 15-minute analysis
)

# Place an auto-bet with 15-minute analysis
auto_success = trader.place_informed_crypto_bet(
    market_title_keyword="ethereum",
    amount=300.0,
    max_price=0.7,
    confidence_threshold=0.5,
    timeframe='15min'  # Use 15-minute analysis
)

# Start continuous monitoring and auto-betting
trader.start_auto_betting(check_interval_seconds=900)  # Check every 15 minutes

# Check monitoring status
status = trader.get_auto_betting_status()
print(f"Monitoring: {status['is_monitoring']}, Active bets: {status['active_bets_count']}")

# Get active bets
active_bets = trader.get_active_bets()
for bet in active_bets:
    print(f"Active bet: {bet['outcome'].value} on market {bet['market_id'][:8]}...")
```

#### View Active Positions
```bash
python main.py --positions
```

#### Set Custom Initial Balance
```bash
python main.py --balance 5000 --portfolio
```

### Python API

You can also use the paper trader as a Python module:

```python
from decimal import Decimal
from poly_market_trader.services.paper_trader import PaperTrader
from poly_market_trader.models.trade import MarketDirection

# Initialize the paper trader with $10,000 virtual balance
trader = PaperTrader(initial_balance=Decimal('10000.00'))

# Perform Chainlink analysis
analysis = trader.get_chainlink_analysis("bitcoin")
print(f"Current price: ${analysis['current_price']:.2f}")
print(f"Trend: {analysis['trend']}")

# Place a bet on a Bitcoin market with Chainlink analysis
success = trader.place_crypto_bet(
    market_title_keyword="bitcoin",
    outcome=MarketDirection.YES,  # Betting that the event will happen
    amount=500.0,  # Risk $500 on this bet
    max_price=0.6  # Will buy at most $0.60 per token
)

# Or place an auto-bet based on Chainlink analysis
auto_success = trader.place_informed_crypto_bet(
    market_title_keyword="ethereum",
    amount=300.0,
    max_price=0.7,
    confidence_threshold=0.5
)

# Check portfolio status
summary = trader.get_portfolio_summary()
print(f"Current Balance: ${summary['current_balance']:.2f}")
print(f"Total Value: ${summary['total_value']:.2f}")
print(f"P&L: ${summary['pnl']:.2f}")
```

## Running with Docker

You can run the application in a containerized environment using Docker.

1. **Build and start the container:**
   ```bash
   docker-compose up -d --build
   ```

2. **View logs:**
   ```bash
   docker-compose logs -f
   ```

3. **Stop the container:**
   ```bash
   docker-compose down
   ```

The web interface will be available at `http://localhost:8000`. Data (portfolio, bets) is persisted in the `data/` directory on your host machine.

## Configuration

The application can be configured by modifying `poly_market_trader/config/settings.py`:

- `DEFAULT_INITIAL_BALANCE`: Starting virtual balance (default: 10000.0)
- `CACHE_DURATION`: Cache duration for market data in seconds (default: 300)
- `CRYPTO_KEYWORDS`: Keywords used to identify crypto-related markets
- `MAX_POSITION_SIZE_PERCENT`: Maximum percentage of balance per position (default: 0.1)
- `MAX_DAILY_RISK_PERCENT`: Maximum daily risk percentage (default: 0.05)

## How It Works

1. **Market Data**: The application fetches real market data from Polymarket APIs
2. **Chainlink Integration**: Retrieves cryptocurrency price data from Chainlink-compatible sources
3. **Technical Analysis**: Calculates trends, moving averages, and volatility metrics
4. **15-Minute Analysis**: Performs short-term technical analysis for quick trading decisions
5. **Continuous Monitoring**: Automatically monitors markets and places bets in 15-minute intervals
6. **Crypto Filtering**: Markets are filtered based on crypto-related keywords
7. **Decision Making**: Uses Chainlink data to inform betting decisions
8. **Virtual Trading**: Trades are simulated using real prices but with virtual money
9. **Position Management**: Tracks your positions and calculates P&L based on market movements
10. **Portfolio Tracking**: Maintains your virtual balance and overall portfolio value

## Risk Disclaimer

This is a simulation tool for educational purposes only. Past performance does not guarantee future results. Cryptocurrency and prediction market trading involve substantial risk and may not be suitable for all investors.

## API Endpoints Used

- **Polymarket APIs**:
  - Gamma API (`https://gamma-api.polymarket.com`): For market discovery
  - CLOB API (`https://clob.polymarket.com`): For price and order book data
  - Data API (`https://data-api.polymarket.com`): For user activity data

- **Chainlink-Compatible APIs**:
  - CoinGecko API: For cryptocurrency price data and historical analysis
  - Alternative exchanges: As backup data sources

## Project Structure

```
poly-market-trader/
├── main.py                 # Main application entry point
├── example_usage.py        # Example usage script
├── test_functionality.py   # Functionality tests
├── SUMMARY.md              # Project summary
├── requirements.txt        # Python dependencies
├── poly_market_trader/     # Main package
│   ├── __init__.py
│   ├── api/                # API clients
│   │   ├── __init__.py
│   │   ├── market_data_provider.py
│   │   └── chainlink_data_provider.py
│   ├── models/             # Data models
│   │   ├── __init__.py
│   │   └── trade.py
│   ├── services/           # Business logic
│   │   ├── __init__.py
│   │   ├── paper_trader.py
│   │   └── order_executor.py
│   ├── utils/              # Utility functions
│   │   ├── __init__.py
│   │   └── helpers.py
│   └── config/             # Configuration
│       ├── __init__.py
│       └── settings.py
```

## Example Workflow

1. Start with a virtual balance of $10,000
2. Analyze cryptocurrency trends using Chainlink-compatible data
3. Browse available crypto markets
4. Place informed bets based on technical analysis
5. Track your portfolio performance
6. Close positions when you want to realize gains/losses

Try the example script to see the paper trader in action:

```bash
python example_usage.py
```

## Rate Limits

Note that the application uses free-tier APIs which may have rate limits. If you encounter "Too Many Requests" errors, wait a few minutes before retrying or consider using a paid API tier for higher rate limits.