import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import os
import time
from ..config.settings import DEFAULT_INITIAL_BALANCE


class ChainlinkDataProvider:
    """
    Provides cryptocurrency price data from Chainlink-compatible sources.
    This implementation uses multiple data sources to simulate Chainlink's
    decentralized oracle network approach.

    PRIMARY: Binance API (free, 1200 requests/minute)
    FALLBACK: CoinGecko API (requires API key, no free tier)
    """

    def __init__(self):
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
            'cardano': 'ADA',
            'ada': 'ADA',
            'ripple': 'XRP',
            'xrp': 'XRP',
            'dogecoin': 'DOGE',
            'doge': 'DOGE',
            'polkadot': 'DOT',
            'dot': 'DOT',
            'litecoin': 'LTC',
            'ltc': 'LTC',
            'bitcoin-cash': 'BCH',
            'bch': 'BCH',
            'bnb': 'BNB',
            'binancecoin': 'BNB',
            'chainlink': 'LINK',
            'link': 'LINK',
            'polygon': 'MATIC',
            'matic': 'MATIC',
            'avalanche': 'AVAX',
            'shiba-inu': 'SHIB',
            'shib': 'SHIB',
            'tron': 'TRX',
            'trx': 'TRX',
            'solana': 'SOL',
            'avalanche': 'AVAX'
        }

        # Common cryptocurrency IDs for CoinGecko API (fallback)
        self.coingecko_ids = {
            'bitcoin': 'bitcoin',
            'ethereum': 'ethereum',
            'solana': 'solana',
            'cardano': 'cardano',
            'ripple': 'ripple',
            'dogecoin': 'dogecoin',
            'polkadot': 'polkadot',
            'litecoin': 'litecoin',
            'bitcoin-cash': 'bitcoin-cash',
            'bnb': 'binancecoin',
            'xrp': 'ripple',
            'usd-coin': 'usd-coin',
            'solana': 'solana',
            'avalanche': 'avalanche-2',
            'chainlink': 'chainlink',
            'polygon': 'polygon',
            'defi': 'defi-pulse-index'
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
                    timestamp = datetime.fromtimestamp(kline[0] / 1000)
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
        :param crypto_name: Name of the cryptocurrency
        :param timeframe: Timeframe for analysis ('15min', '1hour', '1day')
        :return: Dictionary with indicators
        """
        hours = 1  # Default to 1 hour
        if timeframe == '1hour' or timeframe == '1h':
            hours = 1
        elif timeframe == '1day' or timeframe == '1d':
            hours = 24

        interval = '15m' if timeframe == '15min' or timeframe == '15min' else '1h'

        historical_prices = self.get_historical_prices(crypto_name, hours=hours, interval=interval)

        if not historical_prices or len(historical_prices) < 2:
            return {}

        prices = [price for dt, price in historical_prices]

        # Simple Moving Average (SMA)
        sma = sum(prices) / len(prices)

        # Price vs SMA ratio
        current_price = prices[-1]
        price_sma_ratio = (current_price / sma) * 100 if sma > 0 else 100

        # Volatility
        if len(prices) > 1:
            returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
            mean_return = sum(returns) / len(returns)
            variance = sum((ret - mean_return) ** 2 for ret in returns) / len(returns)
            volatility = (variance ** 0.5) * 100
        else:
            volatility = 0.0

        return {
            'sma': sma,
            'price_sma_ratio': price_sma_ratio,
            'volatility': volatility
        }

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
