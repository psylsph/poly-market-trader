import time
import threading
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from ..models.trade import MarketDirection, Trade, TradeType
from ..api.market_data_provider import MarketDataProvider
from ..api.chainlink_data_provider import ChainlinkDataProvider
from ..api.llm_provider import LLMProvider, MarketContext
from ..services.order_executor import OrderExecutor
from ..services.enhanced_order_executor import EnhancedOrderExecutor
from ..models.portfolio import Portfolio
from ..api.websocket_client import PolymarketWebSocketClient
from decimal import Decimal
import logging
from ..config import settings

logger = logging.getLogger(__name__)


class MarketMonitor:
    """
    Monitors crypto markets and automatically places bets based on Chainlink analysis
    """
    
    def __init__(self, portfolio: Portfolio, market_data: MarketDataProvider,
                 chainlink_data: ChainlinkDataProvider, order_executor: OrderExecutor,
                 bet_tracker=None, use_llm: bool = settings.ENABLE_LLM,
                 enhanced_order_executor: Optional[EnhancedOrderExecutor] = None,
                 enable_websocket: bool = True):
        self.portfolio = portfolio
        self.market_data = market_data
        self.chainlink_data = chainlink_data
        self.order_executor = order_executor
        self.enhanced_order_executor = enhanced_order_executor or EnhancedOrderExecutor(portfolio, bet_tracker)
        self.bet_tracker = bet_tracker
        self.is_monitoring = False
        self.monitor_thread = None
        self.check_interval = 900  # 15 minutes in seconds (market scanning interval)
        self.active_bets = []  # Track active bets that need monitoring

        # WebSocket integration
        self.enable_websocket = enable_websocket
        self.websocket_client = None
        self.websocket_thread = None
        self.last_price_update = {}  # Track last update time per asset

        # Risk management state
        self.portfolio_start_balance = float(portfolio.current_balance)
        self.daily_start_balance = float(portfolio.current_balance)
        self.weekly_start_balance = float(portfolio.current_balance)
        self.portfolio_peak_balance = float(portfolio.current_balance)
        self.emergency_stop_triggered = False

        # Load active bets from storage if available
        if self.bet_tracker:
            try:
                self.active_bets = self.bet_tracker.get_active_bets()
                if self.active_bets:
                    print(f"📦 Loaded {len(self.active_bets)} active bets from storage")
            except Exception as e:
                print(f"⚠️ Failed to load active bets from storage: {e}")
                self.active_bets = []

        self.use_llm = use_llm
        self.llm_provider = LLMProvider() if self.use_llm else None # Initialize LLM Provider only if enabled

        if self.use_llm:
            print(f"🧠 Local LLM Integration Enabled (URL: {self.llm_provider.base_url})")
        else:
            print("🧠 Local LLM Integration Disabled")

        print("🚀 Enhanced Order Executor Integrated" if enhanced_order_executor else "📋 Using Standard Order Executor")

        if self.enable_websocket:
            print("🔗 WebSocket Integration Enabled for Real-Time Updates")
            self._init_websocket()
        else:
            print("⏰ Polling Mode Enabled (15-minute intervals)")

    def _init_websocket(self):
        """Initialize WebSocket client for real-time price updates"""
        try:
            # Create WebSocket client
            self.websocket_client = PolymarketWebSocketClient()

            # Set callbacks
            self.websocket_client.on_price_update = self._on_price_update
            self.websocket_client.on_arbitrage = self._on_arbitrage_opportunity

            print("🔌 WebSocket client initialized with callbacks")

        except Exception as e:
            print(f"⚠️ Failed to initialize WebSocket client: {e}")
            self.enable_websocket = False

    def _on_price_update(self, asset_id: str, yes_price: float, no_price: float):
        """Callback for real-time price updates from WebSocket"""
        try:
            # Throttle updates to avoid excessive processing (max 1 per asset per 5 seconds)
            current_time = time.time()
            if asset_id in self.last_price_update:
                if current_time - self.last_price_update[asset_id] < 5:
                    return

            self.last_price_update[asset_id] = current_time

            # Calculate mid prices
            yes_mid = yes_price
            no_mid = no_price

            print(f"📈 Real-time update: {asset_id[:20]}... YES:${yes_mid:.4f}, NO:${no_mid:.4f}")

            # Check if this triggers any analysis (for active positions or opportunities)
            self._check_price_alerts(asset_id, yes_mid, no_mid)

        except Exception as e:
            print(f"Error processing WebSocket price update: {e}")

    def _on_arbitrage_opportunity(self, arbitrage_info: Dict):
        """Callback for arbitrage opportunities detected by WebSocket"""
        try:
            token_id = arbitrage_info['token_id']
            profit_pct = arbitrage_info['profit']

            print(f"🎯 WebSocket Arbitrage: {token_id[:20]}... Profit: {profit_pct:.1f}%")

            # Find market_id for this token
            market_id = self._find_market_for_token(token_id)
            if not market_id:
                print(f"   ⚠️ Could not find market for token {token_id[:20]}...")
                return

            # Place arbitrage bet if profitable enough
            if profit_pct >= 1.0:  # At least 1% profit
                self._place_arbitrage_bet(market_id, arbitrage_info)

        except Exception as e:
            print(f"Error processing arbitrage opportunity: {e}")

    def _check_price_alerts(self, asset_id: str, yes_price: float, no_price: float):
        """Check if price update triggers any alerts or actions"""
        try:
            # Find markets that contain this asset_id
            # This is a simplified approach - in production you'd want a proper mapping
            markets_with_asset = self._find_markets_containing_asset(asset_id)

            for market in markets_with_asset:
                market_id = market.get('id')
                if not market_id:
                    continue

                # Check if we should analyze this market based on price movement
                should_analyze = self._should_analyze_market_on_price_change(market, yes_price, no_price)
                if should_analyze:
                    print(f"🔍 Real-time analysis triggered for market {market_id[:20]}...")
                    self._analyze_market_realtime(market, yes_price, no_price)

        except Exception as e:
            print(f"Error in price alerts check: {e}")

    def _find_markets_containing_asset(self, asset_id: str) -> List[Dict]:
        """Find markets that contain the given asset_id"""
        # This is a simplified implementation
        # In production, you'd maintain a proper asset_id -> market mapping
        try:
            # Get recent crypto markets and check which ones contain this asset
            crypto_markets = self.market_data.get_crypto_up_down_markets(limit=50)
            matching_markets = []

            for market in crypto_markets:
                clob_token_ids_raw = market.get('clobTokenIds', '[]')
                try:
                    if isinstance(clob_token_ids_raw, str):
                        clob_token_ids = json.loads(clob_token_ids_raw)
                    else:
                        clob_token_ids = clob_token_ids_raw

                    if asset_id in clob_token_ids:
                        matching_markets.append(market)
                except:
                    continue

            return matching_markets
        except Exception as e:
            print(f"Error finding markets for asset {asset_id}: {e}")
            return []

    def _should_analyze_market_on_price_change(self, market: Dict, yes_price: float, no_price: float) -> bool:
        """Determine if market should be analyzed based on price change"""
        # Simple logic: analyze if prices are reasonable and market is active
        if yes_price <= 0 or no_price <= 0:
            return False

        if yes_price >= 1.0 or no_price >= 1.0:  # Very unlikely prices
            return False

        # Check if market is still active (not ended)
        end_date_str = market.get('endDate')
        if end_date_str:
            try:
                if end_date_str.endswith('Z'):
                    end_date_str = end_date_str[:-1] + '+00:00'
                end_time = datetime.fromisoformat(end_date_str)
                now = datetime.now(timezone.utc)
                if end_time <= now:
                    return False  # Market has ended
            except:
                pass

        return True

    def _analyze_market_realtime(self, market: Dict, yes_price: float, no_price: float):
        """Perform real-time analysis on a market with current prices"""
        try:
            market_id = market.get('id')
            question = market.get('question', 'Unknown question')

            print(f"  Analyzing: {question[:60]}...")

            # Get technical indicators for the crypto
            crypto_symbol = self._extract_crypto_from_market(market)
            if not crypto_symbol:
                return

            # Get Chainlink data
            try:
                technicals = self.chainlink_data.get_technical_indicators(crypto_symbol, timeframe='15min')
            except Exception as e:
                print(f"    ⚠️ Failed to get technical data: {e}")
                return

            # Create market context for LLM analysis
            context = MarketContext(
                question=question,
                description=market.get('description', ''),
                yes_price=yes_price,
                no_price=no_price,
                volume=float(market.get('volume', 0)),
                tags=market.get('tags', []),
                technicals=technicals,
                balance=float(self.portfolio.current_balance)
            )

            # Get LLM decision
            if self.use_llm and self.llm_provider:
                decision = self.llm_provider.analyze_market(context)
                if decision:
                    action = decision.get('decision', 'SKIP')
                    confidence = decision.get('confidence', 0.0)
                    stake_factor = decision.get('stake_factor', 0.0)

                    print(f"    🤖 LLM Decision: {action} (confidence: {confidence:.2f}, stake: {stake_factor:.2f})")

                    # Place bet if conditions are met
                    if action in ['YES', 'NO'] and confidence >= 0.6 and stake_factor > 0:
                        self._place_realtime_bet(market_id, action, stake_factor, yes_price, no_price)

        except Exception as e:
            print(f"Error in real-time market analysis: {e}")

    def _extract_crypto_from_market(self, market: Dict) -> Optional[str]:
        """Extract crypto symbol from market data"""
        question = market.get('question', '').lower()
        slug = market.get('slug', '').lower()

        # Check for common crypto symbols
        cryptos = ['bitcoin', 'btc', 'ethereum', 'eth', 'xrp', 'ripple', 'sol', 'solana']
        for crypto in cryptos:
            if crypto in question or crypto in slug:
                # Map to Chainlink symbols
                mapping = {
                    'bitcoin': 'bitcoin',
                    'btc': 'bitcoin',
                    'ethereum': 'ethereum',
                    'eth': 'ethereum',
                    'xrp': 'xrp',
                    'ripple': 'xrp',
                    'sol': 'solana',
                    'solana': 'solana'
                }
                return mapping.get(crypto, crypto)

        return None

    def _place_realtime_bet(self, market_id: str, outcome: str, stake_factor: float, yes_price: float, no_price: float):
        """Place a real-time bet based on analysis"""
        try:
            # Determine market direction
            if outcome == 'YES':
                market_direction = MarketDirection.YES
                price = yes_price
            elif outcome == 'NO':
                market_direction = MarketDirection.NO
                price = no_price
            else:
                return

            # Calculate position size
            base_amount = min(500.0, float(self.portfolio.current_balance) * 0.05)  # Max 5% of balance
            bet_amount = base_amount * stake_factor

            if bet_amount < 10:  # Minimum bet
                print(f"    💸 Bet amount too small: ${bet_amount:.2f}")
                return

            # Calculate quantity
            quantity = bet_amount / price

            print(f"    📈 Placing real-time {outcome} bet: ${bet_amount:.2f} @ ${price:.4f} (qty: {quantity:.2f})")

            # Use enhanced order executor for better execution
            if self.enhanced_order_executor:
                trade_result = self.enhanced_order_executor.place_buy_order(
                    market_id=market_id,
                    outcome=market_direction,
                    quantity=quantity,
                    max_price=price * 1.05  # Allow 5% slippage
                )

                if trade_result:
                    print("    ✅ Real-time bet placed successfully!")
                else:
                    print("    ❌ Failed to place real-time bet")

        except Exception as e:
            print(f"Error placing real-time bet: {e}")

    def _find_market_for_token(self, token_id: str) -> Optional[str]:
        """Find market_id for a given token_id"""
        # This would need implementation to map tokens back to markets
        # For now, return None
        return None

    def _place_arbitrage_bet(self, market_id: str, arbitrage_info: Dict):
        """Place an arbitrage bet"""
        # Implementation for placing arbitrage bets
        pass

    def _start_websocket_async(self):
        """Start WebSocket connection in async context"""
        try:
            asyncio.run(self._websocket_main())
        except Exception as e:
            print(f"WebSocket thread error: {e}")

    async def _websocket_main(self):
        """Main WebSocket connection and monitoring loop"""
        while self.is_monitoring:
            try:
                # Connect to WebSocket
                connected = await self.websocket_client.connect()
                if not connected:
                    print("Failed to connect to WebSocket, retrying in 30s...")
                    await asyncio.sleep(30)
                    continue

                # Subscribe to crypto markets
                await self.websocket_client.subscribe_all_crypto_markets()

                # Start listening
                await self.websocket_client.listen()

            except Exception as e:
                print(f"WebSocket connection lost: {e}. Reconnecting in 10s...")
                await asyncio.sleep(10)

    
    def start_monitoring(self, check_interval_seconds: int = 900):
        """
        Start the monitoring loop in a separate thread
        :param check_interval_seconds: How often to check for new opportunities (default 15 min)
        """
        if self.is_monitoring:
            print("Monitoring is already running")
            return

        self.check_interval = check_interval_seconds
        self.is_monitoring = True

        # Start WebSocket if enabled
        if self.enable_websocket and self.websocket_client:
            # Start WebSocket in background thread
            self.websocket_thread = threading.Thread(target=self._start_websocket_async, daemon=True)
            self.websocket_thread.start()
            print("🔗 WebSocket real-time monitoring started")

        # Start monitoring thread
        # Changed from daemon=True to daemon=False to keep main process alive
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=False)
        self.monitor_thread.start()

        mode = "Real-Time + Periodic" if self.enable_websocket else f"Periodic ({check_interval_seconds}s)"
        print(f"Started market monitoring in {mode} mode.")
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.is_monitoring = False

        # Stop WebSocket client
        if self.websocket_client:
            asyncio.run(self.websocket_client.disconnect())
            print("🔌 WebSocket monitoring stopped")

        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)  # Wait up to 2 seconds for thread to finish
        print("Stopped market monitoring.")
    
    def _monitor_loop(self):
        """Internal monitoring loop that runs in a separate thread"""
        while self.is_monitoring:
            try:
                # Print cycle header with separator
                print()
                print("=" * 70)
                print(f"[{time.strftime('%H:%M:%S')}] 🔄 MONITORING CYCLE STARTED")
                print("=" * 70)
                print()

                # Show active bets summary
                self._show_active_bets_summary()
                print()

                # Check risk management limits
                if self._check_drawdown_limits():
                    print("⚠️ Risk limits triggered. Skipping trading activities this cycle.")
                    print()
                else:
                    # Check for new betting opportunities
                    self._check_for_opportunities()

                # Check and settle resolved bets
                self._check_and_settle_resolved_bets()

                # Manage active positions (exit if profitable or risk limits hit)
                self._manage_active_positions()
                self._check_for_opportunities()

                # Check and settle resolved bets
                self._check_and_settle_resolved_bets()

                # Manage active positions (exit if profitable or LLM advises)
                self._manage_active_positions()

                # Update portfolio with current market prices
                self._update_portfolio_values()

                # Print cycle summary
                print()
                print("-" * 70)
                print(f"[{time.strftime('%H:%M:%S')}] ⏳ CYCLE COMPLETE. Next check in {self.check_interval}s...")
                print("-" * 70)

                # Sleep for the specified interval
                sleep_start = time.time()
                while time.time() - sleep_start < self.check_interval and self.is_monitoring:
                    time.sleep(1)

            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(10)  # Wait 10 seconds before retrying

    def _show_active_bets_summary(self):
        """Show summary of currently active bets"""
        if not self.active_bets:
            print("📋 ACTIVE BETS: None")
        else:
            print(f"📋 ACTIVE BETS: {len(self.active_bets)}")
            print()
            for i, bet in enumerate(self.active_bets, 1):
                market_id = bet['market_id']
                # Determine outcome - handle both Enum and string types safely
                outcome_val = bet['outcome']
                if hasattr(outcome_val, 'value'):
                    outcome = outcome_val.value
                else:
                    outcome = str(outcome_val)
                    
                quantity = bet['quantity']
                entry_price = bet['entry_price']
                question = bet['question'][:40]

                # Calculate bet amount
                bet_amount = quantity * entry_price

                print(f"  {i}. [{outcome}] {question}")
                print(f"     Quantity: {quantity:.2f} @ ${entry_price:.2f} = ${bet_amount:.2f}")
                print()
    
    def _check_for_opportunities(self):
        """Check for new betting opportunities based on Chainlink analysis"""
        print("┌─────────────────────────────────────────────────────────────────────────┐")
        print("│ 🔍 SCANNING FOR NEW BETTING OPPORTUNITIES                │")
        print("└─────────────────────────────────────────────────────────────────────────┘")
        print()

        # Get crypto up/down markets (15min, 1h, 4h timeframes)
        crypto_markets = self.market_data.get_crypto_markets(use_15m_only=True)

        if not crypto_markets:
            print("❌ No crypto markets found to analyze")
            return

        print(f"📊 Found {len(crypto_markets)} 15M crypto markets")
        print("🎯 Analyzing all markets...")
        print()

        # Analyze all markets
        for i, market in enumerate(crypto_markets, 1):
            self._analyze_and_bet(market, i)

        print()
        print("┌─────────────────────────────────────────────────────────────────────────┐")
        print("│ 📊 SCAN COMPLETE                                         │")
        print("└─────────────────────────────────────────────────────────────────────────┘")
    
    def _analyze_and_bet(self, market: Dict, index: int = 0):
        """Analyze a single market and place a bet if conditions are favorable"""
        market_id = market.get('id')
        title = market.get('title', '')
        question = market.get('question', title)  # Use title as fallback

        # Check if there's already an active bet on this market
        if self.active_bets:
            for bet in self.active_bets:
                if bet.get('market_id') == market_id:
                    print(f"Skipping {title[:40]}... - already have active bet on this market")
                    return

        # Extract crypto name from slug (most reliable since API regex ensures proper format)
        slug = market.get('slug', '')
        crypto_name = self._extract_crypto_name_from_slug(slug)
        
        # Phase 9: LLM Extraction (Deep Analysis)
        llm_data = None
        market_prices = self._get_prices_safely(market)
        
        # Get Chainlink analysis for 15-minute timeframe
        if crypto_name:
            try:
                current_price = self.chainlink_data.get_current_price(crypto_name)
                if current_price:
                    # Get 15-minute trend and volatility
                    trend = self.chainlink_data.get_recent_trend_15min(crypto_name, lookback_minutes=60)
                    volatility = self.chainlink_data.get_volatility_15min(crypto_name, lookback_minutes=60)

                    # Get RSI for additional confirmation
                    indicators_15m = self.chainlink_data.get_technical_indicators(crypto_name, timeframe='15min')
                    indicators_1h = self.chainlink_data.get_technical_indicators(crypto_name, timeframe='1hour')

                    # Primary indicators from 15-minute timeframe
                    rsi = indicators_15m.get('rsi', 50.0)
                    macd_histogram = indicators_15m.get('macd_histogram', 0)
                    sma_alignment = indicators_15m.get('sma_alignment', 0)

                    # Advanced indicators from 15-minute timeframe
                    adx = indicators_15m.get('adx', 0.0)
                    bb_upper = indicators_15m.get('bb_upper', 0.0)
                    bb_lower = indicators_15m.get('bb_lower', 0.0)
                    bb_percent = indicators_15m.get('bb_percent_b', 0.5)
                    volume_trend = indicators_15m.get('volume_trend', 'neutral')

                    # Multi-timeframe confirmation from 1-hour data
                    rsi_1h = indicators_1h.get('rsi', 50.0) if indicators_1h else 50.0
                    adx_1h = indicators_1h.get('adx', 0.0) if indicators_1h else 0.0
                    bb_percent_1h = indicators_1h.get('bb_percent_b', 0.5) if indicators_1h else 0.5

                    # Prepare technicals for LLM
                    technicals = {
                        "current_price": current_price,
                        "trend": trend,
                        "volatility": volatility,
                        "rsi": rsi,
                        "macd": macd_histogram,
                        "sma_alignment": sma_alignment,
                        "adx": adx,
                        "bollinger": {
                            "upper": bb_upper,
                            "lower": bb_lower,
                            "percent_b": bb_percent
                        },
                        "volume_trend": volume_trend
                    }
                else:
                    technicals = None
            except Exception as e:
                print(f"Error fetching technicals for {crypto_name}: {e}")
                technicals = None
        else:
            technicals = None

        # Only use LLM if regex fails or for deeper verification on high-value targets
        # For now, let's use it to augment the crypto_name if regex failed
        if self.llm_provider:
             # Prepare context for LLM
             context = MarketContext(
                 question=question,
                 description=market.get('description', ''),
                 yes_price=market_prices.get('yes', 0.0),
                 no_price=market_prices.get('no', 0.0),
                 volume=float(market.get('volume', 0.0)),
                 tags=market.get('tags', []),
                 technicals=technicals,
                 balance=float(self.portfolio.current_balance)
             )
             
             # Call LLM
             llm_data = self.llm_provider.analyze_market(context)
             
             if llm_data:
                 # Override or set crypto_name if found
                 if llm_data.get('asset') and not crypto_name:
                     asset = llm_data.get('asset').lower()
                     crypto_mappings = {
                        'bitcoin': 'bitcoin', 'btc': 'bitcoin',
                        'ethereum': 'ethereum', 'eth': 'ethereum',
                        'solana': 'solana', 'sol': 'solana',
                        'ripple': 'ripple', 'xrp': 'ripple'
                     }
                     crypto_name = crypto_mappings.get(asset, '')
                     if crypto_name:
                         print(f"  🧠 LLM identified asset: {asset} -> {crypto_name}")
                 
                 # If LLM provides a decision, use it!
                 if llm_data.get('decision') in ['YES', 'NO', 'SKIP']:
                     print(f"  🧠 LLM Recommendation: {llm_data.get('decision')} (Conf: {llm_data.get('confidence', 0.0):.2f})")
                     print(f"  📝 Reasoning: {llm_data.get('reasoning', 'No reasoning provided')}")
        
        if not crypto_name:
            return  # Skip if not a crypto-related market
        
        print(f"Analyzing market: {question[:50]}... for {crypto_name}")
        
        try:
            # Re-fetch technicals if we just found the name via LLM and didn't have them before
            if not technicals:
                 # Get Chainlink analysis for 15-minute timeframe
                current_price = self.chainlink_data.get_current_price(crypto_name)
                if not current_price:
                    print(f"Could not get current price for {crypto_name}")
                    return
                
                # Get 15-minute trend and volatility
                trend = self.chainlink_data.get_recent_trend_15min(crypto_name, lookback_minutes=60)
                volatility = self.chainlink_data.get_volatility_15min(crypto_name, lookback_minutes=60)
                
                # Get RSI for additional confirmation
                indicators = self.chainlink_data.get_technical_indicators(crypto_name, timeframe='15min')
                rsi = indicators.get('rsi', 50.0)
                macd_histogram = indicators.get('macd_histogram', 0)
                sma_alignment = indicators.get('sma_alignment', 0)
            else:
                # Unpack cached values
                current_price = technicals['current_price']
                trend = technicals['trend']
                volatility = technicals['volatility']
                rsi = technicals['rsi']
                macd_histogram = technicals['macd']
                sma_alignment = technicals['sma_alignment']
                
                # Retrieve indicators dict for later use (ADX etc)
                # In the cached path, we don't have the full indicators dict handy unless we rebuild it or store it
                # For safety, let's create a partial one from technicals
                indicators = {
                    'rsi': rsi,
                    'macd_histogram': macd_histogram,
                    'sma_alignment': sma_alignment,
                    'adx': technicals.get('adx', 0.0)
                }
            
            print(f"  Current price: ${current_price:.2f}, Trend: {trend}, Volatility: {volatility:.2f}%, RSI: {rsi:.2f}")
            
            # Initialize default values
            outcome = None
            confidence = 0.0
            stake_multiplier = 1.0

            # USE LLM DECISION IF AVAILABLE
            if llm_data and llm_data.get('decision') in ['YES', 'NO']:
                decision = llm_data.get('decision')
                outcome = MarketDirection.YES if decision == 'YES' else MarketDirection.NO
                confidence = float(llm_data.get('confidence', 0.5))
                stake_multiplier = float(llm_data.get('stake_factor', 1.0))
                print(f"  🤖 Using LLM Decision: {decision} with {confidence:.2f} confidence (Stake x{stake_multiplier:.1f})")
            
            # HANDLE LLM ARBITRAGE DETECTION
            elif llm_data and llm_data.get('decision') == 'BOTH':
                print(f"  🤖 LLM detected ARBITRAGE opportunity! Proceeding to verification...")
                outcome = None # Will fall through to arbitrage check
            
            # FALLBACK TO ALGORITHMIC LOGIC IF LLM SKIPPED OR NOT USED
            elif not llm_data or llm_data.get('decision') == 'SKIP':
                if llm_data:
                    print(f"  🤖 LLM decided to SKIP: {llm_data.get('reasoning')}")
                
                # Determine bet direction based on trend and volatility
                # STRATEGY UPDATE: Mean Reversion (Reverse Logic)
                # Bullish -> Expect pullback -> Bet NO
                # Bearish -> Expect bounce -> Bet YES
                
                # ENHANCED: Multi-Factor Entry Filter (ADX + Bollinger + RSI)
                # Only trade when ALL conditions are met for higher win rate
                adx = indicators.get('adx', 0.0)
                bb_percent = indicators.get('bb_percent_b', 0.5)
                rsi = indicators.get('rsi', 50.0)

                # Primary filter: Weak trend (ADX < 25) for mean reversion safety
                is_strong_trend = adx > 25.0

                # Secondary filter: Price must be at extreme Bollinger Band position
                # bb_percent < 0.1 means price is near lower band (oversold)
                # bb_percent > 0.9 means price is near upper band (overbought)
                is_extreme_bb = bb_percent < 0.15 or bb_percent > 0.85

                # Tertiary filter: RSI must confirm extreme condition
                is_extreme_rsi = rsi < 35 or rsi > 65

                print(f"  📊 Indicators: ADX={adx:.2f}, BB%={bb_percent:.2f}, RSI={rsi:.2f}")

                if is_strong_trend:
                    print(f"  💪 Strong Trend Detected (ADX: {adx:.2f}). Skipping Mean Reversion Strategy.")
                    return
                elif not is_extreme_bb:
                    print(f"  📈 Price not at Bollinger Band extreme (BB%: {bb_percent:.2f}). Waiting for better entry.")
                    return
                elif not is_extreme_rsi:
                    print(f"  📊 RSI not extreme (RSI: {rsi:.2f}). Waiting for confirmation.")
                    return
                else:
                    print(f"  ✅ All filters passed! Enhanced Mean Reversion Strategy activated.")
                    # ENHANCED MEAN REVERSION with Bollinger + RSI confirmation
                    # Lower BB + Low RSI = Strong oversold signal -> Bet YES (expect bounce)
                    # Upper BB + High RSI = Strong overbought signal -> Bet NO (expect pullback)

                    if bb_percent < 0.15 and rsi < 35:
                        # Strong oversold signal
                        outcome = MarketDirection.YES
                        confidence = 0.65  # Higher confidence due to multiple confirmations
                        print(f"  🎯 STRONG OVERSOLD: BB%={bb_percent:.2f}, RSI={rsi:.2f} → Bet YES")
                    elif bb_percent > 0.85 and rsi > 65:
                        # Strong overbought signal
                        outcome = MarketDirection.NO
                        confidence = 0.65  # Higher confidence due to multiple confirmations
                        print(f"  🎯 STRONG OVERBOUGHT: BB%={bb_percent:.2f}, RSI={rsi:.2f} → Bet NO")
                    else:
                        # Fallback to original trend-based logic but with lower confidence
                        print(f"  ⚠️ Mixed signals, using trend fallback with lower confidence")
                        if trend == 'bullish':
                            outcome = MarketDirection.NO
                            confidence = 0.50
                        elif trend == 'bearish':
                            outcome = MarketDirection.YES
                            confidence = 0.50
                        else:
                            recent = self.chainlink_data.get_recent_trend_15min(crypto_name, lookback_minutes=30)
                            if recent == 'bullish':
                                outcome = MarketDirection.NO
                                confidence = 0.45
                            elif recent == 'bearish':
                                outcome = MarketDirection.YES
                                confidence = 0.45
                            else:
                                return
                
                # RSI Confirmation: Additional boost for extreme readings (already filtered above)
                # Since RSI is already part of entry criteria, this provides marginal confirmation
                if rsi > 75 and outcome == MarketDirection.NO:
                    confidence += 0.05
                    print(f"  RSI ({rsi:.2f}) strongly confirms NO (severely overbought)")
                elif rsi < 25 and outcome == MarketDirection.YES:
                    confidence += 0.05
                    print(f"  RSI ({rsi:.2f}) strongly confirms YES (severely oversold)")
                
                # MACD Adjustment
                if macd_histogram > 0 and outcome == MarketDirection.YES:
                    confidence += 0.05
                    print(f"  MACD ({macd_histogram:.4f}) bullish, boosting YES confidence to {confidence:.2f}")
                elif macd_histogram < 0 and outcome == MarketDirection.NO:
                    confidence += 0.05
                    print(f"  MACD ({macd_histogram:.4f}) bearish, boosting NO confidence to {confidence:.2f}")
                
                if sma_alignment > 0 and outcome == MarketDirection.YES:
                    confidence += 0.05
                    print(f"  SMA alignment bullish, boosting YES confidence to {confidence:.2f}")
                elif sma_alignment < 0 and outcome == MarketDirection.NO:
                    confidence += 0.05
                    print(f"  SMA alignment bearish, boosting NO confidence to {confidence:.2f}")
                
            # Cap confidence at 0.95
            confidence = min(0.95, confidence)
            
            # Get current market price (using the helper method)
            yes_price = market_prices.get('yes', 0.0)
            no_price = market_prices.get('no', 0.0)
            
            print(f"  Market prices: YES=${yes_price:.2f} | NO=${no_price:.2f}")
            
            # ARBITRAGE CHECK: If YES + NO <= 0.99, bet on BOTH outcomes for guaranteed profit
            price_sum = yes_price + no_price
            arbitrage_threshold = 0.99
            
            if price_sum < arbitrage_threshold and yes_price > 0.01 and no_price > 0.01:
                arbitrage_profit = (1.0 - price_sum) * 100  # Expected profit %
                print(f"  🎯 ARBITRAGE OPPORTUNITY! Sum={price_sum:.2f} < {arbitrage_threshold}")
                print(f"  💰 Guaranteed profit: {arbitrage_profit:.1f}%")
                
                # Place bets on BOTH outcomes
                bet_amount = min(500.0, float(self.portfolio.current_balance) * 0.1)  # 10% for arbitrage
                
                # Buy YES
                max_price_yes = min(yes_price * 1.05, 0.95)
                quantity_yes = bet_amount / max_price_yes
                print(f"  Placing YES bet: ${bet_amount:.2f} @ ${max_price_yes:.2f} (qty: {quantity_yes:.2f})")
                
                trade_yes = self.order_executor.place_buy_order(
                    market_id=market_id,
                    outcome=MarketDirection.YES,
                    quantity=quantity_yes,
                    max_price=max_price_yes
                )
                
                # Buy NO
                max_price_no = min(no_price * 1.05, 0.95)
                quantity_no = bet_amount / max_price_no
                print(f"  Placing NO bet: ${bet_amount:.2f} @ ${max_price_no:.2f} (qty: {quantity_no:.2f})")
                
                trade_no = self.order_executor.place_buy_order(
                    market_id=market_id,
                    outcome=MarketDirection.NO,
                    quantity=quantity_no,
                    max_price=max_price_no
                )
                
                if trade_yes and trade_no:
                    print(f"  ✅ Arbitrage bets placed! Total cost: ${bet_amount * 2:.2f}")
                    print(f"  📈 Guaranteed payout: $1.00 per share = ${quantity_yes + quantity_no:.2f}")
                    print(f"  💵 Expected profit: ${(quantity_yes + quantity_no) - (bet_amount * 2):.2f}")
                    
                    # Track YES bet
                    # Get market end time and start time for settlement
                    market_end_date = market.get('endDate', '')
                    market_start_date = ''
                    
                    # Calculate start time (before market end time for price comparison)
                    if market_end_date:
                        try:
                            end_time = datetime.fromisoformat(market_end_date.replace('Z', '+00:00'))
                            start_time = end_time - timedelta(minutes=15)
                            market_start_date = start_time.isoformat()
                        except:
                            market_start_date = None

                    # Add YES bet to active bets (Arbitrage - very conservative stop-loss)
                    bet_info_yes = {
                        'market_id': market_id,
                        'market_slug': market.get('slug', ''),
                        'question': question,
                        'crypto_name': crypto_name,
                        'outcome': MarketDirection.YES.value,
                        'quantity': quantity_yes,
                        'entry_price': max_price_yes,
                        'cost': quantity_yes * max_price_yes,
                        'stop_loss_price': max_price_yes * 0.90,  # 10% stop for arbitrage (very conservative)
                        'placed_at': datetime.now(timezone.utc).isoformat(),
                        'market_start_time': market_start_date,
                        'market_end_time': market_end_date,
                        'entry_crypto_price': current_price if current_price else None
                    }
                    self.bet_tracker.add_active_bet(bet_info_yes)
                    
                    # Add NO bet to active bets (Arbitrage - very conservative stop-loss)
                    bet_info_no = {
                        'market_id': market_id,
                        'market_slug': market.get('slug', ''),
                        'question': question,
                        'crypto_name': crypto_name,
                        'outcome': MarketDirection.NO.value,
                        'quantity': quantity_no,
                        'entry_price': max_price_no,
                        'cost': quantity_no * max_price_no,
                        'stop_loss_price': max_price_no * 0.90,  # 10% stop for arbitrage (very conservative)
                        'placed_at': datetime.now(timezone.utc).isoformat(),
                        'market_start_time': market_start_date,
                        'market_end_time': market_end_date,
                        'entry_crypto_price': current_price if current_price else None
                    }
                    self.bet_tracker.add_active_bet(bet_info_no)

                    # Sync active bets list to reflect new arbitrage bets
                    self._sync_active_bets()

                else:
                    print(f"  ❌ Failed to place arbitrage bets")
                
                return  # Exit after placing arbitrage bets
            
            # Determine the price we would pay for our chosen outcome
            if outcome == MarketDirection.YES:
                market_price = yes_price
            elif outcome == MarketDirection.NO:
                market_price = no_price
            else:
                 # Should only happen if outcome is None (e.g. from BOTH or fallback failure)
                 # If we reached here without returning, it means we didn't place arbitrage bets either.
                 return 
            
            print(f"  Market price for {outcome.value}: ${market_price:.2f}")
            
            # Log analysis results even if prices aren't available yet
            print(f"  Analysis: Trend={trend}, RSI={rsi:.2f}, MACD={macd_histogram:.4f}")
            print(f"  Confidence: {confidence:.2f} | Outcome: {outcome.value}")
            
            # Skip bet placement if market price is $0.00 (market too new, no trading yet)
            if market_price <= 0.01:
                print(f"  ⏳ Waiting for trading activity... Will retry in next cycle")
                return
            
            # Value Betting Check: Confidence must be higher than market price + margin
            # Margin: 0.05 (5%) to account for spread and prediction error
            margin = 0.05
            min_confidence_threshold = 0.55
            
            # Effective threshold price: If market price is $0.80, we need > $0.85 confidence to bet
            if confidence < (market_price + margin):
                print(f"  Skipping: Confidence ({confidence:.2f}) <= Price + Margin ({market_price:.2f} + {margin:.2f})")
                return
            
            if confidence < min_confidence_threshold:
                print(f"  Skipping: Confidence ({confidence:.2f}) below minimum threshold ({min_confidence_threshold:.2f})")
                return
            
            # ENHANCED: Volatility-adjusted position sizing
            # Base bet: 5% of balance, adjusted by volatility and confidence
            base_bet_percent = 0.05

            # Volatility adjustment: Lower volatility = larger position, higher volatility = smaller position
            # Scale volatility factor between 0.5 (high vol) and 1.5 (low vol)
            vol_factor = max(0.5, min(1.5, 1.0 - (volatility - 0.5) * 2.0))  # Normalize around 0.5% vol

            # Confidence adjustment: Higher confidence = larger position
            confidence_factor = min(1.5, confidence / 0.6)  # Scale up to 1.5x for >60% confidence

            # Combined adjustment with stake multiplier from LLM
            adjusted_bet_percent = base_bet_percent * vol_factor * confidence_factor * stake_multiplier

            # Cap at reasonable maximum (15% of balance) and minimum ($10)
            max_bet_percent = 0.15
            adjusted_bet_percent = min(max_bet_percent, adjusted_bet_percent)

            bet_amount = min(500.0 * stake_multiplier, float(self.portfolio.current_balance) * adjusted_bet_percent)

            # Check position limits before sizing
            current_exposure = sum(bet.get('cost', 0.0) for bet in self.active_bets)
            max_portfolio_exposure = float(self.portfolio.current_balance) * 0.50  # Max 50% exposure

            if current_exposure >= max_portfolio_exposure:
                print(f"  Skipping: Portfolio exposure limit reached (${current_exposure:.2f} >= ${max_portfolio_exposure:.2f})")
                return

            # Check single crypto exposure
            crypto_exposure = sum(bet.get('cost', 0.0) for bet in self.active_bets
                                if bet.get('crypto_name') == crypto_name)
            max_crypto_exposure = float(self.portfolio.current_balance) * 0.20  # Max 20% per crypto

            if crypto_exposure >= max_crypto_exposure:
                print(f"  Skipping: {crypto_name} exposure limit reached (${crypto_exposure:.2f} >= ${max_crypto_exposure:.2f})")
                return

            # Check concurrent positions
            if len(self.active_bets) >= 5:
                print(f"  Skipping: Maximum concurrent positions reached ({len(self.active_bets)} >= 5)")
                return

            print(f"  💰 Enhanced Bet Sizing: {adjusted_bet_percent*100:.1f}% of balance")
            print(f"     Factors: Vol={vol_factor:.2f}, Conf={confidence_factor:.2f}, Stake={stake_multiplier:.1f}x")
            print(f"     Volatility: {volatility:.2f}%, Confidence: {confidence:.2f}")

            if bet_amount <= 10:
                print(f"  Skipping: Insufficient balance to bet (min $10 required)")
                return
            
            # Use market price + small buffer as max price (or just market price if we want to match exactly)
            # In Polymarket, you usually pay the current price or a bit more to get filled immediately
            max_price = min(market_price * 1.05, 0.95)  # Cap at 0.95 to avoid overpaying
            
            print(f"  Placing {confidence:.1f} confidence bet: {outcome.value} on {question[:30]}... (Price: ${market_price:.2f})")
            
            # Calculate quantity based on amount and max price
            quantity = bet_amount / max_price
            
            # Execute the trade
            trade = self.order_executor.place_buy_order(
                market_id=market_id,
                outcome=outcome,
                quantity=quantity,
                max_price=max_price
            )
            
            if trade:
                # Get market end time and start time for settlement
                market_end_date = market.get('endDate', '')
                market_start_date = ''
                
                # Calculate start time (before market end time for price comparison)
                if market_end_date:
                    try:
                        end_time = datetime.fromisoformat(market_end_date.replace('Z', '+00:00'))
                        start_time = end_time - timedelta(minutes=15)
                        market_start_date = start_time.isoformat()
                    except:
                        market_start_date = None
                
                # Calculate stop-loss levels
                # Fixed stop-loss: -5% from entry price
                fixed_stop_loss = max_price * 0.95  # 5% loss threshold

                # ATR-based stop-loss (if ATR data available)
                atr_stop_loss = None
                if indicators.get('atr'):
                    atr_value = indicators.get('atr', 0.0)
                    # Use 1.5x ATR for stop distance (common in trading)
                    atr_stop_distance = atr_value * 1.5
                    atr_stop_loss = max_price - atr_stop_distance
                    # Ensure ATR stop isn't too close (minimum 2% stop)
                    atr_stop_loss = min(atr_stop_loss, max_price * 0.98)

                # Use the more conservative (higher) stop-loss level
                stop_loss_price = max(fixed_stop_loss, atr_stop_loss) if atr_stop_loss else fixed_stop_loss

                # Add to active bets for monitoring using BetTracker
                bet_info = {
                    'market_id': market_id,
                    'market_slug': market.get('slug', ''),
                    'question': question,
                    'crypto_name': crypto_name,
                    'outcome': outcome.value,
                    'quantity': quantity,
                    'entry_price': max_price,
                    'cost': quantity * max_price,
                    'stop_loss_price': stop_loss_price,
                    'placed_at': datetime.now(timezone.utc).isoformat(),
                    'market_start_time': market_start_date,
                    'market_end_time': market_end_date,
                    'entry_crypto_price': current_price if current_price else None
                }
                
                self.bet_tracker.add_active_bet(bet_info)

                print(f"  Bet placed successfully! Quantity: {quantity:.2f} at ${max_price:.2f}")

                # Sync active bets list to reflect new bet
                self._sync_active_bets()
            else:
                print(f"  Failed to place bet on {question[:30]}...")
            
        except Exception as e:
            print(f"Error analyzing market {market_id}: {e}")

    def place_limit_order(self, market_id: str, outcome: MarketDirection,
                         quantity: float, limit_price: float, side: TradeType = TradeType.BUY,
                         expires_at: Optional[datetime] = None) -> Optional[str]:
        """
        Place a limit order using the enhanced order executor.

        Args:
            market_id: Market identifier
            outcome: YES or NO outcome
            quantity: Order quantity
            limit_price: Maximum price to pay (for buys) or minimum price to receive (for sells)
            side: Buy or sell
            expires_at: Optional expiration time

        Returns:
            Order ID if successful, None otherwise
        """
        if not self.enhanced_order_executor:
            print("Enhanced order executor not available")
            return None

        return self.enhanced_order_executor.place_limit_order(
            market_id=market_id,
            outcome=outcome,
            quantity=quantity,
            limit_price=limit_price,
            side=side,
            expires_at=expires_at
        )

    def place_trailing_stop(self, market_id: str, outcome: MarketDirection,
                           quantity: float, trailing_percent: float,
                           side: TradeType = TradeType.SELL) -> Optional[str]:
        """
        Place a trailing stop order using the enhanced order executor.

        Args:
            market_id: Market identifier
            outcome: YES or NO outcome
            quantity: Order quantity
            trailing_percent: Percentage to trail price movement
            side: Buy or sell (typically SELL for trailing stops)

        Returns:
            Order ID if successful, None otherwise
        """
        if not self.enhanced_order_executor:
            print("Enhanced order executor not available")
            return None

        return self.enhanced_order_executor.place_trailing_stop(
            market_id=market_id,
            outcome=outcome,
            quantity=quantity,
            trailing_percent=trailing_percent,
            side=side
        )

    def get_enhanced_orders_status(self) -> Dict[str, Any]:
        """
        Get status of all enhanced orders.

        Returns:
            Dictionary with active orders and their status
        """
        if not self.enhanced_order_executor:
            return {"enhanced_orders_enabled": False}

        active_orders = self.enhanced_order_executor.get_active_orders()
        return {
            "enhanced_orders_enabled": True,
            "active_orders_count": len(active_orders),
            "active_orders": active_orders
        }

    def cancel_enhanced_order(self, order_id: str) -> bool:
        """
        Cancel an enhanced order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled successfully, False otherwise
        """
        if not self.enhanced_order_executor:
            print("Enhanced order executor not available")
            return False

        return self.enhanced_order_executor.cancel_order(order_id)

    def _get_prices_safely(self, market: Dict) -> Dict[str, float]:
        """Helper to safely extract prices from market object or fetch fresh"""
        yes_price = 0.0
        no_price = 0.0
        
        try:
            raw_prices = market.get('outcomePrices') or market.get('outcome_prices')
            outcomes = market.get('outcomes')
            
            if raw_prices and outcomes:
                # Handle string formats
                if isinstance(raw_prices, str):
                    raw_prices = json.loads(raw_prices)
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
                    
                if len(outcomes) >= 2 and len(raw_prices) >= 2:
                    # Map indices (Up->Yes, Down->No)
                    yes_index = 0
                    no_index = 1
                    for i, outcome_name in enumerate(outcomes):
                        outcome_lower = str(outcome_name).lower()
                        if outcome_lower in ['yes', 'up', 'long']:
                            yes_index = i
                        elif outcome_lower in ['no', 'down', 'short']:
                            no_index = i
                    
                    if len(raw_prices) > max(yes_index, no_index):
                        yes_price = float(raw_prices[yes_index])
                        no_price = float(raw_prices[no_index])
        except Exception as e:
            print(f"  Error parsing prices from market object: {e}")
        
        # If prices still 0, try fetching fresh
        if yes_price == 0.0 and no_price == 0.0:
            try:
                market_prices = self.market_data.get_market_prices(market.get('id'))
                yes_price = market_prices.get('yes', 0.0)
                no_price = market_prices.get('no', 0.0)
            except Exception:
                pass
                
        return {'yes': yes_price, 'no': no_price}

    def _manage_active_positions(self):
        """Monitor active bets and decide if we should exit early (sell)"""
        if not self.active_bets:
            return

        print()
        print("┌─────────────────────────────────────────────────────────────────────────┐")
        print("│ 🛡️  MANAGING ACTIVE POSITIONS                                  │")
        print("└─────────────────────────────────────────────────────────────────────────┘")
        print()

        for bet in list(self.active_bets): # Copy list to modify safely
            try:
                market_id = bet.get('market_id')
                outcome = bet.get('outcome')
                entry_price = bet.get('entry_price', 0.0)
                quantity = bet.get('quantity', 0.0)
                question = bet.get('question', '')
                
                # Fetch current market price
                market_details = self.market_data.get_market_by_id(market_id)
                prices = self._get_prices_safely(market_details)
                
                current_price = 0.0
                if outcome == 'YES' or outcome == MarketDirection.YES.value:
                    current_price = prices.get('yes', 0.0)
                elif outcome == 'NO' or outcome == MarketDirection.NO.value:
                    current_price = prices.get('no', 0.0)
                
                if current_price <= 0.001:
                    print(f"  ⚠️  No price data for {question[:30]}... (skipping)")
                    continue
                
                # Calculate Unreailzed PnL
                value = quantity * current_price
                cost = bet.get('cost', 0.0)
                pnl = value - cost
                pnl_percent = (pnl / cost) * 100 if cost > 0 else 0.0
                
                print(f"  Checking: {question[:30]}...")
                print(f"    Entry: ${entry_price:.2f} | Current: ${current_price:.2f} | PnL: {pnl_percent:+.1f}%")
                
                should_sell = False
                reason = ""

                # Strategy 0: Stop Loss Protection (Highest Priority)
                stop_loss_price = bet.get('stop_loss_price', 0.0)
                if stop_loss_price > 0.0 and current_price <= stop_loss_price:
                    should_sell = True
                    loss_percent = ((current_price - entry_price) / entry_price) * 100
                    reason = f"Stop Loss Triggered ({loss_percent:.1f}%)"

                # Strategy 1: Take Profit (Multiple Levels)
                if not should_sell:
                    if pnl_percent >= 50.0:
                        should_sell = True
                        reason = f"Take Profit - Excellent (+{pnl_percent:.1f}%)"
                    elif pnl_percent >= 25.0:
                        should_sell = True
                        reason = f"Take Profit - Good (+{pnl_percent:.1f}%)"
                    elif pnl_percent >= 15.0 and outcome == 'YES':
                        # For YES bets, take profit at 15% (faster exit due to time decay)
                        should_sell = True
                        reason = f"Take Profit - Moderate (+{pnl_percent:.1f}%, YES position)"
                
                # Strategy 2: Stop Loss (Deep Loss)
                elif pnl_percent <= -50.0:
                    should_sell = True
                    reason = f"Stop Loss ({pnl_percent:.1f}%)"
                
                # Strategy 3: LLM Re-evaluation
                elif self.llm_provider:
                    # Construct context for re-eval
                    # We need the crypto name again
                    crypto_name = bet.get('crypto_name')
                    technicals = None
                    if crypto_name:
                         # Quick fetch of basic technicals
                         current_crypto_price = self.chainlink_data.get_current_price(crypto_name)
                         if current_crypto_price:
                             trend = self.chainlink_data.get_recent_trend_15min(crypto_name)
                             indicators = self.chainlink_data.get_technical_indicators(crypto_name, timeframe='15min')
                             technicals = {
                                 "current_price": current_crypto_price,
                                 "trend": trend,
                                 "rsi": indicators.get('rsi', 50.0)
                             }
                    
                    context = MarketContext(
                        question=f"[EXISTING POSITION: {outcome} @ ${entry_price:.2f}] {question}",
                        description=f"Current PnL: {pnl_percent:.1f}%. Should I HOLD or SELL?",
                        yes_price=prices.get('yes', 0.0),
                        no_price=prices.get('no', 0.0),
                        volume=0.0, # Not critical for exit
                        tags=['position_management'],
                        technicals=technicals,
                        balance=float(self.portfolio.current_balance)
                    )
                    
                    # Ask LLM
                    # We expect "decision": "SELL" or "HOLD" (mapped from YES/NO/SKIP)
                    # If LLM says "NO" (bearish on position), we SELL.
                    # If LLM says "YES" (bullish on position), we HOLD.
                    llm_resp = self.llm_provider.analyze_market(context)
                    
                    if llm_resp:
                        decision = llm_resp.get('decision')
                        # If we hold YES, and decision is NO -> SELL
                        # If we hold NO, and decision is YES -> SELL
                        # Or if decision is specifically "SELL" (if prompt allowed, but prompt allows YES/NO/SKIP)
                        
                        # Let's interpret:
                        # If decision contradicts our holding -> SELL
                        if outcome == 'YES' and decision == 'NO':
                            should_sell = True
                            reason = f"LLM flipped to NO (Conf: {llm_resp.get('confidence')})"
                        elif outcome == 'NO' and decision == 'YES':
                            should_sell = True
                            reason = f"LLM flipped to YES (Conf: {llm_resp.get('confidence')})"
                        
                        if should_sell:
                            print(f"    🤖 LLM advises EXIT: {llm_resp.get('reasoning')}")

                # Execute Sell
                if should_sell:
                    print(f"    🚨 SELLING POSITION: {reason}")
                    
                    # Convert outcome string to Enum
                    try:
                        outcome_enum = MarketDirection(outcome)
                    except ValueError:
                        outcome_enum = MarketDirection(outcome.upper())
                    
                    # Place Sell Order
                    trade = self.order_executor.place_sell_order(
                        market_id=market_id,
                        outcome=outcome_enum,
                        quantity=quantity,
                        min_price=current_price * 0.95 # Accept 5% slippage to exit fast
                    )
                    
                    if trade:
                        print(f"    ✅ Sold successfully at ${trade.price:.2f}")
                        # Remove from active bets tracking
                        self.active_bets.remove(bet)
                        
                        # Update BetTracker to mark as sold/closed
                        if self.bet_tracker:
                            # We need to manually update the file or add a method to BetTracker
                            # Since we don't have a method exposed yet, we'll just log it.
                            # Ideally, BetTracker should have a close_bet() method.
                            pass
                    else:
                        print("    ❌ Failed to sell position")

            except Exception as e:
                print(f"  Error managing position {bet.get('market_id')}: {e}")

    def _sync_active_bets(self):
        """Sync active bets from BetTracker storage to ensure we have latest data"""
        if self.bet_tracker:
            try:
                self.active_bets = self.bet_tracker.get_active_bets()
            except Exception as e:
                print(f"⚠️ Failed to sync active bets: {e}")

    def _check_drawdown_limits(self):
        """Check portfolio drawdown limits and trigger emergency stops if needed"""
        if self.emergency_stop_triggered:
            return True  # Already stopped

        current_balance = float(self.portfolio.current_balance)

        # Update peak balance
        if current_balance > self.portfolio_peak_balance:
            self.portfolio_peak_balance = current_balance

        # Calculate drawdowns
        portfolio_drawdown = (self.portfolio_peak_balance - current_balance) / self.portfolio_peak_balance * 100
        daily_drawdown = (self.daily_start_balance - current_balance) / self.daily_start_balance * 100
        weekly_drawdown = (self.weekly_start_balance - current_balance) / self.weekly_start_balance * 100

        # Emergency stop: 30% portfolio drawdown
        if portfolio_drawdown >= 30.0:
            print(f"🚨 EMERGENCY STOP: Portfolio down {portfolio_drawdown:.1f}% from peak")
            self.emergency_stop_triggered = True
            self._emergency_stop()
            return True

        # Daily limit: 10% drawdown
        if daily_drawdown >= 10.0:
            print(f"⚠️ Daily drawdown limit reached ({daily_drawdown:.1f}%). Pausing trading for today.")
            return True

        # Weekly limit: 20% drawdown
        if weekly_drawdown >= 20.0:
            print(f"⚠️ Weekly drawdown limit reached ({weekly_drawdown:.1f}%). Reducing position sizes.")
            return True

        return False  # Trading allowed

    def _emergency_stop(self):
        """Emergency stop - close all positions and halt trading"""
        print("🚨 EXECUTING EMERGENCY STOP PROTOCOL")
        print("🔒 Closing all active positions...")

        # Close all active positions at market
        for bet in list(self.active_bets):
            try:
                market_id = bet.get('market_id')
                outcome = bet.get('outcome')
                quantity = bet.get('quantity', 0.0)

                # Convert outcome string to Enum
                try:
                    outcome_enum = MarketDirection(outcome)
                except ValueError:
                    outcome_enum = MarketDirection(outcome.upper())

                # Place emergency sell order
                trade = self.order_executor.place_sell_order(
                    market_id=market_id,
                    outcome=outcome_enum,
                    quantity=quantity,
                    min_price=0.01  # Accept any price to exit quickly
                )

                if trade:
                    print(f"✅ Emergency closed position: {bet.get('question', '')[:30]}...")
                else:
                    print(f"❌ Failed to close position: {bet.get('question', '')[:30]}...")

            except Exception as e:
                print(f"❌ Error closing position: {e}")

        print("🔒 Emergency stop complete. Trading halted.")
        print("💡 To resume trading, restart the application and reset emergency flags.")

    def _check_and_settle_resolved_bets(self):
        """
        Check if any active bets have been resolved and settle them
        """
        # Sync with BetTracker first to ensure we have latest bets
        self._sync_active_bets()

        if not self.active_bets:
            return

        print()
        print("┌─────────────────────────────────────────────────────────────────────────┐")
        print("│ ⏰ CHECKING FOR EXPIRED BETS                          │")
        print("└─────────────────────────────────────────────────────────────────────────┘")
        print()

        current_time = datetime.now(timezone.utc)
        bets_to_remove = []

        for bet_info in self.active_bets:
            market_id = bet_info['market_id']
            market_question = bet_info.get('question', '')

            # Get end date from bet info
            end_date_str = bet_info.get('market_end_time') or bet_info.get('end_date') or bet_info.get('endDate')
            if not end_date_str:
                continue

            try:
                end_time = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))

                # Check if market has closed (give 5 minute buffer after end time)
                time_since_close = (current_time - end_time).total_seconds()
                if time_since_close > 300:  # 5 minutes after market closed
                    print("┌────────────────────────────────────────────────────────────────┐")
                    print("│ 💥 MARKET EXPIRED!                                   │")
                    print("└────────────────────────────────────────────────────────────────┘")
                    print()
                    print(f"  📋 Market: {market_question[:45]}")
                    print(f"  🆔 Market ID: {market_id[:12]}...")
                    print(f"  ⏱️  Time since close: {time_since_close:.0f} seconds ({time_since_close/60:.1f} minutes)")
                    print()

                    # Determine outcome based on price movement
                    result = self._settle_bet(bet_info, end_time)
                    if result and result.get('success'):
                        bets_to_remove.append(bet_info)
                else:
                    # Market still open
                    time_remaining = 300 - time_since_close
                    print(f"  ⏳  Market '{market_question[:30]}...' still open (closes in {time_remaining:.0f}s)")

            except Exception as e:
                print(f"  ❌ Error checking market {market_id[:8]}...: {e}")

        # Remove settled bets from active list
        if bets_to_remove:
            print()
            print("┌────────────────────────────────────────────────────────────────┐")
            print(f"│ 🗑️  REMOVING {len(bets_to_remove)} SETTLED BET(S)             │")
            print("└────────────────────────────────────────────────────────────────┘")

            for bet in bets_to_remove:
                if bet in self.active_bets:
                    self.active_bets.remove(bet)
                    # Also remove from persistent storage (active_bets.json)
                    if self.bet_tracker:
                        # Re-save the updated active_bets list
                        self.bet_tracker.active_bets = self.active_bets
                        self.bet_tracker._save_active_bets()

        if not bets_to_remove:
            print()
            print("✅ All active bets still open")
    def _settle_bet(self, bet_info: Dict, end_time: datetime):
        """
        Settle a bet based on actual market outcome
        :param bet_info: Information about the bet placed
        :param end_time: When the market closed
        """
        # Delegate settlement to BetTracker to ensure consistency
        if self.bet_tracker:
            return self.bet_tracker.settle_bet(
                bet_id=bet_info.get('bet_id'),
                chainlink_data=self.chainlink_data,
                portfolio=self.portfolio,
                order_executor=self.order_executor
            )
        else:
            print("  ❌ BetTracker not available, cannot settle bet")
            return {"success": False, "error": "BetTracker not available"}
    
    def _update_portfolio_values(self):
        """Update portfolio with current market prices"""
        # This would update the portfolio with current market prices
        # to reflect current P&L of open positions
        pass
    


    def _extract_crypto_name_from_slug(self, slug: str) -> str:
        """Extract crypto name from slug (e.g., 'btc-updown-15m-...' -> 'bitcoin')"""
        if not slug:
            return ""

        slug_lower = slug.lower()

        # Map slug prefixes to full crypto names
        crypto_map = {
            'btc': 'bitcoin',
            'eth': 'ethereum',
            'xrp': 'ripple',  # or 'xrp'
            'sol': 'solana'
        }

        for prefix, name in crypto_map.items():
            if slug_lower.startswith(f'{prefix}-'):
                return name

        return ""

    def _extract_crypto_name(self, title: str) -> str:
        """Extract cryptocurrency name from market title/question"""
        question_lower = title.lower()
        
        # Map common phrases to crypto names
        crypto_mappings = {
            'bitcoin': 'bitcoin',
            'btc': 'bitcoin',
            'ethereum': 'ethereum',
            'eth': 'ethereum',
            'solana': 'solana',
            'sol': 'solana',
            'ripple': 'ripple',
            'xrp': 'ripple'
        }
        
        for phrase, crypto_name in crypto_mappings.items():
            if phrase in question_lower:
                return crypto_name
        
        return ""
    
    def get_active_bets(self) -> List[Dict]:
        """Return list of active bets being monitored"""
        return self.active_bets
    
    def get_monitoring_status(self) -> Dict:
        """Get current monitoring status"""
        return {
            'is_monitoring': self.is_monitoring,
            'active_bets_count': len(self.active_bets),
            'check_interval': self.check_interval
        }
