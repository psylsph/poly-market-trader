# AGENTS.md - Developer Guide for AI Agents

## Quick Start Commands

### Setup
```bash
pip install -r requirements.txt  # Install core dependencies
pip install -r requirements-web.txt  # Install web GUI dependencies
```

### Testing
```bash
# Run all tests
python -m unittest discover -s tests

# Run specific test file
python -m unittest tests.test_api
python -m unittest tests.test_services
python -m unittest tests.test_models

# Run specific test class
python -m unittest tests.test_api.TestMarketDataProvider

# Run specific test method
python -m unittest tests.test_api.TestMarketDataProvider.test_get_markets_success

# Run with verbose output
python -m unittest discover -s tests -v

# Run with coverage
coverage run -m unittest discover -s tests
coverage report
```

### Running the Application
```bash
python main.py --portfolio              # Check portfolio status
python main.py --list-markets           # List available crypto markets
python main.py --analyze bitcoin        # Perform Chainlink analysis
python main.py --start-monitoring       # Start auto-betting monitor
python main.py --active-bets            # View active bets
python main.py --dashboard              # Combined ASCII dashboard
```

### Running the Web GUI
```bash
# Install web dependencies
pip install -r requirements-web.txt

# Start web server (runs on port 8000)
python main.py --web

# Or start on custom port
python main.py --web --web-port 8080

# Open in browser
# http://localhost:8000
```

### Running with Docker
```bash
# Build and run with docker-compose
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Code Style Guidelines

### Imports
Follow this order with blank lines between groups:
1. Standard library imports
2. Third-party imports
3. Local/relative imports

```python
# Standard library
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

# Third-party
import requests

# Local (relative imports within package)
from ..models.trade import MarketDirection, TradeType
from ..api.market_data_provider import MarketDataProvider
```

### Type Hints
Always use type hints for function signatures:
```python
def get_crypto_markets(self, use_15m_only: bool = True) -> List[Dict]:
    """Get crypto-related markets"""
    pass

def get_market_prices(self, market_id: str) -> Optional[Dict]:
    """Get current prices for a market"""
    pass
```

### Naming Conventions
- Classes: `PascalCase` (e.g., `PaperTrader`, `MarketDataProvider`)
- Functions/methods: `snake_case` (e.g., `get_crypto_markets`, `place_bet`)
- Private methods: `_snake_case` (e.g., `_extract_crypto_name`, `_is_crypto_market`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_INITIAL_BALANCE`, `GAMMA_API_BASE`)
- Variables: `snake_case`

### Data Classes
Use `@dataclass` for model classes:
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Trade:
    """Represents a single trade in the market"""
    market_id: str
    outcome: MarketDirection
    quantity: float
    price: float
    trade_type: TradeType
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
```

### Enums
Use `Enum` for fixed sets of values:
```python
from enum import Enum

class MarketDirection(Enum):
    YES = "YES"
    NO = "NO"

class TradeType(Enum):
    BUY = "buy"
    SELL = "sell"
```

### Monetary Values
**CRITICAL**: Always use `Decimal` for money, never `float`:
```python
from decimal import Decimal

# Good
amount = Decimal('500.00')
price = Decimal('0.60')
total = amount * price

# Bad
amount = 500.00  # Don't use float for money!
```

### Error Handling
Use try-except with specific exception handling. Print errors for debugging and return `None` or empty values on failure:
```python
def get_markets(self, category: str = None) -> List[Dict]:
    try:
        url = f"{self.gamma_api_base}/markets"
        response = requests.get(url, params={'category': category})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return []
```

### Docstrings
Use simple docstrings for classes and methods:
```python
def place_crypto_bet(self, market_title_keyword: str, outcome: MarketDirection,
                    amount: float, max_price: float = 1.0) -> bool:
    """
    Place a bet on a crypto-related market
    :param market_title_keyword: Keyword to identify the market (e.g., 'bitcoin')
    :param outcome: The outcome to bet on (YES/NO)
    :param amount: Amount to risk on this bet (in USD)
    :param max_price: Maximum price to pay for the outcome token
    :return: True if bet placed successfully, False otherwise
    """
```

## Testing Patterns

### Test Structure
Use Python's built-in `unittest` framework:
```python
import unittest
from unittest.mock import patch, MagicMock
from poly_market_trader.api.market_data_provider import MarketDataProvider

class TestMarketDataProvider(unittest.TestCase):
    """Test cases for the MarketDataProvider class"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        self.provider = MarketDataProvider()
```

### Mocking External APIs
Always mock external API calls:
```python
@patch('poly_market_trader.api.market_data_provider.requests.get')
def test_get_markets_success(self, mock_get):
    """Test getting markets successfully"""
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "1", "question": "Test"}]
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    result = self.provider.get_markets()
    self.assertEqual(len(result), 1)
```

## Project Structure

```
poly-market-trader/
├── main.py                      # CLI entry point
├── requirements.txt             # Dependencies (requests, python-dotenv)
├── poly_market_trader/         # Main package
│   ├── api/                    # External API integrations
│   ├── models/                 # Data models (Trade, Position, Portfolio)
│   ├── services/               # Business logic (PaperTrader, OrderExecutor)
│   ├── config/                 # Configuration (settings.py)
│   └── utils/                  # Utility functions
└── tests/                      # Test suite (unittest framework)
```

## Key Files to Know

- `poly_market_trader/services/paper_trader.py` - Main trader orchestration
- `poly_market_trader/api/market_data_provider.py` - Polymarket API integration
- `poly_market_trader/api/chainlink_data_provider.py` - CoinGecko price data
- `poly_market_trader/models/trade.py` - Trade/Position data classes
- `poly_market_trader/config/settings.py` - All configuration constants
