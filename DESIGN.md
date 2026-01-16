# Polymarket Paper Trader - Design Document

## 📋 Overview

Polymarket Paper Trader is an automated crypto betting system that uses real-time Chainlink price data to place bets on Polymarket's binary options markets. The system simulates trading without risking real money, providing a safe environment for testing trading strategies.

## 🏗️ System Architecture

### Core Components

#### 1. **MarketMonitor** (`poly_market_trader/services/market_monitor.py`)
**Responsibility**: Orchestrates the entire trading loop and manages active positions.

**Key Functions**:
- `_monitor_loop()`: Main 15-minute cycle that scans markets, places bets, settles expired bets, and manages positions
- `_check_for_opportunities()`: Scans for new betting opportunities using Chainlink analysis
- `_analyze_and_bet()`: Analyzes individual markets and places bets based on strategy
- `_check_and_settle_resolved_bets()`: Handles settlement of expired markets
- `_manage_active_positions()`: Monitors and potentially exits profitable positions

**State Management**:
- Maintains `active_bets` list (synced with BetTracker)
- Coordinates with Portfolio, OrderExecutor, and BetTracker
- Handles LLM integration for advanced decision making

#### 2. **BetTracker** (`poly_market_trader/storage/bet_tracker.py`)
**Responsibility**: Persistent storage and settlement logic for bets.

**Key Functions**:
- `add_active_bet()`: Stores new bet information in JSON files
- `settle_bet()`: Processes market outcomes and updates portfolio
- `get_active_bets()`: Retrieves bets for monitoring
- `_determine_outcome()`: Calculates win/loss based on price movements

**Data Storage**:
- `active_bets.json`: Currently monitored positions
- `bet_history.json`: Completed settled bets
- Thread-safe JSON operations

#### 3. **ChainlinkDataProvider** (`poly_market_trader/api/chainlink_data_provider.py`)
**Responsibility**: Fetches and analyzes cryptocurrency price data using Chainlink feeds.

**Key Functions**:
- `get_current_price()`: Latest price for a cryptocurrency
- `get_historical_prices()`: Price history for analysis
- `get_technical_indicators()`: RSI, MACD, SMA, ADX, Bollinger Bands
- `get_recent_trend_15min()`: Short-term trend analysis

**Technical Indicators**:
- **ADX (Average Directional Index)**: Trend strength (25+ = strong trend, avoid mean reversion)
- **RSI (Relative Strength Index)**: Overbought/oversold conditions
- **MACD**: Momentum and trend changes
- **Bollinger Bands**: Volatility and price levels
- **SMA Alignment**: Multi-timeframe trend confirmation

#### 4. **MarketDataProvider** (`poly_market_trader/api/market_data_provider.py`)
**Responsibility**: Interface to Polymarket API for market data and trading.

**Key Functions**:
- `get_crypto_markets()`: Retrieves available crypto markets
- `get_market_prices()`: Current YES/NO prices for markets
- `get_market_by_id()`: Detailed market information

#### 5. **OrderExecutor** (`poly_market_trader/services/order_executor.py`)
**Responsibility**: Handles trade execution and position management.

**Key Functions**:
- `place_buy_order()`: Places market/limit orders
- `place_sell_order()`: Closes positions
- `execute_trade()`: Core trade execution logic

#### 6. **Portfolio** (`poly_market_trader/models/portfolio.py`)
**Responsibility**: Virtual portfolio management with precise decimal accounting.

**Key Functions**:
- `update_balance()`: Adjusts cash balance
- `add_position()` / `remove_position()`: Position tracking
- `get_total_value()`: Portfolio valuation

#### 7. **LLM Provider** (`poly_market_trader/api/llm_provider.py`) [Optional]
**Responsibility**: Advanced decision making using local LLM for market analysis.

**Integration Points**:
- Market context preparation
- Decision making (YES/NO/SKIP/BOTH)
- Stake factor calculation
- Arbitrage detection

## 🔄 Data Flow

### 1. **Market Scanning Phase**
```
MarketDataProvider.get_crypto_markets() → Filter 15min markets
    ↓
For each market:
    ChainlinkDataProvider.get_technical_indicators()
    LLMProvider.analyze_market() [if enabled]
    ↓
    Strategy Decision (Mean Reversion vs Trend Following)
    ↓
    Bet Placement via OrderExecutor
    ↓
    BetTracker.add_active_bet()
```

### 2. **Settlement Phase**
```
Check active_bets for expired markets (end_time + 5min buffer)
    ↓
For each expired market:
    BetTracker.settle_bet()
        ↓
        ChainlinkDataProvider._determine_outcome()
        ↓
        Portfolio.update_balance()
        ↓
        Move to bet_history.json
```

### 3. **Position Management Phase**
```
For each active position:
    Monitor current PnL
    LLM re-evaluation [if enabled]
    ↓
    Take Profit / Stop Loss / Hold decisions
    ↓
    OrderExecutor.place_sell_order() [if selling]
```

## 📊 Trading Strategy

### **Primary Strategy: Mean Reversion**
**Core Principle**: Markets tend to revert to mean after extreme moves.

**Entry Conditions**:
- **Bullish Trend + Weak Momentum**: Bet NO (expect pullback)
- **Bearish Trend + Weak Momentum**: Bet YES (expect bounce)

**ADX Filter**: Only trade when ADX < 25 (weak trend = safer reversion)

**Technical Confirmations**:
- RSI > 70: Confirms NO bet (overbought)
- RSI < 30: Confirms YES bet (oversold)
- MACD divergence: Momentum confirmation
- Bollinger Bands: Extreme price levels

### **Arbitrage Detection**
**Opportunity**: When YES + NO < 0.99 (market inefficiency)

**Execution**: Place bets on both outcomes for guaranteed profit

**Sizing**: 10% of portfolio balance per arbitrage opportunity

### **Position Management**
**Take Profit**: Exit when position > 40% gain
**Stop Loss**: Exit when position < -50% loss
**LLM Override**: AI can recommend early exit based on changing conditions

## ⚙️ Configuration & Settings

### Environment Variables
- `OPENAI_API_KEY`: For LLM integration
- Database/API credentials (future expansion)

### Constants
- `CHECK_INTERVAL`: 15 minutes between market scans
- `SETTLEMENT_BUFFER`: 5 minutes after market close
- `ADX_THRESHOLD`: 25 for strong trend detection
- `DEFAULT_STAKE_PERCENT`: 5% of balance per bet

### Risk Management
- **Maximum bet size**: 5% of portfolio per position
- **Arbitrage allocation**: 10% of portfolio
- **Stop loss**: -50% position loss
- **Take profit**: +40% position gain

## 🛡️ Error Handling & Resilience

### **API Failures**
- **Chainlink data**: Fallback to cached data, skip trade if unavailable
- **Polymarket API**: Retry with exponential backoff
- **LLM service**: Graceful degradation to algorithmic trading

### **Data Validation**
- **Price validation**: Reject invalid/zero prices
- **Market filtering**: Skip non-crypto or malformed markets
- **Bet validation**: Ensure sufficient balance and reasonable quantities

### **State Persistence**
- **JSON corruption**: Backup and recreate corrupted files
- **Concurrent access**: File locking for thread safety
- **Recovery**: Load last known good state on restart

## 📈 Performance Considerations

### **Monitoring Efficiency**
- 15-minute cycles to balance responsiveness vs API limits
- Parallel market analysis where possible
- Caching of expensive computations

### **Memory Management**
- Bounded active bets list
- Periodic cleanup of old history
- Efficient JSON serialization

### **API Rate Limiting**
- Respect Chainlink/Binance API limits
- Intelligent retry strategies
- Circuit breaker patterns for failing endpoints

## 🔮 Future Extensibility

### **Additional Strategies**
- Trend following (opposite of current mean reversion)
- Multi-timeframe analysis
- Machine learning models
- Social sentiment integration

### **New Markets**
- Non-crypto assets (stocks, commodities)
- Sports betting
- Political markets
- Weather derivatives

### **Advanced Features**
- Web dashboard with real-time charts
- Backtesting framework
- Risk analytics and reporting
- Multi-account management

### **Infrastructure**
- Database backend (PostgreSQL/MySQL)
- Docker containerization
- Kubernetes deployment
- Monitoring and alerting

## 🧪 Testing Strategy

### **Unit Tests**
- Component isolation with mocks
- Edge case coverage (API failures, invalid data)
- Business logic validation

### **Integration Tests**
- End-to-end settlement flows
- Multi-market scenarios
- Concurrent operation testing

### **Performance Tests**
- API rate limit handling
- Memory usage monitoring
- Response time validation

---

*This document should be updated whenever significant architectural changes are made to the system.*</content>
<parameter name="filePath">/home/stuart/repos/poly-market-trader/DESIGN.md