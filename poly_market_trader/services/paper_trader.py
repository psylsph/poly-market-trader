from ..models.portfolio import Portfolio
from ..api.market_data_provider import MarketDataProvider
from ..api.chainlink_data_provider import ChainlinkDataProvider
from ..api.websocket_client import PolymarketWebSocketClient
from ..services.order_executor import OrderExecutor
from ..services.market_monitor import MarketMonitor
from ..models.trade import MarketDirection, TradeType
from ..config.settings import DEFAULT_INITIAL_BALANCE, CACHE_DURATION, CRYPTO_KEYWORDS
from ..storage.portfolio_storage import PortfolioStorage
from ..storage.bet_tracker import BetTracker
from ..ui.dashboard_simple import PortfolioDashboard, BetHistoryDashboard, MonitoringStatusDashboard
from ..ui.live_monitor import LiveMonitor
from ..analytics.combined_dashboard import CombinedDashboard
from ..analytics.offer_tracker import OfferTracker
from ..analytics.statistics_aggregator import StatisticsAggregator
from decimal import Decimal
from typing import Dict, List, Tuple, Optional, Callable
from datetime import datetime, timezone
import asyncio
import threading
import time


class PaperTrader:
    """Main class for paper trading on Polymarket with crypto focus"""

    def __init__(self, initial_balance: Decimal = None, auto_load: bool = True, use_llm: Optional[bool] = None):
        self.storage = PortfolioStorage()
        self.bet_tracker = BetTracker()
        self.portfolio_dashboard = PortfolioDashboard()
        self.bet_history_dashboard = BetHistoryDashboard()
        self.monitoring_dashboard = MonitoringStatusDashboard()
        self.offer_tracker = OfferTracker()
        self.statistics_aggregator = StatisticsAggregator()
        
        if auto_load:
            # Try to load existing portfolio first
            loaded_portfolio = self.storage.load_portfolio()
            if loaded_portfolio is not None:
                self.portfolio = loaded_portfolio
            else:
                # No saved portfolio, create new one
                if initial_balance is None:
                    initial_balance = Decimal(str(DEFAULT_INITIAL_BALANCE))
                self.portfolio = Portfolio(initial_balance=initial_balance)
                self.storage.save_portfolio(self.portfolio)
        else:
            # Skip auto-load, create new portfolio
            if initial_balance is None:
                initial_balance = Decimal(str(DEFAULT_INITIAL_BALANCE))
            self.portfolio = Portfolio(initial_balance=initial_balance)
        
        self.market_data = MarketDataProvider()
        self.chainlink_data = ChainlinkDataProvider()
        self.order_executor = OrderExecutor(self.portfolio, storage=self.storage)
        
        # Prepare MarketMonitor arguments
        monitor_kwargs = {
            'portfolio': self.portfolio,
            'market_data': self.market_data,
            'chainlink_data': self.chainlink_data,
            'order_executor': self.order_executor,
            'bet_tracker': self.bet_tracker
        }
        if use_llm is not None:
            monitor_kwargs['use_llm'] = use_llm

        self.market_monitor = MarketMonitor(**monitor_kwargs)
        self.crypto_markets_cache = []
        self.last_cache_update = 0
        self.cache_duration = CACHE_DURATION
        self.use_15m_only = True  # Default to 15M crypto markets
        
        # WebSocket client for real-time data
        self.ws_client = None
        self.ws_monitor = None
        self.ws_loop = None
        self.ws_thread = None
        self.is_ws_monitoring = False
    
    def reset_portfolio(self, initial_balance: Decimal = None) -> None:
        """
        Reset portfolio to fresh state (wipe all data)
        :param initial_balance: Starting balance for new portfolio (defaults to $10,000)
        """
        if initial_balance is None:
            initial_balance = Decimal(str(DEFAULT_INITIAL_BALANCE))
        
        self.portfolio = self.storage.reset_portfolio(initial_balance)
        self.bet_tracker = BetTracker()
        self.order_executor = OrderExecutor(self.portfolio, storage=self.storage)
        self.market_monitor = MarketMonitor(
            portfolio=self.portfolio,
            market_data=self.market_data,
            chainlink_data=self.chainlink_data,
            order_executor=self.order_executor,
            bet_tracker=self.bet_tracker
        )

    def refresh_crypto_markets(self, use_15m_only: bool = None):
        """
        Refresh the cache of crypto markets if needed
        :param use_15m_only: If True, fetch only 15M markets; if None, use instance default
        """
        current_time = time.time()
        if current_time - self.last_cache_update > self.cache_duration:
            print("Refreshing crypto markets...")
            # Use provided value or instance default
            fetch_15m = use_15m_only if use_15m_only is not None else self.use_15m_only
            markets = self.market_data.get_crypto_markets(use_15m_only=fetch_15m)
            
            # Fetch prices for each market
            for market in markets:
                market_id = market['id']
                prices = self.market_data.get_market_prices(market_id)
                market['yes_price'] = prices['yes']
                market['no_price'] = prices['no']
                market['has_prices'] = prices['yes'] > 0 or prices['no'] > 0
            
            self.crypto_markets_cache = markets
            self.last_cache_update = current_time
    
    def get_crypto_markets(self, use_15m_only: bool = True):
        """
        Get crypto-related markets
        :param use_15m_only: If True, only return 15M crypto markets (default: True)
        :return: List of crypto markets
        """
        self.refresh_crypto_markets()
        return self.crypto_markets_cache
    
    def get_market_prices(self, market_id: str):
        """Get current prices for a market"""
        return self.market_data.get_market_prices(market_id)
    
    def place_crypto_bet(self, market_title_keyword: str, outcome: MarketDirection,
                        amount: float, max_price: float = 1.0, use_chainlink_analysis: bool = True,
                        timeframe: str = '15min'):
        """
        Place a bet on a crypto-related market
        :param market_title_keyword: Keyword to identify the market (e.g., 'bitcoin', 'ethereum')
        :param outcome: The outcome to bet on (YES/NO)
        :param amount: Amount to risk on this bet (in USD)
        :param max_price: Maximum price to pay for the outcome token
        :param use_chainlink_analysis: Whether to use Chainlink data for decision making
        :param timeframe: Timeframe for analysis ('15min', '1h', 'daily')
        """
        # Find a market that matches the keyword
        crypto_markets = self.get_crypto_markets()

        target_market = None
        for market in crypto_markets:
            if market_title_keyword.lower() in market.get('question', '').lower():
                target_market = market
                break

        if not target_market:
            print(f"No crypto market found with keyword: {market_title_keyword}")
            return False

        market_id = target_market['id']
        print(f"Found market: {target_market['question'][:50]}... (ID: {market_id[:8]}...)")

        # Initialize crypto_name and current_price
        crypto_name = None
        current_price = None

        # If using Chainlink analysis, adjust decision based on market data
        if use_chainlink_analysis:
            # Extract crypto name from market question to get Chainlink data
            crypto_name = self._extract_crypto_name_from_question(target_market['question'])
            if crypto_name:
                print(f"Analyzing Chainlink data for {crypto_name} (timeframe: {timeframe})...")

                # Get analysis based on selected timeframe
                analysis = self.get_chainlink_analysis(crypto_name, timeframe=timeframe)

                # Get current price and trend
                current_price = analysis['current_price']
                if current_price:
                    print(f"Current {crypto_name.title()} price: ${current_price:.2f}")
                    print(f"Current {crypto_name.title()} price: ${current_price:.2f}")

                # Get trend analysis
                trend = analysis['trend']
                print(f"{crypto_name.title()} trend ({timeframe}): {trend}")

                # Get technical indicators
                indicators = analysis['indicators']
                if indicators:
                    if timeframe == '15min':
                        print(f"15-min Volatility: {indicators.get('volatility_15min', 0):.2f}%")
                    else:
                        print(f"SMA: ${indicators.get('sma', 0):.2f}, "
                              f"Volatility: {indicators.get('volatility', 0):.2f}, "
                              f"Current vs SMA: {indicators.get('price_sma_ratio', 0):.2f}")

                # Adjust decision based on Chainlink data
                if trend == 'bullish' and outcome == MarketDirection.YES:
                    print(f"Chainlink data supports a bullish outlook ({timeframe}), reinforcing YES bet")
                elif trend == 'bearish' and outcome == MarketDirection.NO:
                    print(f"Chainlink data supports a bearish outlook ({timeframe}), reinforcing NO bet")
                elif trend == 'bullish' and outcome == MarketDirection.NO:
                    print(f"WARNING: Chainlink data suggests bullish trend ({timeframe}) but betting NO")
                    # Optionally reduce bet size or skip bet based on this contradiction
                elif trend == 'bearish' and outcome == MarketDirection.YES:
                    print(f"WARNING: Chainlink data suggests bearish trend ({timeframe}) but betting YES")
                    # Optionally reduce bet size or skip bet based on this contradiction

        # Calculate quantity based on amount and price
        quantity = amount / max_price

        # Execute the trade
        trade = self.order_executor.place_buy_order(
            market_id=market_id,
            outcome=outcome,
            quantity=quantity,
            max_price=max_price
        )

        # Track the bet for settlement
        if trade:
            crypto_name = self._extract_crypto_name_from_question(target_market['question'])
            bet_info = {
                'market_id': market_id,
                'question': target_market['question'],
                'crypto_name': crypto_name,
                'outcome': outcome.value,
                'quantity': quantity,
                'entry_price': max_price,
                'cost': quantity * max_price,
                'market_start_time': target_market.get('startDate') or target_market.get('start_date'),
                'market_end_time': target_market.get('endDate') or target_market.get('end_date'),
                'entry_crypto_price': current_price if use_chainlink_analysis else None
            }
            self.bet_tracker.add_active_bet(bet_info)

        return trade is not None

    def _extract_crypto_name_from_question(self, question: str) -> str:
        """
        Extract cryptocurrency name from market question
        :param question: The market question
        :return: Extracted crypto name or empty string if none found
        """
        question_lower = question.lower()

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

    def place_informed_crypto_bet(self, market_title_keyword: str,
                                 amount: float,
                                 max_price: float = 1.0,
                                 confidence_threshold: float = 0.6,
                                 timeframe: str = '15min'):
        """
        Place a crypto bet based on Chainlink data analysis
        :param market_title_keyword: Keyword to identify the market
        :param amount: Amount to risk on this bet
        :param max_price: Maximum price to pay for the outcome token
        :param confidence_threshold: Minimum confidence level to place bet (0.0 to 1.0)
        :param timeframe: Timeframe for analysis ('15min', '1h', 'daily')
        """
        # Find a market that matches the keyword
        crypto_markets = self.get_crypto_markets()

        target_market = None
        for market in crypto_markets:
            if market_title_keyword.lower() in market.get('question', '').lower():
                target_market = market
                break

        if not target_market:
            print(f"No crypto market found with keyword: {market_title_keyword}")
            return False

        market_id = target_market['id']
        print(f"Found market: {target_market['question'][:50]}... (ID: {market_id[:8]}...)")

        # Extract crypto name from market question
        crypto_name = self._extract_crypto_name_from_question(target_market['question'])
        if not crypto_name:
            print(f"Could not identify crypto in market: {target_market['question']}")
            return False

        # Get Chainlink data analysis based on timeframe
        print(f"Analyzing Chainlink data for {crypto_name} (timeframe: {timeframe})...")

        analysis = self.get_chainlink_analysis(crypto_name, timeframe=timeframe)

        current_price = analysis['current_price']
        if current_price:
            print(f"Current {crypto_name.title()} price: ${current_price:.2f}")

        trend = analysis['trend']
        print(f"{crypto_name.title()} trend ({timeframe}): {trend}")

        indicators = analysis['indicators']
        if indicators:
            if timeframe == '15min':
                print(f"15-min Volatility: {indicators.get('volatility_15min', 0):.2f}%")
            else:
                print(f"SMA: ${indicators.get('sma', 0):.2f}, "
                      f"Volatility: {indicators.get('volatility', 0):.2f}, "
                      f"Current vs SMA: {indicators.get('price_sma_ratio', 0):.2f}")

        # Determine the outcome based on Chainlink analysis
        # STRATEGY: Mean Reversion (Consistent with MarketMonitor)
        # Bullish -> Expect pullback -> Bet NO
        # Bearish -> Expect bounce -> Bet YES
        
        volatility = 0.0
        if indicators:
            if timeframe == '15min':
                volatility = indicators.get('volatility_15min', 0.0)
            else:
                volatility = indicators.get('volatility', 0.0)
        
        if trend == 'bullish':
            outcome = MarketDirection.NO
            # High volatility increases confidence in reversal
            if volatility > 0.1:
                confidence = 0.7
            else:
                confidence = 0.55
        elif trend == 'bearish':
            outcome = MarketDirection.YES
            # High volatility increases confidence in reversal
            if volatility > 0.1:
                confidence = 0.7
            else:
                confidence = 0.55
        else:  # neutral
            outcome = MarketDirection.YES  # Default to YES if no strong signal
            confidence = 0.4  # Lower confidence for neutral trend

        # Only place bet if confidence is above threshold
        if confidence < confidence_threshold:
            print(f"Confidence ({confidence:.2f}) below threshold ({confidence_threshold}), skipping bet")
            return False

        print(f"Placing {outcome.value} bet with {confidence:.2f} confidence")

        # Calculate quantity based on amount and price
        quantity = amount / max_price

        # Execute the trade
        trade = self.order_executor.place_buy_order(
            market_id=market_id,
            outcome=outcome,
            quantity=quantity,
            max_price=max_price
        )

        return trade is not None
    
    def close_position(self, market_id: str, outcome: MarketDirection, 
                      quantity: float = None, min_price: float = 0.0):
        """
        Close a position by selling
        :param market_id: The market ID
        :param outcome: The outcome to sell (YES/NO)
        :param quantity: Quantity to sell (if None, sell entire position)
        :param min_price: Minimum acceptable price
        """
        position = self.portfolio.get_position(market_id, outcome.value)
        
        if not position:
            print(f"No position found for market {market_id} and outcome {outcome.value}")
            return False
        
        # Determine quantity to sell
        sell_quantity = quantity if quantity else position.quantity
        
        if sell_quantity > position.quantity:
            print(f"Cannot sell {sell_quantity}, only {position.quantity} available")
            return False
        
        # Execute the sell order
        trade = self.order_executor.place_sell_order(
            market_id=market_id,
            outcome=outcome,
            quantity=sell_quantity,
            min_price=min_price
        )
        
        return trade is not None
    
    def get_portfolio_summary(self):
        """Get a summary of the portfolio"""
        crypto_markets = self.get_crypto_markets()
        market_prices = {}
        
        # Get current prices for markets where we have positions
        for position in self.portfolio.positions:
            if position.market_id not in market_prices:
                market_prices[position.market_id] = self.get_market_prices(position.market_id)
        
        total_value = self.portfolio.get_total_value(market_prices)
        pnl = self.portfolio.get_pnl(market_prices)
        
        summary = {
            'current_balance': float(self.portfolio.current_balance),
            'total_value': float(total_value),
            'pnl': float(pnl),
            'positions_count': len(self.portfolio.positions),
            'trade_count': len(self.portfolio.trade_history)
        }
        
        return summary
    
    def print_portfolio_summary(self):
        """Print a formatted portfolio summary using rich"""
        summary = self.get_portfolio_summary()
        active_bets = self.bet_tracker.get_active_bets()
        
        self.portfolio_dashboard.display_portfolio(
            summary,
            [],
            len(active_bets)
        )
    
    def list_positions(self):
        """List all current positions using simple formatting"""
        if not self.portfolio.positions:
            print("\n📍 No active positions.\n")
            return
        
        print(f"\n📍 Active Positions ({len(self.portfolio.positions)}):")
        print("=" * 60)
        print(f"  {'Market ID':<12} {'Outcome':<8} {'Quantity':<12} {'Avg Price':<12}")
        print("-" * 60)
        
        for i, position in enumerate(self.portfolio.positions, 1):
            market_id = position.market_id[:12]
            outcome = position.outcome.value
            quantity = position.quantity
            avg_price = position.avg_price
            
            print(f"  {i}. {market_id:<12} {outcome:<8} {quantity:>12.2f} ${avg_price:<10.2f}")
        
        print("=" * 60 + "\n")
    
    def list_crypto_markets(self, limit: int = 10):
        """List available crypto markets"""
        crypto_markets = self.get_crypto_markets()

        print(f"\n=== Available Crypto Markets (showing first {limit}) ===")
        for i, market in enumerate(crypto_markets[:limit]):
            question = market['question'][:60] + ('...' if len(market['question']) > 60 else '')
            
            # Show price status
            has_prices = market.get('has_prices', False)
            yes_price = market.get('yes_price', 0)
            no_price = market.get('no_price', 0)
            
            if has_prices:
                price_str = f"YES: ${yes_price:.2f} | NO: ${no_price:.2f}"
            else:
                price_str = "⏳ Awaiting pricing..."
            
            print(f"{i+1}. {question}")
            print(f"    ID: {market['id'][:8]}... | {price_str}")
        print("=" * 50)

    def get_chainlink_analysis(self, crypto_name: str, timeframe: str = '15min') -> Dict:
        """
        Get comprehensive Chainlink analysis for a cryptocurrency
        :param crypto_name: Name of the cryptocurrency
        :param timeframe: Timeframe for analysis ('15min', '1h', 'daily')
        :return: Dictionary with analysis data
        """
        analysis = {}

        # Get current price
        current_price = self.chainlink_data.get_current_price(crypto_name)
        analysis['current_price'] = current_price

        # Get trend based on timeframe
        if timeframe == '15min':
            trend = self.chainlink_data.get_recent_trend_15min(crypto_name)
            analysis['trend'] = trend
        else:
            trend = self.chainlink_data.get_crypto_trend(crypto_name)
            analysis['trend'] = trend

        # Get technical indicators based on timeframe
        if timeframe == '15min':
            # For 15-minute analysis, get more relevant short-term indicators
            volatility = self.chainlink_data.get_volatility_15min(crypto_name)
            analysis['indicators'] = {
                'volatility_15min': volatility,
                'current_price': current_price,
                'trend_direction': trend
            }
        else:
            indicators = self.chainlink_data.get_technical_indicators(crypto_name)
            analysis['indicators'] = indicators

        # Get historical prices based on timeframe
        if timeframe == '15min':
            historical_prices = self.chainlink_data.get_historical_prices(crypto_name, hours=4, interval='15min')
            analysis['historical_prices'] = historical_prices
        else:
            historical_prices = self.chainlink_data.get_historical_prices(crypto_name, days=7)
            analysis['historical_prices'] = historical_prices

        return analysis

    def start_auto_betting(self, check_interval_seconds: int = 900, confidence_threshold: float = None):
        """
        Start the auto-betting loop that monitors markets and places bets based on Chainlink analysis
        :param check_interval_seconds: How often to check for new opportunities (default 15 min = 900 sec)
        :param confidence_threshold: Minimum confidence level
        """
        self.market_monitor.start_monitoring(check_interval_seconds, confidence_threshold)

    def stop_auto_betting(self):
        """Stop the auto-betting loop"""
        self.market_monitor.stop_monitoring()

    def get_auto_betting_status(self) -> Dict:
        """Get the status of the auto-betting system"""
        return self.market_monitor.get_monitoring_status()

    def get_active_bets(self) -> List[Dict]:
        """Get list of active bets being monitored by auto-betting system"""
        bets = self.bet_tracker.get_active_bets()
        
        # Backfill market_slug if missing (fix for legacy bets)
        for bet in bets:
            if not bet.get('market_slug'):
                market_id = bet.get('market_id')
                if not market_id:
                    continue
                    
                # Try to find in cache first
                for m in self.crypto_markets_cache:
                    if str(m.get('id')) == str(market_id):
                        bet['market_slug'] = m.get('slug', '')
                        break
        
        return bets
    
    def settle_bets(self) -> Dict:
        """
        Manually settle all ready bets
        :return: Dictionary with settlement results
        """
        print("\n🔍 Checking for ready bets to settle...")
        results = self.bet_tracker.settle_all_ready_bets(
            self.chainlink_data,
            self.portfolio,
            self.order_executor
        )
        
        # Save portfolio after settlements
        if results:
            self.storage.save_portfolio(self.portfolio)
        
        return {
            'count': len(results),
            'results': results
        }
    
    def start_live_monitoring(self, check_interval_seconds: int = 900) -> None:
        """
        Start live monitoring with real-time updates
        :param check_interval_seconds: How often to check for opportunities (default 15 min = 900 sec)
        """
        # Create live monitor
        from ..ui.live_monitor import LiveMonitor
        live_monitor = LiveMonitor(
            interval_seconds=check_interval_seconds
        )
        
        # Start monitoring
        live_monitor.start_monitoring(
            portfolio_summary_callback=self.get_portfolio_summary,
            active_bets_callback=self.bet_tracker.get_active_bets,
            activity_log_callback=lambda: self.market_monitor.active_bets
        )
    
    def get_bet_history(self, limit: int = None, status_filter: str = None, start_time: datetime = None) -> List[Dict]:
        """
        Get bet history with optional filtering
        :param limit: Maximum number of bets to return
        :param status_filter: Filter by status ('won', 'lost')
        :param start_time: Only return bets settled after this time
        :return: List of settled bets
        """
        return self.bet_tracker.get_bet_history(limit, status_filter, start_time)
    
    def get_pending_offers(self) -> List[Dict]:
        """
        Get pending offers from offer tracker
        :return: List of pending offers
        """
        return self.offer_tracker.get_pending_offers()
    
    def get_all_offers(self) -> List[Dict]:
        """
        Get all offers from offer tracker
        :return: List of all offers
        """
        return self.offer_tracker.get_all_offers()
    
    def update_offer_action(self, offer_id: str, action: str) -> None:
        """
        Update action for a specific offer
        :param offer_id: ID of offer to update
        :param action: 'accepted', 'skipped', 'expired'
        """
        self.offer_tracker.update_offer_action(offer_id, action)
    
    def accept_offer(self, offer_id: str) -> None:
        """
        Accept a specific offer
        :param offer_id: ID of offer to accept
        """
        self.offer_tracker.update_offer_action(offer_id, 'accepted')
        print(f"\n  ✅ Accepted offer: {offer_id}")
    
    def skip_offer(self, offer_id: str) -> None:
        """
        Skip a specific offer
        :param offer_id: ID of offer to skip
        """
        self.offer_tracker.update_offer_action(offer_id, 'skipped')
        print(f"\n  ⏭️  Skipped offer: {offer_id}")
    
    def skip_all_offers(self) -> None:
        """
        Skip all pending offers
        """
        for offer in self.offer_tracker.get_pending_offers():
            self.offer_tracker.update_offer_action(offer.get('offer_id'), 'skipped')
        print(f"\n  📭  Skipped all pending offers")
    
    def accept_all_qualifying_offers(self, min_confidence: float = 0.6) -> None:
        """
        Accept all offers meeting minimum confidence
        :param min_confidence: Minimum confidence threshold (default 0.6)
        """
        offers = self.offer_tracker.get_pending_offers()
        accepted = 0
        
        for offer in offers:
            if offer.get('confidence', 0.0) >= min_confidence:
                self.offer_tracker.update_offer_action(offer.get('offer_id'), 'accepted')
                accepted += 1
        
        if accepted > 0:
            print(f"\n  ✅ Accepted {accepted} qualifying offers")
        else:
            print(f"\n  ⏭️  No qualifying offers to accept")
    
    def start_dashboard(self, refresh_interval_seconds: int = 15) -> None:
        """
        Start the combined dashboard
        :param refresh_interval_seconds: Refresh interval (default 15 seconds)
        """
        dashboard = CombinedDashboard(
            portfolio_summary_callback=self.get_portfolio_summary,
            active_bets_callback=self.bet_tracker.get_active_bets,
            bet_history_callback=self.bet_tracker.get_bet_history,
            market_monitor_callback=lambda: []
        )
        
        dashboard.start_dashboard()
    
    def start_realtime_monitoring(self) -> bool:
        """
        Start real-time market monitoring via WebSocket for instant arbitrage detection
        :return: True if started successfully, False otherwise
        """
        if self.is_ws_monitoring:
            print("Real-time monitoring is already running")
            return False
        
        print("🚀 Starting real-time WebSocket monitoring...")
        
        def run_ws_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._ws_monitor_loop())
            except Exception as e:
                print(f"WebSocket loop error: {e}")
            finally:
                loop.close()
        
        self.ws_thread = threading.Thread(target=run_ws_loop, daemon=True)
        self.ws_thread.start()
        
        # Wait a moment for connection
        time.sleep(1)
        
        if self.ws_client and self.ws_client.is_connected:
            self.is_ws_monitoring = True
            print("✅ Real-time WebSocket monitoring active!")
            return True
        else:
            print("❌ Failed to connect to WebSocket")
            return False
    
    async def _ws_monitor_loop(self):
        """Internal WebSocket monitoring loop using FastMarketMonitor"""
        from ..api.websocket_client import FastMarketMonitor
        
        self.ws_monitor = FastMarketMonitor(
            portfolio=self.portfolio,
            order_executor=self.order_executor,
            market_data=self.market_data
        )
        
        success = await self.ws_monitor.start()
        
        if success:
            # Store reference to ws_client for price fetching
            self.ws_client = self.ws_monitor.ws_client
        else:
            self.ws_monitor = None
    
    def _handle_ws_arbitrage(self, arbitrage_info: dict):
        """Handle arbitrage detected via WebSocket"""
        token_id = arbitrage_info.get('token_id', '')[:20]
        yes_price = arbitrage_info.get('yes_price', 0)
        no_price = arbitrage_info.get('no_price', 0)
        profit = arbitrage_info.get('profit', 0)
        
        print(f"\n🎯 REALTIME ARBITRAGE: {token_id}...")
        print(f"   YES={yes_price:.4f}, NO={no_price:.4f}, Profit={profit:.1f}%")
        
        # Note: Actual order placement is handled by FastMarketMonitor
        # This is just for logging in PaperTrader
    
    def stop_realtime_monitoring(self):
        """Stop real-time WebSocket monitoring"""
        if not self.is_ws_monitoring:
            print("Real-time monitoring is not running")
            return
        
        print("🛑 Stopping real-time WebSocket monitoring...")
        
        if self.ws_monitor:
            asyncio.run(self.ws_monitor.stop())
            self.ws_monitor = None
        
        if self.ws_client:
            self.ws_client = None
        
        self.is_ws_monitoring = False
        print("✅ Real-time monitoring stopped")
    
    def get_realtime_prices(self) -> Dict[str, Dict]:
        """Get current prices from WebSocket connection"""
        if self.ws_client and self.ws_client.is_connected:
            return self.ws_client.get_all_prices()
        return {}
    
    def get_monitoring_status(self) -> Dict:
        """Get status of all monitoring systems"""
        return {
            'polling_active': self.market_monitor.is_monitoring if self.market_monitor else False,
            'websocket_active': self.is_ws_monitoring,
            'websocket_connected': self.ws_client.is_connected if self.ws_client else False,
            'active_bets': len(self.bet_tracker.get_active_bets()) if self.bet_tracker else 0
        }
    
    def print_monitoring_status(self) -> None:
        """Print monitoring system status using the dashboard"""
        status = self.get_monitoring_status()
        self.monitoring_dashboard.display_status(status)
    
    def print_portfolio_status(self) -> None:
        """Print complete portfolio and monitoring status"""
        portfolio_summary = self.get_portfolio_summary()
        active_bets = self.get_active_bets()
        
        self.portfolio_dashboard.display_portfolio(
            portfolio_summary=portfolio_summary,
            positions=[],
            active_bets_count=len(active_bets)
        )
        
        self.print_monitoring_status()
        
        if active_bets:
            self.portfolio_dashboard.display_active_bets(active_bets)
