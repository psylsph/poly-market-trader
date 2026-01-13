import time
import threading
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from ..models.trade import MarketDirection, Trade, TradeType
from ..api.market_data_provider import MarketDataProvider
from ..api.chainlink_data_provider import ChainlinkDataProvider
from ..services.order_executor import OrderExecutor
from ..models.portfolio import Portfolio
from decimal import Decimal


class MarketMonitor:
    """
    Monitors crypto markets and automatically places bets based on Chainlink analysis
    """
    
    def __init__(self, portfolio: Portfolio, market_data: MarketDataProvider, 
                 chainlink_data: ChainlinkDataProvider, order_executor: OrderExecutor):
        self.portfolio = portfolio
        self.market_data = market_data
        self.chainlink_data = chainlink_data
        self.order_executor = order_executor
        self.is_monitoring = False
        self.monitor_thread = None
        self.check_interval = 900  # 15 minutes in seconds
        self.active_bets = []  # Track active bets that need monitoring
    
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
        # Changed from daemon=True to daemon=False to keep main process alive
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=False)
        self.monitor_thread.start()
        print(f"Started market monitoring. Checking every {check_interval_seconds} seconds.")
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.is_monitoring = False
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

                # Check for new betting opportunities
                self._check_for_opportunities()

                # Check and settle resolved bets
                self._check_and_settle_resolved_bets()

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
                outcome = bet['outcome'].value
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
        print(f"[{time.strftime('%H:%M:%S')}] Checking for new betting opportunities...")

        # Get 15M crypto markets (expiring in ~15 minutes)
        crypto_markets = self.market_data.get_crypto_markets(use_15m_only=True)
        
        if not crypto_markets:
            print("No crypto markets found to analyze")
            return
        
        print(f"Found {len(crypto_markets)} crypto markets to analyze")

        # Analyze up to 5 markets (Binance API allows 1200 requests/minute)
        # This is much better than CoinGecko's free tier (~10 req/min)
        for market in crypto_markets[:5]:
            self._analyze_and_bet(market)
    
    def _analyze_and_bet(self, market: Dict):
        """Analyze a single market and place a bet if conditions are favorable"""
        market_id = market.get('id')
        question = market.get('question', '')
        
        # Extract crypto name from question
        crypto_name = self._extract_crypto_name(question)
        if not crypto_name:
            return  # Skip if not a crypto-related market
        
        print(f"Analyzing market: {question[:50]}... for {crypto_name}")
        
        try:
            # Get Chainlink analysis for 15-minute timeframe
            current_price = self.chainlink_data.get_current_price(crypto_name)
            if not current_price:
                print(f"Could not get current price for {crypto_name}")
                return
            
            # Get 15-minute trend
            trend = self.chainlink_data.get_recent_trend_15min(crypto_name, lookback_minutes=60)
            volatility = self.chainlink_data.get_volatility_15min(crypto_name, lookback_minutes=60)
            
            print(f"  Current price: ${current_price:.2f}, Trend: {trend}, Volatility: {volatility:.2f}%")
            
            # Determine bet direction based on trend and volatility
            if trend == 'bullish' and volatility > 1.0:  # High confidence bullish
                outcome = MarketDirection.YES
                confidence = 0.8
            elif trend == 'bearish' and volatility > 1.0:  # High confidence bearish
                outcome = MarketDirection.NO
                confidence = 0.8
            elif trend == 'bullish':
                outcome = MarketDirection.YES
                confidence = 0.6
            elif trend == 'bearish':
                outcome = MarketDirection.NO
                confidence = 0.6
            else:
                # Neutral trend, skip betting
                return
            
            # Only bet if we have sufficient confidence and balance
            min_confidence = 0.6
            bet_amount = min(500.0, float(self.portfolio.current_balance) * 0.05)  # Bet max 5% of balance
            
            if confidence >= min_confidence and bet_amount > 10:  # Minimum $10 bet
                # Get current market prices to determine max price we're willing to pay
                market_prices = self.market_data.get_market_prices(market_id)
                
                # For YES/NO markets, we want to buy the outcome we think will win
                # Use a reasonable price threshold based on market sentiment
                max_price = 0.7 if outcome == MarketDirection.YES else 0.7  # Conservative approach
                
                print(f"  Placing {confidence:.1f} confidence bet: {outcome.value} on {question[:30]}...")
                
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
                    # Get market end time for settlement
                    market_end_date = market.get('endDate', '')

                    # Add to active bets for monitoring
                    bet_info = {
                        'trade': trade,
                        'market_id': market_id,
                        'outcome': outcome,
                        'confidence': confidence,
                        'entry_price': max_price,
                        'quantity': quantity,
                        'timestamp': time.time(),
                        'end_date': market_end_date,
                        'question': question
                    }
                    self.active_bets.append(bet_info)
                    print(f"  Bet placed successfully! Quantity: {quantity:.2f} at ${max_price:.2f}")
                else:
                    print(f"  Failed to place bet on {question[:30]}...")
            
        except Exception as e:
            print(f"Error analyzing market {market_id}: {e}")

    def _check_and_settle_resolved_bets(self):
        """Check if any active bets have resolved and settle them"""
        current_time = datetime.now(timezone.utc)
        bets_to_remove = []

        for bet_info in self.active_bets:
            market_id = bet_info['market_id']
            market_question = bet_info.get('question', '')

            # Get end date from bet info
            end_date_str = bet_info.get('end_date', '')
            if not end_date_str:
                print(f"  Market {market_id[:8]}... has no end date, skipping")
                continue

            try:
                end_time = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))

                # Check if market has closed (give 5 minute buffer after end time)
                time_since_close = (current_time - end_time).total_seconds()
                if time_since_close > 300:  # 5 minutes after market closed
                    print(f"\n[{time.strftime('%H:%M:%S')}] Market {market_id[:8]}... has closed.")
                    print(f"  Time since close: {time_since_close:.0f} seconds")

                    # Determine outcome based on price movement
                    self._settle_bet(bet_info, end_time)
                    bets_to_remove.append(bet_info)

            except Exception as e:
                print(f"  Error checking market {market_id[:8]}...: {e}")

        # Remove settled bets from active list
        for bet in bets_to_remove:
            if bet in self.active_bets:
                self.active_bets.remove(bet)

    def _settle_bet(self, bet_info: Dict, end_time: datetime):
        """
        Settle a bet based on actual market outcome
        :param bet_info: Information about the bet placed
        :param end_time: When the market closed
        """
        market_id = bet_info['market_id']
        market_question = bet_info['question']
        bet_outcome = bet_info['outcome']
        bet_quantity = bet_info['quantity']
        bet_price = bet_info['entry_price']

        print(f"  Settling bet on: {market_question[:40]}...")

        # Extract crypto name from question
        crypto_name = self._extract_crypto_name(market_question)
        if not crypto_name:
            print(f"  Could not extract crypto name from question")
            return

        try:
            # Determine outcome based on price movement during market period
            start_time = end_time - timedelta(minutes=15)

            print(f"  Market period: {start_time.strftime('%H:%M:%S')} to {end_time.strftime('%H:%M:%S')}")

            # Get price at start of market period
            start_price = self.chainlink_data.get_price_at_time(crypto_name, start_time)

            # Get price at end of market period
            end_price = self.chainlink_data.get_price_at_time(crypto_name, end_time)

            if start_price is not None and end_price is not None:
                print(f"  Price at start: ${start_price:.2f}, Price at end: ${end_price:.2f}")

                # Determine actual outcome based on price movement
                if end_price > start_price:
                    actual_outcome = MarketDirection.YES
                    print(f"  Price went UP by {((end_price - start_price) / start_price * 100):.2f}%")
                elif end_price < start_price:
                    actual_outcome = MarketDirection.NO
                    print(f"  Price went DOWN by {((start_price - end_price) / start_price * 100):.2f}%")
                else:
                    # Price stayed the same
                    actual_outcome = MarketDirection.NO
                    print(f"  Price stayed the same (resolves to NO)")

                print(f"  Actual market outcome: {actual_outcome.value}")
                print(f"  Our bet: {bet_outcome.value}")

                # Calculate win/loss
                if bet_outcome == actual_outcome:
                    # We won!
                    payout = Decimal(str(bet_quantity)) * Decimal('1.00')  # $1.00 per share
                    print(f"  🎉 WE WON! Payout: ${payout:.2f}")

                    # Add payout to balance
                    self.portfolio.update_balance(payout)

                    # Remove position (we sold at $1.00)
                    self.portfolio.remove_position(market_id, bet_outcome.value)

                    # Create a sell trade to record the win
                    self.order_executor.execute_trade(
                        market_id=market_id,
                        outcome=bet_outcome,
                        quantity=bet_quantity,
                        price=1.0,
                        trade_type=TradeType.SELL
                    )
                else:
                    # We lost
                    loss_amount = Decimal(str(bet_quantity)) * Decimal(str(bet_price))
                    print(f"  😢 WE LOST! Bet amount: ${loss_amount:.2f}")

                    # Remove position (worth $0.00 now)
                    self.portfolio.remove_position(market_id, bet_outcome.value)

                    # Create a sell trade at $0.00 to record the loss
                    self.order_executor.execute_trade(
                        market_id=market_id,
                        outcome=bet_outcome,
                        quantity=bet_quantity,
                        price=0.0,
                        trade_type=TradeType.SELL
                    )
            else:
                print(f"  Could not get price data for {crypto_name}")
                print(f"  Cannot determine outcome, skipping settlement")
                # Remove position as we can't determine outcome
                self.portfolio.remove_position(market_id, bet_outcome.value)

        except Exception as e:
            print(f"  Error settling bet: {e}")
    
    def _update_portfolio_values(self):
        """Update portfolio with current market prices"""
        # This would update the portfolio with current market prices
        # to reflect current P&L of open positions
        pass
    
    def _extract_crypto_name(self, question: str) -> str:
        """Extract cryptocurrency name from market question"""
        question_lower = question.lower()
        
        # Map common phrases to crypto names
        crypto_mappings = {
            'bitcoin': 'bitcoin',
            'btc': 'bitcoin',
            'ethereum': 'ethereum',
            'eth': 'ethereum',
            'solana': 'solana',
            'sol': 'solana',
            'cardano': 'cardano',
            'ada': 'cardano',
            'ripple': 'ripple',
            'xrp': 'ripple',
            'dogecoin': 'dogecoin',
            'doge': 'dogecoin',
            'polkadot': 'polkadot',
            'dot': 'polkadot',
            'litecoin': 'litecoin',
            'ltc': 'litecoin',
            'bitcoin cash': 'bitcoin-cash',
            'bch': 'bitcoin-cash',
            'bnb': 'bnb',
            'binance coin': 'bnb',
            'chainlink': 'chainlink',
            'link': 'chainlink',
            'polygon': 'polygon',
            'matic': 'polygon',
            'defi': 'defi',
            'decentralized finance': 'defi',
            'coinbase': 'coinbase',
            'shiba': 'shiba-inu',
            'shib': 'shiba-inu'
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