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
    """

    def __init__(self):
        # Using CoinGecko as a reliable data source that can complement Chainlink feeds
        # Get API key from environment (CoinGecko now requires API keys for many endpoints)
        self.api_key = os.getenv('COINGECKO_API_KEY', '')

        if self.api_key:
            # Use Pro API endpoint with API key
            self.coingecko_api = "https://pro-api.coingecko.com/api/v3"
        else:
            # Use free endpoint (rate limited)
            self.coingecko_api = "https://api.coingecko.com/api/v3"

        # Alternative: You can use other APIs that provide similar data to Chainlink
        self.alternative_api = "https://api.binance.com/api/v3"

        # Cache for reducing API calls (cache price for 30 seconds)
        self.price_cache = {}
        self.cache_duration = 30  # seconds

        # Rate limiting delays (in seconds)
        self.last_request_time = 0
        self.min_request_delay = 3.0  # Wait at least 1.2 seconds between requests

    def _rate_limit_request(self):
        """Apply rate limiting to API requests"""
        time_since_last_request = time.time() - self.last_request_time
        if time_since_last_request < self.min_request_delay:
            sleep_time = self.min_request_delay - time_since_last_request
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _get_with_retry(self, url: str, params: Dict = None, max_retries: int = 3) -> Optional[requests.Response]:
        """Make HTTP request with retry logic and rate limiting"""
        for attempt in range(max_retries):
            try:
                # Apply rate limiting
                self._rate_limit_request()

                # Add API key if available
                headers = {}
                if self.api_key:
                    headers['x-cg-pro-api-key'] = self.api_key

                response = requests.get(url, params=params, headers=headers, timeout=10)

                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    wait_time = min(retry_after, 120)  # Cap at 2 minutes
                    print(f"  Rate limited. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue

                # Handle unauthorized (401) - try with free endpoint
                if response.status_code == 401 and self.api_key:
                    print(f"  API key unauthorized. Trying free endpoint...")
                    # Remove API key and retry
                    self.api_key = ''
                    url = url.replace('pro-api', 'api')
                    self.coingecko_api = url.split('/api')[0] + '/api/v3'
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.Timeout:
                print(f"  Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff: 2s, 4s, 8s
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
        
        # Common cryptocurrency IDs for CoinGecko API
        self.crypto_ids = {
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
    
    def get_current_price(self, crypto_name: str) -> Optional[float]:
        """
        Get the current price for a cryptocurrency
        :param crypto_name: Name of the cryptocurrency (e.g., 'bitcoin', 'ethereum')
        :return: Current price in USD or None if not found
        """
        crypto_id = self.crypto_ids.get(crypto_name.lower())
        if not crypto_id:
            # Try to find the closest match
            for key, value in self.crypto_ids.items():
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
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            price = data.get(crypto_id, {}).get('usd')
            return float(price) if price is not None else None
            
        except Exception as e:
            print(f"Error fetching price for {crypto_name}: {e}")
            return None
    
    def get_historical_prices(self, crypto_name: str, days: int = 7, hours: int = 24, interval: str = '15min') -> Optional[List[Tuple[datetime, float]]]:
        """
        Get historical prices for a cryptocurrency
        :param crypto_name: Name of the cryptocurrency
        :param days: Number of days of historical data (for backward compatibility)
        :param hours: Number of hours of historical data (max 24h for minute intervals on free tier)
        :param interval: Time interval ('15min', '30min', '1h', 'daily')
        :return: List of (datetime, price) tuples or None if not found
        """
        crypto_id = self.crypto_ids.get(crypto_name.lower())
        if not crypto_id:
            # Try to find the closest match
            for key, value in self.crypto_ids.items():
                if crypto_name.lower() in key or crypto_name.lower() in value:
                    crypto_id = value
                    break

        if not crypto_id:
            return None

        try:
            url = f"{self.coingecko_api}/coins/{crypto_id}/market_chart"

            # Map our interval to CoinGecko's supported intervals
            # CoinGecko supports: 'minutely' (up to 1 day), 'hourly' (up to 90 days), 'daily' (up to max)
            if interval == '15min':
                # For 15-minute-like data, use 'hourly' as CoinGecko doesn't support 15min specifically
                # but we'll treat hourly data as our closest approximation to 15min for this implementation
                cg_interval = 'hourly'
            elif interval.startswith('1h'):
                cg_interval = 'hourly'
            else:
                cg_interval = 'daily'

            # Calculate days based on hours
            effective_days = max(1, hours // 24) if hours > 24 else days  # Use hours if > 24, otherwise use days
            if hours < 24 and interval == '15min':
                effective_days = '1'  # For 15min intervals, limit to 1 day max
            elif hours < 24:
                effective_days = f'{hours}h'  # For sub-day periods, use hour notation if supported

            params = {
                'vs_currency': 'usd',
                'days': effective_days,
                'interval': cg_interval
            }

            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            prices_data = data.get('prices', [])

            # Convert to list of (datetime, price) tuples
            historical_prices = []
            for timestamp_price in prices_data:
                timestamp_ms, price = timestamp_price
                dt = datetime.fromtimestamp(timestamp_ms / 1000)  # Convert ms to seconds
                historical_prices.append((dt, float(price)))

            return historical_prices

        except Exception as e:
            print(f"Error fetching historical prices for {crypto_name}: {e}")
            return None

    def get_recent_trend_15min(self, crypto_name: str, lookback_minutes: int = 120) -> str:
        """
        Determine the trend for a cryptocurrency based on 15-minute data
        :param crypto_name: Name of the cryptocurrency
        :param lookback_minutes: Number of minutes to look back (default 120 = 8 intervals of 15min)
        :return: Trend as 'bullish', 'bearish', or 'neutral'
        """
        # Calculate hours needed based on lookback minutes
        hours = max(1, lookback_minutes // 60)

        historical_prices = self.get_historical_prices(crypto_name, hours=hours, interval='15min')

        if not historical_prices or len(historical_prices) < 2:
            return 'neutral'

        # Filter for the last lookback_minutes
        import time
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(minutes=lookback_minutes)

        recent_prices = [(dt, price) for dt, price in historical_prices if dt >= cutoff_time]

        if len(recent_prices) < 2:
            return 'neutral'

        # Calculate trend based on first and last prices in the period
        first_price = recent_prices[0][1]
        last_price = recent_prices[-1][1]

        change_percent = ((last_price - first_price) / first_price) * 100

        if change_percent > 1.0:  # Adjust threshold for 15-min timeframe
            return 'bullish'
        elif change_percent < -1.0:  # Adjust threshold for 15-min timeframe
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
        # Calculate hours needed based on lookback minutes
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

    def get_price_at_time(self, crypto_name: str, target_time: datetime) -> Optional[float]:
        """
        Get the price of a cryptocurrency at or closest to a specific time
        :param crypto_name: Name of cryptocurrency
        :param target_time: The target time to find price for
        :return: Price at or closest to target time, or None if not found
        """
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
            if closest_price and closest_diff <= 1800:  # 30 minutes in seconds
                return closest_price
            elif closest_price:
                print(f"  Closest price data is {closest_diff/60:.1f} minutes away from target time")
                return closest_price
            else:
                return None

        except Exception as e:
            print(f"  Error getting price at time for {crypto_name}: {e}")
            return None
    
    def get_multiple_prices(self, crypto_names: List[str]) -> Dict[str, float]:
        """
        Get current prices for multiple cryptocurrencies
        :param crypto_names: List of cryptocurrency names
        :return: Dictionary mapping crypto name to price
        """
        prices = {}
        
        # Group crypto names by their IDs for a single API call
        crypto_ids = []
        name_to_id = {}
        
        for name in crypto_names:
            crypto_id = self.crypto_ids.get(name.lower())
            if not crypto_id:
                # Try to find the closest match
                for key, value in self.crypto_ids.items():
                    if name.lower() in key or name.lower() in value:
                        crypto_id = value
                        break
            
            if crypto_id:
                crypto_ids.append(crypto_id)
                name_to_id[crypto_id] = name
        
        if not crypto_ids:
            return prices
        
        try:
            # Join crypto IDs with commas for the API call
            ids_str = ','.join(crypto_ids)
            url = f"{self.coingecko_api}/simple/price"
            params = {
                'ids': ids_str,
                'vs_currencies': 'usd'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            for crypto_id, price_data in data.items():
                crypto_name = name_to_id.get(crypto_id)
                if crypto_name and 'usd' in price_data:
                    prices[crypto_name] = float(price_data['usd'])
            
            return prices
            
        except Exception as e:
            print(f"Error fetching multiple prices: {e}")
            return prices
    
    def get_chainlink_feed_address(self, pair: str) -> Optional[str]:
        """
        Get the Chainlink feed address for a specific pair (simulated)
        In a real implementation, this would return actual Chainlink contract addresses
        :param pair: Currency pair (e.g., 'BTC/USD', 'ETH/USD')
        :return: Simulated contract address
        """
        # This is a simulation - in a real implementation, you'd have actual addresses
        feed_addresses = {
            'BTC/USD': '0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c',  # Real Chainlink BTC/USD feed
            'ETH/USD': '0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419',  # Real Chainlink ETH/USD feed
            'SOL/USD': '0x5SS77X3HuUx4T6X1FAJrcP5BnzQN99JwdL3yieYfJazW',  # Placeholder
            'ADA/USD': '0xAE480456D34300Dc529c0Eb4b6C4bED6e68E5453',  # Placeholder
            'LINK/USD': '0x26a9a27CD55019f1d66270D43e89269f9e4aA90a',  # Placeholder
        }
        
        return feed_addresses.get(pair.upper())
    
    def get_crypto_trend(self, crypto_name: str, days: int = 7) -> str:
        """
        Determine the trend for a cryptocurrency based on historical data
        :param crypto_name: Name of the cryptocurrency
        :param days: Number of days to analyze
        :return: Trend as 'bullish', 'bearish', or 'neutral'
        """
        historical_prices = self.get_historical_prices(crypto_name, days)
        
        if not historical_prices or len(historical_prices) < 2:
            return 'neutral'
        
        # Calculate simple trend based on first and last prices
        first_price = historical_prices[0][1]
        last_price = historical_prices[-1][1]
        
        change_percent = ((last_price - first_price) / first_price) * 100
        
        if change_percent > 2.0:
            return 'bullish'
        elif change_percent < -2.0:
            return 'bearish'
        else:
            return 'neutral'
    
    def get_technical_indicators(self, crypto_name: str, days: int = 30) -> Dict[str, float]:
        """
        Calculate basic technical indicators for a cryptocurrency
        :param crypto_name: Name of the cryptocurrency
        :param days: Number of days of historical data
        :return: Dictionary of technical indicators
        """
        historical_prices = self.get_historical_prices(crypto_name, days)
        
        if not historical_prices:
            return {}
        
        prices = [price for _, price in historical_prices]
        
        # Simple moving average (SMA)
        sma = sum(prices) / len(prices)
        
        # Volatility (standard deviation)
        mean = sma
        variance = sum((price - mean) ** 2 for price in prices) / len(prices)
        volatility = variance ** 0.5
        
        # Current price vs SMA
        current_price = prices[-1]
        price_sma_ratio = current_price / sma if sma != 0 else 0
        
        return {
            'sma': sma,
            'volatility': volatility,
            'current_price': current_price,
            'price_sma_ratio': price_sma_ratio,
            'trend_direction': 'bullish' if current_price > sma else 'bearish'
        }