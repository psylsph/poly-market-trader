# Polymarket Paper Trader Configuration

# API Settings
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"

# Default settings
DEFAULT_INITIAL_BALANCE = 10000.0  # Starting virtual balance
CACHE_DURATION = 300  # 5 minutes cache duration for market data
DEFAULT_MAX_PRICE = 1.0  # Default maximum price for buying tokens

# Crypto keywords to identify crypto-related markets
CRYPTO_KEYWORDS = [
    'bitcoin', 'btc',
    'ethereum', 'eth',
    'solana', 'sol',
    'ripple', 'xrp'
]

# Risk management
MAX_POSITION_SIZE_PERCENT = 0.1  # Max 10% of balance per position
MAX_DAILY_RISK_PERCENT = 0.05  # Max 5% daily risk