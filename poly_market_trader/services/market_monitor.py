import time
import threading
import json
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from ..models.trade import MarketDirection, Trade, TradeType
from ..api.market_data_provider import MarketDataProvider
from ..api.chainlink_data_provider import ChainlinkDataProvider
from ..api.llm_provider import LLMProvider, MarketContext
from ..services.order_executor import OrderExecutor
from ..models.portfolio import Portfolio
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
                 bet_tracker=None, use_llm: bool = settings.ENABLE_LLM):
        self.portfolio = portfolio
        self.market_data = market_data
        self.chainlink_data = chainlink_data
        self.order_executor = order_executor
        self.bet_tracker = bet_tracker
        self.is_monitoring = False
        self.monitor_thread = None
        self.check_interval = 900  # 15 minutes in seconds
        self.active_bets = []  # Track active bets that need monitoring
        
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
        print("┌─────────────────────────────────────────────────────────────────────────┐")
        print("│ 🔍 SCANNING FOR NEW BETTING OPPORTUNITIES                │")
        print("└─────────────────────────────────────────────────────────────────────────┘")
        print()

        # Get 15M crypto markets (expiring in ~15 minutes)
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
        question = market.get('question', '')
        
        # Check if there's already an active bet on this market
        if self.active_bets:
            for bet in self.active_bets:
                if bet.get('market_id') == market_id:
                    print(f"Skipping {question[:40]}... - already have active bet on this market")
                    return
        
        # Extract crypto name from question using Regex (Fast Fallback)
        crypto_name = self._extract_crypto_name(question)
        
        if crypto_name:
            # Uncomment for verbose debugging if needed
            # print(f"  ⚡ Regex identified asset: {crypto_name}")
            pass
        
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
                    indicators = self.chainlink_data.get_technical_indicators(crypto_name, timeframe='15min')
                    rsi = indicators.get('rsi', 50.0)
                    macd_histogram = indicators.get('macd_histogram', 0)
                    sma_alignment = indicators.get('sma_alignment', 0)
                    
                    # Prepare technicals for LLM
                    technicals = {
                        "current_price": current_price,
                        "trend": trend,
                        "volatility": volatility,
                        "rsi": rsi,
                        "macd": macd_histogram,
                        "sma_alignment": sma_alignment
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
                
                if trend == 'bullish' and volatility > 0.1:
                    outcome = MarketDirection.NO
                    confidence = 0.7
                elif trend == 'bearish' and volatility > 0.1:
                    outcome = MarketDirection.YES
                    confidence = 0.7
                elif trend == 'bullish':
                    outcome = MarketDirection.NO
                    confidence = 0.55
                elif trend == 'bearish':
                    outcome = MarketDirection.YES
                    confidence = 0.55
                else:
                    recent = self.chainlink_data.get_recent_trend_15min(crypto_name, lookback_minutes=30)
                    if recent == 'bullish':
                        outcome = MarketDirection.NO
                        confidence = 0.5
                    elif recent == 'bearish':
                        outcome = MarketDirection.YES
                        confidence = 0.5
                    else:
                        return
                
                # RSI Adjustment: Boost confidence if RSI confirms mean reversion
                # RSI > 70: Overbought -> Price likely to drop -> Confirms Bullish -> Pullback -> Bet NO
                # RSI < 30: Oversold -> Price likely to rise -> Confirms Bearish -> Bounce -> Bet YES
                if rsi > 70 and outcome == MarketDirection.NO:
                    confidence += 0.1
                    print(f"  RSI ({rsi:.2f}) confirms NO (overbought), boosting confidence to {confidence:.2f}")
                elif rsi < 30 and outcome == MarketDirection.YES:
                    confidence += 0.1
                    print(f"  RSI ({rsi:.2f}) confirms YES (oversold), boosting confidence to {confidence:.2f}")
                elif 40 < rsi < 60:
                    # Neutral RSI, slight confidence boost for mean reversion
                    confidence += 0.05
                    print(f"  RSI ({rsi:.2f}) is neutral, slight confidence boost to {confidence:.2f}")
                
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
            
            # ARBITRAGE CHECK: If YES + NO < 0.99, bet on BOTH outcomes for guaranteed profit
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
                    
                    # Calculate start time (15 minutes before end time)
                    if market_end_date:
                        try:
                            end_time = datetime.fromisoformat(market_end_date.replace('Z', '+00:00'))
                            start_time = end_time - timedelta(minutes=15)
                            market_start_date = start_time.isoformat()
                        except:
                            market_start_date = None

                    # Add YES bet to active bets
                    bet_info_yes = {
                        'market_id': market_id,
                        'market_slug': market.get('slug', ''),
                        'question': question,
                        'crypto_name': crypto_name,
                        'outcome': MarketDirection.YES.value,
                        'quantity': quantity_yes,
                        'entry_price': max_price_yes,
                        'cost': quantity_yes * max_price_yes,
                        'placed_at': datetime.now(timezone.utc).isoformat(),
                        'market_start_time': market_start_date,
                        'market_end_time': market_end_date,
                        'entry_crypto_price': current_price if current_price else None
                    }
                    self.bet_tracker.add_active_bet(bet_info_yes)
                    
                    # Add NO bet to active bets
                    bet_info_no = {
                        'market_id': market_id,
                        'market_slug': market.get('slug', ''),
                        'question': question,
                        'crypto_name': crypto_name,
                        'outcome': MarketDirection.NO.value,
                        'quantity': quantity_no,
                        'entry_price': max_price_no,
                        'cost': quantity_no * max_price_no,
                        'placed_at': datetime.now(timezone.utc).isoformat(),
                        'market_start_time': market_start_date,
                        'market_end_time': market_end_date,
                        'entry_crypto_price': current_price if current_price else None
                    }
                    self.bet_tracker.add_active_bet(bet_info_no)
                    
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
            
            # Bet amount: Max 5% of balance, capped at $500
            # Apply Stake Multiplier from LLM
            base_bet_percent = 0.05
            adjusted_bet_percent = base_bet_percent * stake_multiplier
            
            bet_amount = min(500.0 * stake_multiplier, float(self.portfolio.current_balance) * adjusted_bet_percent)
            
            print(f"  💰 Bet Sizing: {adjusted_bet_percent*100:.1f}% of balance (Base: 5% * {stake_multiplier}x)")
            
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
                
                # Calculate start time (15 minutes before end time)
                if market_end_date:
                    try:
                        end_time = datetime.fromisoformat(market_end_date.replace('Z', '+00:00'))
                        start_time = end_time - timedelta(minutes=15)
                        market_start_date = start_time.isoformat()
                    except:
                        market_start_date = None
                
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
                    'placed_at': datetime.now(timezone.utc).isoformat(),
                    'market_start_time': market_start_date,
                    'market_end_time': market_end_date,
                    'entry_crypto_price': current_price if current_price else None
                }
                
                self.bet_tracker.add_active_bet(bet_info)
                
                print(f"  Bet placed successfully! Quantity: {quantity:.2f} at ${max_price:.2f}")
            else:
                print(f"  Failed to place bet on {question[:30]}...")
            
        except Exception as e:
            print(f"Error analyzing market {market_id}: {e}")

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
                
                # Strategy 1: Take Profit (High ROI)
                if pnl_percent >= 40.0:
                    should_sell = True
                    reason = f"Take Profit (+{pnl_percent:.1f}%)"
                
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

    def _check_and_settle_resolved_bets(self):
        """
        Check if any active bets have been resolved and settle them
        """
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
