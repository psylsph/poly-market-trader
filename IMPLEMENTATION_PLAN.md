# Polymarket Paper Trader - Implementation Plan

**Date:** January 14, 2026
**Status:** Phase 10 Complete

---

## Executive Summary

This plan covers the complete implementation of the Polymarket Paper Trader application, including recent strategy improvements to increase win rate.

### Completed Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Core Persistence (JSON-based storage) |
| Phase 2 | ✅ Complete | Bet Tracking & Automatic Settlement |
| Phase 3 | ✅ Complete | Enhanced UI with Rich (ASCII dashboards) |
| Phase 4 | ✅ Complete | Live Monitoring Dashboard |
| Phase 5 | ✅ Complete | Web GUI (FastAPI + Vue.js SPA) |
| Phase 6 | ✅ Complete | Docker Containerization |
| Phase 7 | ✅ Complete | Testing, Polish & Documentation |
| Phase 8 | ✅ Complete | Strategy Improvements (Value Betting & RSI) |
| Phase 10 | ✅ Complete | WebSocket Real-Time Data (Faster Arbitrage Detection) |

### Active/In Progress Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 9 | 🔮 Future | Local LLM Integration (Deep Understanding) |

---

## Architecture Overview

```
poly-market-trader/
├── main.py                          # CLI entry point
├── requirements.txt                 # Core dependencies
├── poly_market_trader/
│   ├── api/
│   │   ├── market_data_provider.py  # Polymarket API
│   │   └── chainlink_data_provider.py  # Crypto Data + RSI Logic
│   ├── services/
│   │   ├── market_monitor.py        # Betting Logic (Enhanced)
│   │   └── paper_trader.py          # Main orchestrator
...
```

---

## Phase 8: Strategy Improvements (Value Betting & RSI)

**Status:** ✅ Complete

**Goal:** Increase win rate by making the bot smarter about *price* and *momentum*.

### 1. Value Betting (The "Price Check")
The bot now checks if the odds are favorable before betting:
*   **Logic:** `Confidence Score > Market Price + Margin`
*   **Example:** If we are 65% confident Bitcoin goes UP (YES), but YES shares cost $0.80, we **SKIP** (Negative EV).
*   **Margin:** 5% safety margin required.

### 2. Relative Strength Index (RSI)
Added RSI to detect overbought/oversold conditions for the "Mean Reversion" strategy:
*   **RSI > 70:** Overbought -> Expect Drop -> Bet NO on "Up" / YES on "Down"
*   **RSI < 30:** Oversold -> Expect Bounce -> Bet YES on "Up" / NO on "Down"

### 3. MACD & SMA Alignment
Added additional confirmation indicators:
*   **MACD Histogram:** Boosts confidence when MACD confirms trend direction
*   **SMA Alignment (9/20/50):** Boosts confidence when price is above/below multiple SMAs

### 4. Bug Fixes
*   Fixed market price parsing: Polymarket API returns `clobTokenIds` as JSON string, now properly parsed
*   Fixed division by zero: Added safety check `if market_price <= 0.01: return` for stale/invalid prices
*   **Note:** Some 15min markets return $0.00 prices if they just opened (no order book yet). Bot correctly skips these.

### 3. Implementation Summary

#### Step 3.1: Update ChainlinkDataProvider ✅
- [x] Add `calculate_rsi(prices, period=14)` method
- [x] Update `get_technical_indicators` to include RSI
- [x] **TEST:** 8 unit tests for RSI calculation passing

#### Step 3.2: Enhance MarketMonitor Logic ✅
- [x] Fetch current market price (YES/NO shares) before betting
- [x] Implement value gating: `if confidence < (market_price + 0.05): return`
- [x] Fix division by zero: `if market_price <= 0.01: return`
- [x] Update `_analyze_and_bet`:
    - [x] Calculate RSI from historical data
    - [x] Adjust confidence based on RSI (Boost confidence if RSI confirms trend/reversion)
    - [x] Use actual market price for `max_price` (was previously hardcoded to 0.7)
    - [x] Add MACD and SMA alignment confidence boosts
- [x] **TEST:** 9 strategy logic tests passing

#### Step 3.3: Local LLM (Future/Optional)
- [ ] *Deferred to Phase 10* - Parse complex questions using local LLM.

---

## Phase 10: Local LLM Integration (Future)

**Goal:** Use a local Large Language Model (e.g., Llama 3, Mistral via Ollama) to parse market questions for precise data extraction.

### Problem
Regex parsing (e.g., finding "Bitcoin") is brittle. It misses context like:
- "Will Bitcoin close *above* $98k?" (Target Price extraction)
- "Will Solana flip BNB by Friday?" (Relative performance)
- "Will the SEC approve an ETH ETF?" (News sentiment)

### Solution
Integrate a local LLM to structure the unstructured market question into a JSON object:
```json
{
  "asset": "Bitcoin",
  "metric": "price",
  "condition": "above",
  "target_value": 98000,
  "deadline": "2026-01-16T00:00:00Z"
}
```

### Implementation Steps
1.  **Setup Ollama:** Run a lightweight model (e.g., `mistral:7b`) locally.
2.  **Prompt Engineering:** Create a system prompt to extract structured data from market questions.
3.  **Integration:** Create an `LLMDataProvider` class to interface with the local model API.
4.  **Hybrid Logic:** Combine Chainlink data (prices) with LLM extraction (targets) for precise betting.

---

## Todo List for Phase 10

- [ ] **Setup & Infrastructure**
    - [ ] Install/Verify LMStudio setup (http://localhost:1234)
    - [ ] Pull lightweight model (e.g., `mistralai/ministral-3-14b-reasoning` or `nvidia/nemotron-3-nano`)
- [ ] **Development**
    - [ ] Create `LLMDataProvider` class
    - [ ] Design extraction prompt (JSON output)
    - [ ] Implement response caching (to save compute)
- [ ] **Integration**
    - [ ] Replace Regex logic in `MarketMonitor` with LLM call (fallback to regex if LLM fails)
    - [ ] Test with complex market questions (e.g., "Will BTC hit $100k?")

## Phase 10: WebSocket Real-Time Data

**Status:** ✅ Complete

**Goal:** Replace polling with WebSocket for sub-second market data and faster arbitrage detection.

### Problem
- 15min markets sell out in seconds
- Polling every 15 minutes is too slow
- Missing arbitrage opportunities due to latency

### Solution
Use Polymarket's Real-Time Data Socket (WebSocket) API:
- **Endpoint:** `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- **Latency:** ~100ms (vs 1-2 seconds for polling)
- **Data:** Order book updates, price changes, trades

### Implementation Summary

#### ✅ Completed Steps

1. **WebSocket Client Created:** `poly_market_trader/api/websocket_client.py`
   - `PolymarketWebSocketClient` class for connection management
   - `FastMarketMonitor` class for real-time arbitrage detection
   - Auto-reconnect with exponential backoff
   - Price history tracking (last 100 updates per market)

2. **Message Handling:** Handles both dict and list responses from WebSocket
   - Supports multiple price formats (nested 'yes'/'no' dicts, flat 'yes_bid'/'yes_ask' fields)
   - Callbacks for `on_price_update` and `on_arbitrage`

3. **PaperTrader Integration:**
   - Added `ws_client`, `ws_loop`, `ws_thread` attributes
   - `start_realtime_monitoring()` - Starts WebSocket in background thread
   - `stop_realtime_monitoring()` - Stops WebSocket connection
   - `get_realtime_prices()` - Returns current prices from WebSocket
   - `get_monitoring_status()` - Shows both polling and WebSocket status

4. **Arbitrage Detection:**
   - Checks `YES + NO < 0.99` on every price update
   - Logs realtime arbitrage opportunities with profit %
   - Places arbitrage bets automatically (YES + NO for guaranteed profit)

5. **CLI Integration:** `main.py` updated with new commands:
   - `--realtime-monitor` - Start WebSocket monitoring
   - `--stop-realtime` - Stop WebSocket monitoring
   - `--realtime-status` - Show WebSocket prices and status

6. **Comprehensive Testing:** `tests/test_websocket.py` with 22 tests:
   - WebSocket client connection tests
   - Message processing tests (dict, list, flat formats)
   - Price history tracking tests
   - Arbitrage detection tests
   - FastMarketMonitor behavior tests
   - PaperTrader integration tests

### Usage

```bash
# CLI - Start real-time monitoring
python main.py --realtime-monitor

# CLI - Check real-time status
python main.py --realtime-status

# CLI - Stop real-time monitoring
python main.py --stop-realtime

# Python API
from poly_market_trader.services.paper_trader import PaperTrader

pt = PaperTrader()

# Start real-time monitoring (WebSocket)
pt.start_realtime_monitoring()

# Check status
status = pt.get_monitoring_status()
print(f"WebSocket active: {status['websocket_active']}")

# Get current prices
prices = pt.get_realtime_prices()
for token_id, data in prices.items():
    print(f"{token_id[:20]}: YES={data['yes_mid']}, NO={data['no_mid']}")

# Stop when done
pt.stop_realtime_monitoring()
```

### Benefits
- Catch arbitrage opportunities before they disappear
- Stay synced with fast-moving 15min markets
- Reduce missed opportunities due to polling latency
- Run alongside polling monitor for redundancy

---

**Document Version:** 6.0
**Last Updated:** January 14, 2026
**Previous Version:** 5.0 (Phase 8 completion)
