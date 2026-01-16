# Developer Guide for AI Agents

## 🚀 Quick Start

### Setup
```bash
# Install core dependencies
pip install -r requirements.txt

# Install web dependencies (optional, for web GUI)
pip install -r requirements-web.txt
```

### Running the App
```bash
python main.py --portfolio           # Check status
python main.py --web                 # Start Web GUI (auto-starts monitoring)
python main.py --start-monitoring    # Start CLI auto-betting
```

### Todo List Management
**CRITICAL:** Always maintain and update todo list when implementing features or fixes:

1. **Create Initial Todo List**: Before starting any non-trivial task, create a comprehensive todo list
2. **Update Progress**: Mark tasks as `in_progress` when working on them and `completed` when done
3. **Keep Dates**: Update todo list timestamps regularly to track progress
4. **Use Todowrite**: Always use `todowrite` tool to update todos (not just Todoread)

Example:
```python
# Create todos before implementation
todowrite(todos=[
    {"id": "1", "content": "Add validation logic", "status": "pending", "priority": "high"},
    {"id": "2", "content": "Write unit tests", "status": "pending", "priority": "medium"}
])

# Mark as in_progress when working
todowrite(todos=[..., {"id": "1", "content": "Add validation logic", "status": "in_progress", ...}])

# Mark as completed when done
todowrite(todos=[..., {"id": "1", "content": "Add validation logic", "status": "completed", ...}])
```

## 🛠 Development Workflow

### Testing
**CRITICAL:** You MUST run tests and linting after every significant code change.

```bash
# Run ALL tests (Required before finishing)
python -m unittest discover -s tests

# Run a SPECIFIC test file (Recommended for focused work)
python -m unittest tests.test_api
python -m unittest tests.test_services
python -m unittest tests.test_settlement

# Run a SPECIFIC test class
python -m unittest tests.test_api.TestMarketDataProvider

# Run a SPECIFIC test method
python -m unittest tests.test_api.TestMarketDataProvider.test_get_markets_success

# Run tests with verbose output
python -m unittest tests.test_settlement -v

# Run tests matching a pattern
python -m unittest tests.test_* -k settlement
```

### Linting & Code Quality
This project uses `flake8` for linting with custom configuration.

```bash
# Basic linting for critical errors
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Full linting with complexity and line length checks
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

# Lint specific file
flake8 poly_market_trader/services/market_monitor.py

# Lint with ignore patterns (if needed)
flake8 . --ignore=E501,W503
```

### Pre-commit Checks
**MANDATORY:** Before committing, ensure:
1. All tests pass: `python -m unittest discover -s tests`
2. Linting passes: `flake8 . --count --select=E9,F63,F7,F82`
3. No syntax errors: `python -m py_compile poly_market_trader/**/*.py`

## 📐 Code Style Guidelines

### 1. Imports
Order: Standard lib -> Third-party -> Local.
```python
# Standard library
from typing import Dict, List, Optional
from decimal import Decimal

# Third-party
import requests

# Local
from ..models.trade import MarketDirection
```

### 2. Type Hints
**Mandatory** for all function signatures. Use specific types, not `Any`.
```python
def get_market_prices(self, market_id: str) -> Optional[Dict]:
    """Get current prices for a market"""
    pass

def place_bet(self, amount: Decimal, outcome: MarketDirection) -> bool:
    """Place a bet with precise decimal amount"""
    pass
```

### 3. Naming Conventions
- **Classes:** `PascalCase` (e.g., `PaperTrader`, `BetTracker`)
- **Functions/Vars:** `snake_case` (e.g., `place_bet`, `market_id`, `current_price`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- **Private:** `_snake_case` (e.g., `_validate_input`, `_sync_active_bets`)
- **Test Classes:** `Test{CamelCase}` (e.g., `TestBetSettlement`)
- **Test Methods:** `test_{descriptive_name}` (e.g., `test_active_bets_persistence`)

### 4. Monetary Values
**CRITICAL:** Always use `Decimal` for money. NEVER use `float`.
```python
from decimal import Decimal
amount = Decimal('100.00')  # Correct
amount = 100.00            # WRONG - loses precision
```

### 5. Error Handling
Use `try-except` blocks. Log errors and return sensible defaults on failure.
```python
def fetch_data(self) -> Dict:
    try:
        # ... operation ...
        return data
    except Exception as e:
        print(f"Error fetching data: {e}")
        return {}

def get_price_at_time(self, crypto: str, timestamp: datetime) -> Optional[Decimal]:
    try:
        price = self._fetch_price(crypto, timestamp)
        return Decimal(str(price))  # Convert to Decimal safely
    except Exception as e:
        print(f"Error getting price for {crypto}: {e}")
        return None
```

### 6. Data Models
Use `@dataclass` for data structures and `Enum` for fixed options.
```python
from dataclasses import dataclass
from enum import Enum

class MarketDirection(Enum):
    YES = "YES"
    NO = "NO"

@dataclass
class Trade:
    market_id: str
    outcome: MarketDirection
    quantity: float
    price: Decimal  # Always use Decimal for money
    trade_type: TradeType
```

### 7. Documentation
- **Docstrings:** Required for all public classes and methods
- **Comments:** Use for complex logic, not obvious code
- **Type hints:** Complement docstrings, don't replace them

### 8. File Structure
- **One class per file** when possible
- **Related functionality** grouped in modules
- **Tests mirror source structure** (`tests/test_api.py` for `poly_market_trader/api/`)

### 9. Constants and Configuration
- **Magic numbers** should be constants at module level
- **Configuration** should be centralized in `config/` module
- **Environment variables** for sensitive data

### 10. Logging
Use `logging` module, not `print` statements in production code.
```python
import logging
logger = logging.getLogger(__name__)

def process_bet(self, bet_data: Dict):
    logger.info(f"Processing bet for market {bet_data['market_id']}")
    try:
        # ... processing logic ...
        logger.debug("Bet processed successfully")
    except Exception as e:
        logger.error(f"Failed to process bet: {e}")
        raise
```

## 📂 Project Structure

```text
poly-market-trader/
├── main.py                      # CLI entry point
├── requirements.txt             # Core dependencies
├── requirements-web.txt         # Web GUI dependencies
├── poly_market_trader/          # Main package
│   ├── api/                     # API integrations (Polymarket, Chainlink)
│   ├── models/                  # Data classes (Trade, Portfolio)
│   ├── services/                # Business logic (PaperTrader, MarketMonitor)
│   ├── storage/                 # Data persistence (BetTracker, JSON files)
│   ├── web/                     # Web GUI implementation
│   └── config/                  # Settings
├── tests/                       # Unit tests (mirrors source structure)
└── data/                        # Persistent data (active_bets.json, bet_history.json)
```

## 🔑 Key Files
- `poly_market_trader/services/paper_trader.py`: Core logic for trading and portfolio management.
- `poly_market_trader/services/market_monitor.py`: Auto-betting loop and analysis.
- `poly_market_trader/api/market_data_provider.py`: Polymarket API interface.
- `poly_market_trader/api/chainlink_data_provider.py`: Chainlink price feeds and technical indicators.
- `poly_market_trader/storage/bet_tracker.py`: Bet persistence and settlement logic.
- `poly_market_trader/models/trade.py`: Trade and Position definitions.
- `main.py`: CLI interface with comprehensive argument parsing.
- `DESIGN.md`: **CRITICAL** - System architecture and design decisions. **MUST be kept up-to-date** with any architectural changes, new features, or significant modifications to the codebase.

## 💡 Development Best Practices

- **NEVER commit changes** unless explicitly requested by the user
- **Always run tests and linting** after significant code changes
- **Use `Decimal` for all monetary calculations** - precision matters
- **Handle timezones properly** - use `timezone.utc` for timestamps
- **Prefer composition over inheritance** for service classes
- **Write tests for new features** before implementation
- **Mock external APIs** and test edge cases
- **Never log sensitive data** (API keys, private keys)
- **Validate all inputs** from external sources
- **ALWAYS update DESIGN.md** when making architectural changes, adding new features, or implementing significant modifications to the codebase
