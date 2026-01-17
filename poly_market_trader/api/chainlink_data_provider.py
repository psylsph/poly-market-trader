import requests
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import json
import os
import time
import pandas as pd
import numpy as np
from functools import lru_cache
from ..config.settings import DEFAULT_INITIAL_BALANCE


class ChainlinkDataProvider:
    """
    Provides cryptocurrency price data from Chainlink-compatible sources.
    This implementation uses multiple data sources to simulate Chainlink's
    decentralized oracle network approach.

    PRIMARY: Binance API (free, 1200 requests/minute)
    FALLBACK: CoinGecko API (requires API key, no free tier)

    PERFORMANCE FEATURES:
    - In-memory caching for technical indicators (5-minute TTL)
    - LRU cache for price data to reduce API calls
    """

    def __init__(self):
        # PERFORMANCE: Caching layer for improved speed
        # Cache for technical indicators (symbol -> {timestamp, data})
        self._tech_cache: Dict[str, Dict] = {}
        self._cache_ttl = 300  # 5 minutes TTL for technical indicators

        # LRU cache for price data to reduce API calls
        self._price_cache: Dict[str, Tuple[List, float]] = {}
        self._price_cache_ttl = 60  # 1 minute TTL for price data
        # Binance API - FREE tier, no API key required
        # https://binance-docs.github.io/apidocs/spot/en/#market-data-endpoints
        self.binance_api = "https://api.binance.com/api/v3"

        # CoinGecko API - Now requires paid tier only
        # Get API key from environment if available
        self.api_key = os.getenv('COINGECKO_API_KEY', '')

        if self.api_key:
            # Use Pro API endpoint with API key
            self.coingecko_api = "https://pro-api.coingecko.com/api/v3"
            self.use_coingecko = True
        else:
            # CoinGecko no longer has free tier - use Binance instead
            self.coingecko_api = "https://api.coingecko.com/api/v3"
            self.use_coingecko = False
            print("Using Binance API (free tier, 1200 requests/minute, no API key required)")

        # Cryptocurrency symbol mappings (Binance uses uppercase symbols)
        self.binance_symbols = {
            'bitcoin': 'BTC',
            'btc': 'BTC',
            'ethereum': 'ETH',
            'eth': 'ETH',
            'solana': 'SOL',
            'sol': 'SOL',
            'ripple': 'XRP',
            'xrp': 'XRP'
        }

        # Common cryptocurrency IDs for CoinGecko API (fallback)
        self.coingecko_ids = {
            'bitcoin': 'bitcoin',
            'ethereum': 'ethereum',
            'solana': 'solana',
            'ripple': 'ripple',
            'xrp': 'ripple',
            'solana': 'solana'
        }

        # Cache for reducing API calls (cache price for 30 seconds)
        self.price_cache = {}
        self.cache_duration = 30  # seconds

        # Rate limiting delays (in seconds)
        self.last_request_time = 0
        self.min_request_delay = 0.5  # Binance allows 1200 req/min (0.05s between requests)

    def _rate_limit_request(self):
        """Apply rate limiting to API requests"""
        time_since_last_request = time.time() - self.last_request_time
        if time_since_last_request < self.min_request_delay:
            sleep_time = self.min_request_delay - time_since_last_request
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _get_binance_current_price(self, crypto_name: str) -> Optional[float]:
        """Get current price from Binance API"""
        symbol = self.binance_symbols.get(crypto_name.lower())
        if not symbol:
            # Try to find closest match
            for key, value in self.binance_symbols.items():
                if crypto_name.lower() in key or crypto_name.lower() in value.lower():
                    symbol = value
                    break

        if not symbol:
            return None

        try:
            url = f"{self.binance_api}/ticker/price"
            params = {'symbol': f'{symbol}USDT'}  # Binance uses USDT pair

            response = self._get_with_retry(url, params)
            if response:
                data = response.json()
                price = float(data.get('price', 0))
                return price

            return None

        except Exception as e:
            print(f"  Error fetching price from Binance for {crypto_name}: {e}")
            return None

    def _get_with_retry(self, url: str, params: Dict = None, max_retries: int = 3) -> Optional[requests.Response]:
        """Make HTTP request with retry logic and rate limiting"""
        for attempt in range(max_retries):
            try:
                # Apply rate limiting
                self._rate_limit_request()

                # Add API key if available
                headers = {}
                if self.api_key and 'coingecko' in url.lower():
                    headers['x-cg-pro-api-key'] = self.api_key

                response = requests.get(url, params=params, headers=headers, timeout=10)

                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 10))
                    wait_time = min(retry_after, 30)  # Cap at 30 seconds
                    print(f"  Rate limited. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.Timeout:
                print(f"  Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff: 2s, 4s
            except requests.exceptions.RequestException as e:
                print(f"  Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        return None

    def _get_cached_price(self, cache_key: str) -> Optional[float]:
        """Get price from cache if available and not expired"""
        if cache_key in self.price_cache:
            cached_data = self.price_cache[cache_key]
            timestamp, price = cached_data
            if time.time() - timestamp < self.cache_duration:
                return price
        return None

    def _cache_price(self, cache_key: str, price: float):
        """Cache price with current timestamp"""
        self.price_cache[cache_key] = (time.time(), price)

    def get_current_price(self, crypto_name: str) -> Optional[float]:
        """
        Get current price for a cryptocurrency
        :param crypto_name: Name of the cryptocurrency (e.g., 'bitcoin', 'ethereum')
        :return: Current price in USD or None if not found
        """
        # Check cache first
        cache_key = f"current_{crypto_name}"
        cached_price = self._get_cached_price(cache_key)
        if cached_price is not None:
            return cached_price

        # Try Binance API first (free, no API key required)
        if not self.use_coingecko:
            price = self._get_binance_current_price(crypto_name)
            if price is not None:
                self._cache_price(cache_key, price)
                return price
        else:
            # Use CoinGecko (requires API key)
            crypto_id = self.coingecko_ids.get(crypto_name.lower())
            if not crypto_id:
                # Try to find closest match
                for key, value in self.coingecko_ids.items():
                    if crypto_name.lower() in key or crypto_name.lower() in value:
                        crypto_id = value
                        break

            if not crypto_id:
                return None

            try:
                url = f"{self.coingecko_api}/simple/price"
                params = {
                    'ids': crypto_id,
                    'vs_currencies': 'usd'
                }

                response = self._get_with_retry(url, params)
                if response:
                    data = response.json()
                    price = data.get(crypto_id, {}).get('usd')
                    price_value = float(price) if price is not None else None

                    # Cache price
                    if price_value is not None:
                        self._cache_price(cache_key, price_value)

                    return price_value

                return None

            except Exception as e:
                print(f"Error fetching price for {crypto_name}: {e}")
                return None

        return None

    def _get_binance_historical_prices_df(self, crypto_name: str, hours: int = 1, interval: str = '15m') -> Optional[pd.DataFrame]:
        """
        Get historical prices from Binance API as a Pandas DataFrame
        Includes: timestamp, open, high, low, close, volume
        """
        symbol = self.binance_symbols.get(crypto_name.lower())
        if not symbol:
            # Try to find closest match
            for key, value in self.binance_symbols.items():
                if crypto_name.lower() in key or crypto_name.lower() in value.lower():
                    symbol = value
                    break

        if not symbol:
            return None

        try:
            url = f"{self.binance_api}/klines"
            params = {
                'symbol': f'{symbol}USDT',
                'interval': interval,
                'limit': hours * (60 if interval == '1m' else 20)  # Get enough data points
            }

            response = self._get_with_retry(url, params)
            if response:
                data = response.json()
                
                # Binance returns: [open_time, open, high, low, close, volume, ...]
                # We need columns for OHLCV
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume', 
                    'close_time', 'quote_asset_volume', 'trades', 
                    'taker_buy_base', 'taker_buy_quote', 'ignore'
                ])
                
                # Convert types
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df['open'] = df['open'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                df['close'] = df['close'].astype(float)
                df['volume'] = df['volume'].astype(float)
                
                # Keep relevant columns
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                return df

            return None

        except Exception as e:
            print(f"Error fetching historical DF from Binance for {crypto_name}: {e}")
            return None

    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate Average Directional Index (ADX) using Pandas
        """
        if len(df) < period + 1:
            return 0.0
            
        # Calculate True Range
        df['h-l'] = df['high'] - df['low']
        df['h-pc'] = abs(df['high'] - df['close'].shift(1))
        df['l-pc'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
        
        # Calculate Directional Movement
        df['up_move'] = df['high'] - df['high'].shift(1)
        df['down_move'] = df['low'].shift(1) - df['low']
        
        df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
        df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
        
        # Calculate Smoothed TR and DM (Wilder's Smoothing)
        # First value is simple sum
        tr14 = df['tr'].rolling(period).sum()
        plus_dm14 = df['plus_dm'].rolling(period).sum()
        minus_dm14 = df['minus_dm'].rolling(period).sum()
        
        # Subsequent values use smoothing: previous - (previous/period) + current
        # For simplicity in this implementation, we'll use EMA as a proxy which is close enough for trading signals
        # Or standard rolling mean for simplicity if dataset is small
        
        # Calculate +DI and -DI
        df['plus_di'] = 100 * (plus_dm14 / tr14)
        df['minus_di'] = 100 * (minus_dm14 / tr14)
        
        # Calculate DX
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
        
        # Calculate ADX (Smoothed DX)
        adx = df['dx'].rolling(period).mean().iloc[-1]
        
        return float(adx) if not pd.isna(adx) else 0.0

    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        """
        Calculate Bollinger Bands
        """
        if len(df) < period:
            return {'upper': 0.0, 'middle': 0.0, 'lower': 0.0, 'percent_b': 0.5}
            
        df['sma'] = df['close'].rolling(period).mean()
        df['std'] = df['close'].rolling(period).std()
        
        df['upper'] = df['sma'] + (df['std'] * std_dev)
        df['lower'] = df['sma'] - (df['std'] * std_dev)
        
        last_row = df.iloc[-1]
        upper = float(last_row['upper'])
        lower = float(last_row['lower'])
        middle = float(last_row['sma'])
        close = float(last_row['close'])
        
        # Percent B: Where is price relative to bands? (0 = lower, 1 = upper, >1 = breakout)
        if upper != lower:
            percent_b = (close - lower) / (upper - lower)
        else:
            percent_b = 0.5
            
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'percent_b': percent_b
        }

    def calculate_volume_trend(self, df: pd.DataFrame, period: int = 20) -> Dict[str, Any]:
        """
        Analyze volume trend
        """
        if len(df) < period:
            return {'trend': 'neutral', 'change_percent': 0.0}
            
        vol_sma = df['volume'].rolling(period).mean()
        current_vol = df['volume'].iloc[-1]
        avg_vol = vol_sma.iloc[-1]
        
        vol_change = ((current_vol - avg_vol) / avg_vol) * 100 if avg_vol > 0 else 0
        
        trend = 'neutral'
        if vol_change > 20:
            trend = 'high'
        elif vol_change < -20:
            trend = 'low'
            
        return {
            'trend': trend,
            'change_percent': vol_change,
            'current': float(current_vol),
            'average': float(avg_vol)
        }

    def _get_binance_historical_prices(self, crypto_name: str, hours: int = 1, interval: str = '15m') -> Optional[List[Tuple[datetime, float]]]:
        """Get historical prices from Binance API"""
        symbol = self.binance_symbols.get(crypto_name.lower())
        if not symbol:
            # Try to find closest match
            for key, value in self.binance_symbols.items():
                if crypto_name.lower() in key or crypto_name.lower() in value.lower():
                    symbol = value
                    break

        if not symbol:
            return None

        try:
            url = f"{self.binance_api}/klines"
            params = {
                'symbol': f'{symbol}USDT',
                'interval': interval,  # 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d
                'limit': hours * (60 if interval == '1m' else 20)  # Get enough data points
            }

            response = self._get_with_retry(url, params)
            if response:
                data = response.json()
                prices = []

                # Binance returns: [open_time, open, high, low, close, volume, close_time, ...]
                # We want (timestamp, close_price)
                for kline in data:
                    timestamp_ms = int(kline[0])
                    timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
                    close_price = float(kline[4])  # Close price is at index 4
                    prices.append((timestamp, close_price))

                return prices

            return None

        except Exception as e:
            print(f"Error fetching historical prices from Binance for {crypto_name}: {e}")
            return None

    def get_historical_prices(self, crypto_name: str, days: int = 7, hours: int = 24, interval: str = '15min') -> Optional[List[Tuple[datetime, float]]]:
        """
        Get historical prices for a cryptocurrency
        :param crypto_name: Name of the cryptocurrency
        :param days: Number of days of historical data (for backward compatibility)
        :param hours: Number of hours of historical data (if provided, overrides days)
        :param interval: Data interval (15min, 1h, 1d)
        :return: List of (timestamp, price) tuples
        """
        # Try Binance API first (free, no API key)
        if not self.use_coingecko:
            # Convert days to hours if needed
            if hours is None:
                hours = days * 24

            # Map interval strings
            interval_map = {
                '15min': '15m',
                '15m': '15m',
                '1hour': '1h',
                '1h': '1h',
                '1day': '1d',
                '1d': '1d',
                'hourly': '1h',
                'daily': '1d'
            }

            binance_interval = interval_map.get(interval, '15m')

            prices = self._get_binance_historical_prices(crypto_name, hours, binance_interval)
            if prices:
                return prices

        # Fallback to CoinGecko (requires API key)
        crypto_id = self.coingecko_ids.get(crypto_name.lower())
        if not crypto_id:
            # Try to find closest match
            for key, value in self.coingecko_ids.items():
                if crypto_name.lower() in key or crypto_name.lower() in value:
                    crypto_id = value
                    break

        if not crypto_id:
            return None

        try:
            # CoinGecko uses 'interval' differently - we need to map it
            interval_param = 'hourly'  # Default to hourly
            if interval in ['15min', '15m']:
                # CoinGecko doesn't have 15min interval, use hourly and filter
                interval_param = 'hourly'

            url = f"{self.coingecko_api}/coins/{crypto_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days if days is not None else hours / 24 if hours else 1
            }

            # Add interval parameter
            if interval_param:
                params['interval'] = interval_param

            response = self._get_with_retry(url, params)
            if response:
                data = response.json()
                prices = data.get('prices', [])

                result = []
                for price_data in prices:
                    timestamp = datetime.fromtimestamp(price_data[0] / 1000)
                    price = float(price_data[1])
                    result.append((timestamp, price))

                return result

            return None

        except Exception as e:
            print(f"Error fetching historical prices for {crypto_name}: {e}")
            return None

    def _get_binance_price_at_time(self, crypto_name: str, target_time: datetime) -> Optional[float]:
        """Get price at or closest to specific time from Binance API"""
        symbol = self.binance_symbols.get(crypto_name.lower())
        if not symbol:
            # Try to find closest match
            for key, value in self.binance_symbols.items():
                if crypto_name.lower() in key or crypto_name.lower() in value.lower():
                    symbol = value
                    break

        if not symbol:
            return None

        try:
            # Get klines (candlestick) data around target time
            # Binance doesn't have direct price-at-time, need to get klines and find closest
            url = f"{self.binance_api}/klines"
            params = {
                'symbol': f'{symbol}USDT',
                'interval': '15m',  # 15-minute candles
                'limit': 100  # Get recent candles
            }

            response = self._get_with_retry(url, params)
            if response:
                data = response.json()

                # Find kline with timestamp closest to target time
                closest_price = None
                closest_diff = float('inf')

                for kline in data:
                    kline_timestamp = datetime.fromtimestamp(kline[0] / 1000)
                    
                    # Make kline_timestamp timezone-aware to match target_time
                    if kline_timestamp.tzinfo is None:
                        kline_timestamp = kline_timestamp.replace(tzinfo=target_time.tzinfo)
                    
                    time_diff = abs((kline_timestamp - target_time).total_seconds())

                    if time_diff < closest_diff:
                        closest_diff = time_diff
                        # Use close price
                        closest_price = float(kline[4])

                # Only return if we have a price within reasonable time window (30 minutes)
                if closest_price is not None and closest_diff <= 1800:  # 30 minutes in seconds
                    return closest_price
                elif closest_price is not None:
                    return closest_price  # Return closest even if > 30 min
                else:
                    return None

            return None

        except Exception as e:
            print(f"  Error getting price at time from Binance for {crypto_name}: {e}")
            return None

    def get_price_at_time(self, crypto_name: str, target_time: datetime) -> Optional[float]:
        """
        Get the price of a cryptocurrency at or closest to a specific time
        :param crypto_name: Name of cryptocurrency
        :param target_time: The target time to find price for
        :return: Price at or closest to target time, or None if not found
        """
        # Try Binance API first (free, no API key)
        if not self.use_coingecko:
            return self._get_binance_price_at_time(crypto_name, target_time)

        try:
            # Fetch historical prices around the target time
            # Get a wider window to ensure we have data
            # For 15M markets, we need data for about 30 minutes around the market period
            hours_needed = 2  # Get 2 hours of data to be safe
            historical_prices = self.get_historical_prices(crypto_name, hours=hours_needed, interval='15min')

            if not historical_prices:
                print(f"  No historical price data available for {crypto_name}")
                return None

            # Find the price with timestamp closest to target time
            closest_price = None
            closest_diff = float('inf')

            for dt, price in historical_prices:
                # Handle timezone differences
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=target_time.tzinfo) or dt.replace(tzinfo=datetime.now().tzinfo)

                time_diff = abs((dt - target_time).total_seconds())

                if time_diff < closest_diff:
                    closest_diff = time_diff
                    closest_price = price

            # Only return if we have a price within reasonable time window (30 minutes)
            if closest_price is not None and closest_diff <= 1800:  # 30 minutes in seconds
                return closest_price
            elif closest_price is not None:
                print(f"  Closest price data is {closest_diff/60:.1f} minutes away from target time")
                return closest_price
            else:
                return None

        except Exception as e:
            print(f"  Error getting price at time for {crypto_name}: {e}")
            return None

    def get_recent_trend_15min(self, crypto_name: str, lookback_minutes: int = 120) -> str:
        """
        Determine the trend for a cryptocurrency based on 15-minute data
        :param crypto_name: Name of the cryptocurrency
        :param lookback_minutes: Number of minutes to look back (default 120 = 8 intervals of 15min)
        :return: Trend as 'bullish', 'bearish', or 'neutral'
        """
        # Convert lookback to hours
        hours = max(1, lookback_minutes // 60)

        historical_prices = self.get_historical_prices(crypto_name, hours=hours, interval='15min')

        if not historical_prices or len(historical_prices) < 2:
            return 'neutral'

        # Filter for the last lookback_minutes
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(minutes=lookback_minutes)

        recent_prices = [(dt, price) for dt, price in historical_prices if dt >= cutoff_time]

        if len(recent_prices) < 2:
            return 'neutral'

        # Calculate trend based on first and last prices in the period
        first_price = recent_prices[0][1]
        last_price = recent_prices[-1][1]

        change_percent = ((last_price - first_price) / first_price) * 100

        # Lower threshold for more trading opportunities
        if change_percent > 0.2:  # 0.2% threshold
            return 'bullish'
        elif change_percent < -0.2:  # -0.2% threshold
            return 'bearish'
        else:
            return 'neutral'

    def get_volatility_15min(self, crypto_name: str, lookback_minutes: int = 120) -> float:
        """
        Calculate volatility based on 15-minute price data
        :param crypto_name: Name of the cryptocurrency
        :param lookback_minutes: Number of minutes to look back
        :return: Volatility as a percentage
        """
        # Convert lookback to hours
        hours = max(1, lookback_minutes // 60)

        historical_prices = self.get_historical_prices(crypto_name, hours=hours, interval='15min')

        if not historical_prices or len(historical_prices) < 2:
            return 0.0

        # Filter for the last lookback_minutes
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(minutes=lookback_minutes)

        recent_prices = [price for dt, price in historical_prices if dt >= cutoff_time]

        if len(recent_prices) < 2:
            return 0.0

        # Calculate standard deviation of returns
        returns = []
        for i in range(1, len(recent_prices)):
            ret = (recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]
            returns.append(ret)

        if not returns:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((ret - mean_return) ** 2 for ret in returns) / len(returns)
        volatility = (variance ** 0.5) * 100  # Convert to percentage

        return volatility

    def get_technical_indicators(self, crypto_name: str, timeframe: str = '15min') -> Dict[str, float]:
        """
        Calculate technical indicators for a cryptocurrency
        Uses caching to improve performance (5-minute TTL)

        :param crypto_name: Name of the cryptocurrency
        :param timeframe: Timeframe for analysis ('15min', '1hour', '1day')
        :return: Dictionary with indicators
        """
        # Check cache first
        cache_key = f"{crypto_name}_{timeframe}"
        current_time = time.time()

        if cache_key in self._tech_cache:
            cached_data = self._tech_cache[cache_key]
            if current_time - cached_data['timestamp'] < self._cache_ttl:
                return cached_data['indicators'].copy()  # Return copy to prevent modification

        # Cache miss - calculate indicators
        indicators = self._calculate_technical_indicators(crypto_name, timeframe)

        # Store in cache
        self._tech_cache[cache_key] = {
            'timestamp': current_time,
            'indicators': indicators.copy()
        }

        return indicators

    def _calculate_technical_indicators(self, crypto_name: str, timeframe: str = '15min') -> Dict[str, float]:
        """
        Internal method to calculate technical indicators (not cached)
        """
        hours = 1  # Default to 1 hour
        interval = '15m'
        rsi_period = 14

        if timeframe == '15min':
            hours = 8  # Need 8 hours for 14-period RSI on 15m candles (32 points)
            interval = '15m'
        elif timeframe == '1hour' or timeframe == '1h':
            hours = 48  # 2 days of 1h candles
            interval = '1h'
        elif timeframe == '1day' or timeframe == '1d':
            hours = 336  # 14 days of 1d candles
            interval = '1d'

        historical_prices = self.get_historical_prices(crypto_name, hours=hours, interval=interval)

        if not historical_prices or len(historical_prices) < rsi_period + 1:
            return {}

        prices = [price for dt, price in historical_prices]

        # Short-term SMA (9-period) - faster response
        sma_9 = sum(prices[-9:]) / min(9, len(prices)) if len(prices) >= 9 else sum(prices) / len(prices)
        
        # Medium-term SMA (20-period) - medium response
        sma_20 = sum(prices[-20:]) / min(20, len(prices)) if len(prices) >= 20 else sma_9
        
        # Long-term SMA (50-period) - slow response
        sma_50 = sum(prices[-50:]) / min(50, len(prices)) if len(prices) >= 50 else sma_20

        # Current price vs SMAs
        current_price = prices[-1]
        
        # Price vs SMA ratio (using 20-period as reference)
        price_sma_ratio = (current_price / sma_20) * 100 if sma_20 > 0 else 100
        
        # SMA alignment signal (bullish if price > sma_9 > sma_20 > sma_50)
        sma_alignment = 0
        if sma_9 > sma_20 > sma_50:
            sma_alignment = 0.1  # Strong bullish alignment
        elif sma_9 < sma_20 < sma_50:
            sma_alignment = -0.1  # Strong bearish alignment

        # Volatility
        if len(prices) > 1:
            returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
            mean_return = sum(returns) / len(returns)
            variance = sum((ret - mean_return) ** 2 for ret in returns) / len(returns)
            volatility = (variance ** 0.5) * 100
        else:
            volatility = 0.0

        # RSI (7-period for 15min trading - faster signals)
        rsi_period = 7 if timeframe == '15min' else 14
        rsi = self.calculate_rsi(prices, period=rsi_period)
        
        # MACD (12, 26, 9 standard)
        macd_line, signal_line, macd_histogram = self.calculate_macd(prices, fast=12, slow=26, signal=9)

        # NEW: Advanced Indicators using Pandas (ADX, Bollinger, Volume)
        adx = 0.0
        bb = {'upper': 0.0, 'lower': 0.0, 'percent_b': 0.5}
        vol_data = {'trend': 'neutral'}
        
        try:
            # Re-fetch as DataFrame for advanced calc
            # We need more data for accurate ADX/BB (at least 20-30 periods)
            df = self._get_binance_historical_prices_df(crypto_name, hours=hours*2, interval=interval)
            if df is not None and not df.empty:
                adx = self.calculate_adx(df)
                bb = self.calculate_bollinger_bands(df)
                vol_data = self.calculate_volume_trend(df)
        except Exception as e:
            print(f"Error calculating advanced indicators for {crypto_name}: {e}")

        return {
            'sma_9': sma_9,
            'sma_20': sma_20,
            'sma_50': sma_50,
            'price_sma_ratio': price_sma_ratio,
            'sma_alignment': sma_alignment,
            'volatility': volatility,
            'rsi': rsi,
            'macd_line': macd_line,
            'signal_line': signal_line,
            'macd_histogram': macd_histogram,
            'adx': adx,
            'bb_upper': bb.get('upper', 0.0),
            'bb_lower': bb.get('lower', 0.0),
            'bb_percent_b': bb.get('percent_b', 0.5),
            'volume_trend': vol_data.get('trend', 'neutral')
        }

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """
        Calculate the Relative Strength Index (RSI) for a list of prices.
        
        :param prices: List of prices (must have at least 'period' + 1 values)
        :param period: RSI period (standard is 14, use 7 for faster signals on 15min)
        :return: RSI value (0-100)
        """
        if len(prices) < period + 1:
            return 50.0  # Default to neutral if not enough data

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        # Use the last 'period' values
        recent_gains = gains[-period:]
        recent_losses = losses[-period:]

        avg_gain = sum(recent_gains) / period
        avg_loss = sum(recent_losses) / period

        if avg_loss == 0:
            return 100.0  # Strong bullish signal if no losses

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        :param prices: List of prices
        :param fast: Fast EMA period (default 12)
        :param slow: Slow EMA period (default 26)
        :param signal: Signal line period (default 9)
        :return: Tuple of (MACD line, Signal line, MACD Histogram)
        """
        if len(prices) < slow + signal:
            return 0.0, 0.0, 0.0
        
        # Calculate EMAs
        def calc_ema(prices_list, period):
            if len(prices_list) < period:
                return sum(prices_list) / len(prices_list)
            k = 2 / (period + 1)
            ema = prices_list[0]
            for price in prices_list[1:]:
                ema = price * k + ema * (1 - k)
            return ema
        
        ema_fast = calc_ema(prices[-fast:], fast) if len(prices) >= fast else calc_ema(prices, len(prices))
        ema_slow = calc_ema(prices[-slow:], slow) if len(prices) >= slow else calc_ema(prices, len(prices))
        
        macd_line = ema_fast - ema_slow
        
        # Calculate signal line (EMA of MACD line)
        # Create synthetic MACD values for signal calculation
        macd_values = []
        for i in range(max(0, len(prices) - slow), len(prices)):
            # Recalculate MACD for each point (simplified)
            start_idx = max(0, i - slow + 1)
            fast_ema = calc_ema(prices[start_idx:i+1], fast) if i - start_idx + 1 >= fast else calc_ema(prices[start_idx:i+1], i - start_idx + 1)
            slow_ema = calc_ema(prices[start_idx:i+1], slow) if i - start_idx + 1 >= slow else calc_ema(prices[start_idx:i+1], i - start_idx + 1)
            macd_values.append(fast_ema - slow_ema)
        
        signal_line = calc_ema(macd_values[-signal:], signal) if len(macd_values) >= signal else calc_ema(macd_values, len(macd_values))
        
        macd_histogram = macd_line - signal_line
        
        return macd_line, signal_line, macd_histogram

    # Legacy methods for test compatibility (not used in app)
    def get_chainlink_feed_address(self, pair: str) -> Optional[str]:
        """Get Chainlink feed address (legacy, for tests only)"""
        # This is not implemented for Binance API
        # Chainlink feeds are Ethereum contract addresses
        # Binance doesn't provide this
        return None

    def get_crypto_trend(self, crypto_name: str, days: int = 7) -> str:
        """Get crypto trend (legacy, for tests only)"""
        # Use 15min trend as fallback
        return self.get_recent_trend_15min(crypto_name, lookback_minutes=days*24*60)

    def get_multiple_prices(self, crypto_names: List[str]) -> Dict[str, float]:
        """Get multiple crypto prices at once (legacy, for tests only)"""
        prices = {}
        for name in crypto_names:
            price = self.get_current_price(name)
            if price is not None:
                prices[name] = price
        return prices
