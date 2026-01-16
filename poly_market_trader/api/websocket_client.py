import asyncio
import json
import websockets
import time
from typing import Dict, Optional, Callable
from datetime import datetime
from threading import Thread, Lock
from collections import deque


class PolymarketWebSocketClient:
    """
    Real-time WebSocket client for Polymarket CLOB data.
    Provides sub-second updates for market prices and order books.
    
    Endpoint: wss://ws-subscriptions-clob.polymarket.com/ws/market
    """
    
    def __init__(self):
        self.ws = None
        self.ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        self.is_connected = False
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_attempts = 10
        self.reconnect_count = 0
        
        # Store latest market data
        self.market_data: Dict[str, Dict] = {}
        self.market_lock = Lock()
        
        # Price history for arbitrage detection (last 100 updates per market)
        self.price_history: Dict[str, deque] = {}
        
        # Callback for new price updates
        self.on_price_update: Optional[Callable] = None
        
        # Callback for arbitrage opportunity
        self.on_arbitrage: Optional[Callable] = None
        
        # Tracking
        self.subscribed_markets: set = set()
    
    async def connect(self) -> bool:
        """Connect to Polymarket WebSocket"""
        try:
            self.ws = await websockets.connect(self.ws_url)
            self.is_connected = True
            self.reconnect_count = 0
            print(f"✅ Connected to Polymarket WebSocket: {self.ws_url}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to WebSocket: {e}")
            self.is_connected = False
            return False
    
    async def subscribe_markets(self, token_ids: list[str]) -> bool:
        """Subscribe to market updates by token IDs"""
        if not self.is_connected or not self.ws:
            print("⚠️ Not connected to WebSocket")
            return False
        
        message = {
            "type": "market",
            "assets_ids": token_ids
        }
        
        try:
            await self.ws.send(json.dumps(message))
            for tid in token_ids:
                self.subscribed_markets.add(tid)
            print(f"📡 Subscribed to {len(token_ids)} token IDs")
            return True
        except Exception as e:
            print(f"❌ Failed to subscribe: {e}")
            return False
    
    async def subscribe_all_crypto_markets(self) -> bool:
        """Subscribe to short-term crypto markets (15m, 1h, 4h) for arbitrage"""
        from poly_market_trader.api.market_data_provider import MarketDataProvider

        market_data = MarketDataProvider()
        token_ids = market_data.get_crypto_asset_ids(limit=200)  # Get up to 200 asset IDs

        if token_ids:
            return await self.subscribe_markets(token_ids)
        return False
    
    async def listen(self):
        """Listen for messages"""
        if not self.ws:
            return
        
        try:
            async for message in self.ws:
                await self._handle_message(message)
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
            self.is_connected = False
            await self._reconnect()
    
    async def _handle_message(self, message):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # Handle both dict and list responses
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        await self._process_single_message(item)
                return
            
            # Handle dict response
            if isinstance(data, dict):
                await self._process_single_message(data)
                
        except json.JSONDecodeError:
            pass
    
    async def _process_single_message(self, data: dict):
        """Process a single message dict"""
        try:
            msg_type = data.get('type', '')
            
            if msg_type == 'book' or msg_type == 'price_change':
                await self._handle_price_update(data)
            elif msg_type == 'last_trade_price':
                await self._handle_trade(data)
            elif msg_type == 'subscribed':
                print(f"📡 Subscription confirmed: {data.get('message', '')}")
            elif msg_type == 'error':
                print(f"❌ WebSocket error: {data.get('message', data)}")
        except Exception as e:
            print(f"Error processing message: {e}")
    
    async def _handle_price_update(self, data: dict):
        """Handle price update from order book"""
        # Try different field names for asset/token ID
        asset_id = (data.get('asset_id') or 
                   data.get('token_id') or 
                   data.get('asset') or
                   data.get('market_id') or
                   data.get('id'))
        
        if not asset_id:
            return
        
        # Extract prices from various possible formats
        yes_bid = 0.0
        yes_ask = 0.0
        no_bid = 0.0
        no_ask = 0.0
        
        # Format 1: Nested 'yes'/'no' dicts
        if 'yes' in data and isinstance(data['yes'], dict):
            yes_bid = float(data['yes'].get('best_bid', 0) or data['yes'].get('bid', 0) or 0)
            yes_ask = float(data['yes'].get('best_ask', 0) or data['yes'].get('ask', 0) or 0)
        elif 'yes_bid' in data:
            yes_bid = float(data.get('yes_bid', 0) or 0)
            yes_ask = float(data.get('yes_ask', 0) or 0)
        
        if 'no' in data and isinstance(data['no'], dict):
            no_bid = float(data['no'].get('best_bid', 0) or data['no'].get('bid', 0) or 0)
            no_ask = float(data['no'].get('best_ask', 0) or data['no'].get('ask', 0) or 0)
        elif 'no_bid' in data:
            no_bid = float(data.get('no_bid', 0) or 0)
            no_ask = float(data.get('no_ask', 0) or 0)
        
        # Calculate mid prices
        yes_mid = (yes_bid + yes_ask) / 2 if yes_bid > 0 and yes_ask > 0 else (yes_bid or yes_ask)
        no_mid = (no_bid + no_ask) / 2 if no_bid > 0 and no_ask > 0 else (no_bid or no_ask)
        
        # Store market data (use asset_id as key)
        with self.market_lock:
            self.market_data[asset_id] = {
                'yes_bid': yes_bid,
                'yes_ask': yes_ask,
                'yes_mid': yes_mid,
                'no_bid': no_bid,
                'no_ask': no_ask,
                'no_mid': no_mid,
                'timestamp': datetime.now().isoformat()
            }
            
            # Track price history
            if asset_id not in self.price_history:
                self.price_history[asset_id] = deque(maxlen=100)
            self.price_history[asset_id].append({
                'yes_mid': yes_mid,
                'no_mid': no_mid,
                'timestamp': time.time()
            })
        
        # Check for arbitrage
        if yes_mid > 0 and no_mid > 0:
            price_sum = yes_mid + no_mid
            if price_sum < 0.99:
                arbitrage_info = {
                    'token_id': asset_id,
                    'yes_price': yes_mid,
                    'no_price': no_mid,
                    'sum': price_sum,
                    'profit': (1.0 - price_sum) * 100
                }
                print(f"🎯 ARBITRAGE: {asset_id[:20]}... YES={yes_mid:.4f}, NO={no_mid:.4f}, Profit={arbitrage_info['profit']:.1f}%")
                if self.on_arbitrage:
                    self.on_arbitrage(arbitrage_info)
        
        # Trigger callback
        if self.on_price_update:
            self.on_price_update(asset_id, yes_mid, no_mid)
    
    async def _handle_trade(self, data: dict):
        """Handle trade notification"""
        asset_id = data.get('asset_id')
        if asset_id:
            print(f"📊 Trade: {asset_id[:20]}... {data.get('side')} {data.get('size')} @ {data.get('price')}")
    
    async def _reconnect(self):
        """Attempt to reconnect with exponential backoff"""
        if self.reconnect_count >= self.max_reconnect_attempts:
            print("❌ Max reconnection attempts reached")
            return
        
        self.reconnect_count += 1
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_count - 1)), 300)
        
        print(f"🔄 Reconnecting in {delay}s (attempt {self.reconnect_count}/{self.max_reconnect_attempts})...")
        
        await asyncio.sleep(delay)
        
        if await self.connect():
            # Re-subscribe to markets
            if self.subscribed_markets:
                await self.subscribe_markets(list(self.subscribed_markets))
            asyncio.create_task(self.listen())
    
    def get_market_price(self, token_id: str) -> Optional[Dict]:
        """Get latest price for a token"""
        with self.market_lock:
            return self.market_data.get(token_id)
    
    def get_all_prices(self) -> Dict[str, Dict]:
        """Get all market prices"""
        with self.market_lock:
            return dict(self.market_data)
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            print("🔌 Disconnected from WebSocket")


class FastMarketMonitor:
    """
    Fast market monitor using WebSocket for real-time data.
    Checks for arbitrage and betting opportunities much faster than polling.
    """
    
    def __init__(self, portfolio=None, order_executor=None, market_data=None):
        self.ws_client = PolymarketWebSocketClient()
        self.is_running = False
        self.fast_check_interval = 1  # Check every 1 second via WebSocket
        self.slow_poll_interval = 60  # Full poll every 60 seconds
        
        # Trading settings
        self.arbitrage_threshold = 0.99
        self.min_profit_threshold = 1.0  # 1% minimum profit for arbitrage
        
        # Track markets we've already placed bets on
        self.bet_history = set()
        
        # Order execution
        self.portfolio = portfolio
        self.order_executor = order_executor
        self.market_data = market_data
        
        # Token ID to Market ID mapping
        self.token_to_market: Dict[str, str] = {}
        
        # Cache for market info
        self._market_cache = {}
        self._last_cache_update = 0
        self._cache_ttl = 300  # 5 minutes
    
    async def start(self) -> bool:
        """Start the fast market monitor"""
        print("🚀 Starting Fast Market Monitor (WebSocket)...")
        
        # Connect to WebSocket
        if not await self.ws_client.connect():
            print("❌ Failed to connect to WebSocket, falling back to polling mode")
            return False
        
        # Subscribe to crypto markets
        await self.ws_client.subscribe_all_crypto_markets()
        
        # Set up callbacks
        self.ws_client.on_arbitrage = self._handle_arbitrage
        self.ws_client.on_price_update = self._handle_price_update
        
        self.is_running = True
        
        # Start listening in background
        asyncio.create_task(self.ws_client.listen())
        
        # Also run a periodic poll to catch any missed updates
        asyncio.create_task(self._periodic_poll())
        
        print("✅ Fast Market Monitor running!")
        return True
    
    async def _periodic_poll(self):
        """Periodic full poll to catch any missed markets"""
        while self.is_running:
            await asyncio.sleep(self.slow_poll_interval)
            if self.is_running:
                print("🔄 Periodic market refresh...")
                await self.ws_client.subscribe_all_crypto_markets()
    
    def _handle_arbitrage(self, arbitrage_info: dict):
        """Handle arbitrage opportunity detected via WebSocket"""
        token_id = arbitrage_info['token_id']
        
        if token_id in self.bet_history:
            return
        
        if arbitrage_info['profit'] < self.min_profit_threshold:
            return
        
        yes_price = arbitrage_info['yes_price']
        no_price = arbitrage_info['no_price']
        
        print(f"\n🎯 FAST ARBITRAGE DETECTED! {token_id[:20]}...")
        print(f"   YES={yes_price:.4f}, NO={no_price:.4f}")
        print(f"   Profit: {arbitrage_info['profit']:.1f}%")
        
        # Find market_id for this token
        market_id = self._find_market_for_token(token_id)
        if not market_id:
            print(f"   ⚠️ Could not find market for token {token_id[:20]}...")
            self.bet_history.add(token_id)
            return
        
        # Check if we have order executor
        if not self.order_executor:
            print(f"   ℹ️ Order executor not configured, skipping bet placement")
            self.bet_history.add(token_id)
            return
        
        # Calculate bet amount (10% of balance, max $500)
        if self.portfolio:
            bet_amount = min(500.0, float(self.portfolio.current_balance) * 0.1)
        else:
            bet_amount = 100.0  # Default
        
        if bet_amount < 10:
            print(f"   ⚠️ Insufficient balance for arbitrage bet")
            self.bet_history.add(token_id)
            return
        
        # Place arbitrage bets on BOTH outcomes
        from ..models.trade import MarketDirection
        
        # Buy YES
        max_price_yes = min(yes_price * 1.05, 0.95)
        quantity_yes = bet_amount / max_price_yes
        print(f"   📗 Placing YES bet: ${bet_amount:.2f} @ ${max_price_yes:.2f} (qty: {quantity_yes:.2f})")
        
        trade_yes = self.order_executor.place_buy_order(
            market_id=market_id,
            outcome=MarketDirection.YES,
            quantity=quantity_yes,
            max_price=max_price_yes
        )
        
        # Buy NO
        max_price_no = min(no_price * 1.05, 0.95)
        quantity_no = bet_amount / max_price_no
        print(f"   📕 Placing NO bet: ${bet_amount:.2f} @ ${max_price_no:.2f} (qty: {quantity_no:.2f})")
        
        trade_no = self.order_executor.place_buy_order(
            market_id=market_id,
            outcome=MarketDirection.NO,
            quantity=quantity_no,
            max_price=max_price_no
        )
        
        if trade_yes and trade_no:
            total_cost = bet_amount * 2
            total_qty = quantity_yes + quantity_no
            print(f"   ✅ Arbitrage bets placed! Total cost: ${total_cost:.2f}")
            print(f"   📈 Guaranteed payout: $1.00 per share = ${total_qty:.2f}")
            print(f"   💵 Expected profit: ${total_qty - total_cost:.2f}")
        else:
            print(f"   ❌ Failed to place one or both arbitrage bets")
        
        self.bet_history.add(token_id)
    
    def _find_market_for_token(self, token_id: str) -> Optional[str]:
        """Find market_id for a given token_id"""
        # Check cache first
        current_time = time.time()
        if current_time - self._last_cache_update > self._cache_ttl:
            self._refresh_market_cache()
        
        # Check if we have it cached
        if token_id in self.token_to_market:
            return self.token_to_market[token_id]
        
        # Try to find it
        self._refresh_market_cache()
        return self.token_to_market.get(token_id)
    
    def _refresh_market_cache(self):
        """Refresh the token to market mapping cache"""
        if not self.market_data:
            return

        try:
            markets = self.market_data.get_short_term_crypto_markets(limit=150)
            import json
            
            for market in markets:
                market_id = market.get('id')
                clob_token_ids_raw = market.get('clobTokenIds', '[]')
                try:
                    if isinstance(clob_token_ids_raw, str):
                        clob_token_ids = json.loads(clob_token_ids_raw)
                    else:
                        clob_token_ids = clob_token_ids_raw
                    
                    for i, token in enumerate(clob_token_ids):
                        if token not in self.token_to_market:
                            self.token_to_market[token] = market_id
                except:
                    pass
            
            self._last_cache_update = time.time()
        except Exception as e:
            print(f"Error refreshing market cache: {e}")
    
    def _handle_price_update(self, token_id: str, yes_price: float, no_price: float):
        """Handle real-time price update"""
        pass
    
    async def stop(self):
        """Stop the monitor"""
        self.is_running = False
        await self.ws_client.disconnect()
        print("🛑 Fast Market Monitor stopped")
