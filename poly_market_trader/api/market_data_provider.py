import requests
from typing import Dict, List, Optional
from ..models.trade import MarketDirection
from ..config.settings import GAMMA_API_BASE, CLOB_API_BASE, DATA_API_BASE
from datetime import datetime, timedelta, timezone
import json
import re


class MarketDataProvider:
    """Fetches real market data from Polymarket APIs"""

    def __init__(self):
        self.gamma_api_base = GAMMA_API_BASE
        self.clob_api_base = CLOB_API_BASE
        self.data_api_base = DATA_API_BASE

    def _fetch_events(self, limit=100, offset=0) -> List[Dict]:
        """Fetch events from Gamma API"""
        url = f"{self.gamma_api_base}/events"
        
        params = {
            'active': 'true',
            'closed': 'false',
            'limit': limit,
            'offset': offset
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching events: {e}")
            return []

    def get_market_prices(self, market_id: str) -> Dict[str, float]:
        """
        Get current prices for both YES and NO outcomes of a market
        Checks outcomePrices first, then falls back to CLOB prices
        :param market_id: The market ID
        :return: Dictionary with YES and NO prices
        """
        market_details = self.get_market_by_id(market_id)
        prices = {'yes': 0.0, 'no': 0.0}
        
        outcomes = market_details.get('outcomes')
        # Parse outcomes
        if outcomes and isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except:
                pass
        
        if not outcomes or not isinstance(outcomes, list) or len(outcomes) < 2:
            return prices

        # Determine indices
        yes_index = 0
        no_index = 1
        for i, outcome in enumerate(outcomes):
            outcome_lower = str(outcome).lower()
            if outcome_lower in ['yes', 'up', 'long']:
                yes_index = i
            elif outcome_lower in ['no', 'down', 'short']:
                no_index = i

        # Try outcomePrices first
        raw_prices = market_details.get('outcomePrices') or market_details.get('outcome_prices')
        if raw_prices:
            if isinstance(raw_prices, str):
                try:
                    raw_prices = json.loads(raw_prices)
                except:
                    pass
            
            if isinstance(raw_prices, list) and len(raw_prices) >= 2:
                try:
                    # Use max index to avoid index out of range
                    if len(raw_prices) > max(yes_index, no_index):
                        prices['yes'] = float(raw_prices[yes_index])
                        prices['no'] = float(raw_prices[no_index])
                except Exception as e:
                    print(f"Error parsing raw prices: {e}")

        return prices

    def get_crypto_up_down_markets(self, limit: int = 100) -> List[Dict]:
        """
        Get crypto up/down markets (15M, 1H, 4H) with volume > 0
        Uses regex: (eth|xrp|btc|sol)-updown-(15m|1h|4h)-
        :param limit: Number of markets to return
        :return: List of crypto up/down market dictionaries
        """
        # Fetch all active events with pagination
        all_events = []
        offset = 0
        event_limit = 100
        max_events = 10000 # Increased limit to scan enough events
        
        print("Scanning active events for opportunities...")
        while len(all_events) < max_events:
            events = self._fetch_events(limit=event_limit, offset=offset)
            if not events:
                break
            all_events.extend(events)
            if len(events) < event_limit:
                break
            offset += event_limit
        
        print(f"Scanned {len(all_events)} events.")

        # Filter for crypto up/down markets by slug regex and volume
        crypto_markets = []
        # Strict regex as requested
        slug_pattern = re.compile(r'(eth|xrp|btc|sol)-updown-(15m|1h|4h)-')
        
        for event in all_events:
            slug = event.get('slug', '').lower()
            
            # Apply strict regex filter on slug
            if not slug_pattern.search(slug):
                continue
            
            # Get markets from event
            markets = event.get('markets', [])
            if not markets:
                continue
            
            # Check volume at MARKET level
            for market in markets:
                try:
                    volume = float(market.get('volume', 0))
                except (ValueError, TypeError):
                    volume = 0.0
                
                # Check timestamps to avoid betting too far in advance
                # We only want markets ending within the next 90 minutes
                # (15m duration + 75m lookahead)
                end_date_str = market.get('endDate')
                is_imminent = False
                
                if end_date_str:
                    try:
                        # Handle 'Z' manually if python < 3.11
                        if end_date_str.endswith('Z'):
                            end_date_str = end_date_str[:-1] + '+00:00'
                        
                        end_time = datetime.fromisoformat(end_date_str)
                        now = datetime.now(timezone.utc)
                        
                        # Calculate time until end
                        time_to_end = (end_time - now).total_seconds()
                        
                        # Filter:
                        # 1. Must be in future (time_to_end > 0)
                        # 2. Must be within 90 minutes (5400 seconds)
                        if 0 < time_to_end <= 5400:
                            is_imminent = True
                        else:
                            # Skip if too far in future or already passed
                            continue
                            
                    except Exception as e:
                        print(f"Error parsing date {end_date_str}: {e}")
                        continue
                else:
                    # No date, skip to be safe
                    continue

                # Only include markets with volume > 0 AND are imminent
                if volume > 0 and is_imminent:
                    market['title'] = event.get('title', '')
                    market['slug'] = event.get('slug', '')
                    market['event_id'] = event.get('id')
                    crypto_markets.append(market)
                
                if len(crypto_markets) >= limit:
                    break
            
            if len(crypto_markets) >= limit:
                break
        
        if crypto_markets:
            print(f"Found {len(crypto_markets)} crypto up/down markets with volume > 0")
        else:
            print("No crypto up/down markets found matching regex")
        
        return crypto_markets

    def get_markets(self, category: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Get all available markets or filter by category
        :param category: Filter markets by category (e.g., 'Crypto')
        :param limit: Number of markets to return
        :return: List of market dictionaries
        """
        params = {'limit': limit}
        if category:
            params['category'] = category

        response = requests.get(f"{self.gamma_api_base}/markets", params=params)
        response.raise_for_status()
        return response.json()

    def get_market_by_id(self, market_id: str) -> Dict:
        """
        Get a specific market by its ID
        :param market_id: The unique identifier for the market
        :return: Market details
        """
        response = requests.get(f"{self.gamma_api_base}/markets", params={'marketId': market_id})
        response.raise_for_status()
        markets = response.json()
        return markets[0] if markets else {}

    def get_order_book(self, token_id: str) -> Dict:
        """
        Get order book for a specific token
        :param token_id: The token ID for which to get the order book
        :return: Order book data
        """
        response = requests.get(f"{self.clob_api_base}/book", params={'token_id': token_id})
        response.raise_for_status()
        return response.json()

    def get_current_price(self, token_id: str) -> float:
        """
        Get current price for a specific token
        :param token_id: The token ID for which to get the price
        :return: Current price
        """
        response = requests.get(f"{self.clob_api_base}/price", params={'token_id': token_id})
        response.raise_for_status()
        price_data = response.json()
        return float(price_data.get('price', 0))

    def get_crypto_markets(self, use_15m_only: bool = False, limit: int = 100) -> List[Dict]:
        """
        Get all markets related to cryptocurrency
        :param use_15m_only: If True, only return crypto up/down markets (15min, 1h, 4h timeframes)
        :param limit: Number of markets to return
        :return: List of crypto-related market dictionaries
        """
        # If 15M markets requested, use the new method
        if use_15m_only:
            return self.get_crypto_up_down_markets(limit)
        
        # For non-15m, return empty list (not used in main app)
        return []
