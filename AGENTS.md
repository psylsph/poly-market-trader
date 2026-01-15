# Developer Guide for AI Agents

## 🚀 Quick Start

### Setup
```bash
pip install -r requirements.txt -r requirements-web.txt
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

### Linting & Formatting
This project uses `flake8` for linting.
```bash
# Run linting
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

### Testing
Use `unittest` for testing. Always run relevant tests before and after changes.

**CRITICAL:** You MUST run tests and linting after every significant code change to ensure you haven't broken anything.

```bash
# Run ALL tests (Required before finishing)
python -m unittest discover -s tests

# Run linting (Required before finishing)
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

```bash
# Run a SPECIFIC test file (Recommended for focused work)
python -m unittest tests.test_api
python -m unittest tests.test_services

# Run a SPECIFIC test class
python -m unittest tests.test_api.TestMarketDataProvider

# Run a SPECIFIC test method
python -m unittest tests.test_api.TestMarketDataProvider.test_get_markets_success
```

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
**Mandatory** for all function signatures.
```python
def get_market_prices(self, market_id: str) -> Optional[Dict]:
    """Get current prices for a market"""
    pass
```

### 3. Naming Conventions
- **Classes:** `PascalCase` (e.g., `PaperTrader`)
- **Functions/Vars:** `snake_case` (e.g., `place_bet`, `market_id`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- **Private:** `_snake_case` (e.g., `_validate_input`)

### 4. Monetary Values
**CRITICAL:** Always use `Decimal` for money. NEVER use `float`.
```python
from decimal import Decimal
amount = Decimal('100.00')  # Correct
amount = 100.00            # WRONG
```

### 5. Error Handling
Use `try-except` blocks. Log errors and return `None` or empty containers/False on failure.
```python
def fetch_data(self) -> Dict:
    try:
        # ... operation ...
        return data
    except Exception as e:
        print(f"Error fetching data: {e}")
        return {}
```

### 6. Data Models
Use `@dataclass` for data structures and `Enum` for fixed options.

## 📂 Project Structure

```text
poly-market-trader/
├── main.py                      # CLI entry point
├── requirements.txt             # Core dependencies
├── poly_market_trader/          # Main package
│   ├── api/                     # API integrations (Polymarket, Chainlink)
│   ├── models/                  # Data classes (Trade, Portfolio)
│   ├── services/                # Business logic (PaperTrader, MarketMonitor)
│   ├── web/                     # Web GUI implementation
│   └── config/                  # Settings
└── tests/                       # Unit tests (mirrors source structure)
```

## 🔑 Key Files
- `poly_market_trader/services/paper_trader.py`: Core logic for trading and portfolio management.
- `poly_market_trader/services/market_monitor.py`: Auto-betting loop and analysis.
- `poly_market_trader/api/market_data_provider.py`: Polymarket API interface.
- `poly_market_trader/models/trade.py`: Trade and Position definitions.
- `DESIGN.md`: Detailed design documents for features and fixes. Always reference this file for implementation details and technical decisions.
