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

    def get_15m_crypto_markets(self, limit: int = 100) -> List[Dict]:
        """
        Get crypto markets that expire in approximately 15 minutes (15M markets)
        :param limit: Number of markets to return
        :return: List of 15M crypto-related market dictionaries
        """
        # Calculate time window for 15-minute expiry
        now = datetime.now(timezone.utc)
        # Look for markets expiring between 1 and 16 minutes from now
        end_date_min = now + timedelta(minutes=1)
        end_date_max = now + timedelta(minutes=16)

        # Format as ISO 8601 strings
        end_date_min_str = end_date_min.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date_max_str = end_date_max.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Query Polymarket API for markets expiring in this window
        params = {
            'active': 'true',
            'closed': 'false',
            'archived': 'false',
            'end_date_min': end_date_min_str,
            'end_date_max': end_date_max_str,
            'limit': limit
        }

        response = requests.get(f"{self.gamma_api_base}/markets", params=params)
        response.raise_for_status()
        markets = response.json()

        # Filter for crypto-related markets only
        crypto_markets = []
        for market in markets:
            if self._is_crypto_market(market):
                crypto_markets.append(market)

        return crypto_markets

    def _is_crypto_market(self, market: Dict) -> bool:
        """
        Check if a market is crypto-related
        :param market: Market dictionary
        :return: True if crypto-related, False otherwise
        """
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        category = market.get('category', '').lower()

        # Check if the market is in a crypto-related category (highest priority)
        is_crypto_category = category in ['crypto', 'defi', 'bitcoin', 'ethereum', 'altcoins']
        if is_crypto_category:
            return True

        # Check for crypto asset names with word boundary matching
        crypto_assets = [
            'bitcoin', 'ethereum', 'btc', 'eth', 'solana', 'sol', 'cardano', 'ada',
            'ripple', 'xrp', 'dogecoin', 'doge', 'polkadot', 'dot', 'litecoin', 'ltc',
            'bitcoin cash', 'bch', 'bnb', 'binance coin', 'chainlink', 'link',
            'polygon', 'matic', 'shiba', 'shib', 'tron', 'trx', 'monero', 'xmr',
            'stellar', 'xlm', 'vechain', 'vnx', 'zcash', 'zec', 'algorand', 'algo'
        ]

        # Check for crypto asset names with financial/trading terms
        for asset in crypto_assets:
            asset_pattern = r'\b' + re.escape(asset) + r'\b'
            if re.search(asset_pattern, question) or re.search(asset_pattern, description):
                # Check for 15M crypto market patterns (e.g., "Bitcoin Up or Down")
                crypto_15m_phrases = [
                    'up or down', 'up/down', 'price up or down', 'higher or lower',
                    'increase or decrease', 'above or below', 'price target',
                    'close above', 'close below', 'direction', 'movement'
                ]
                if any(phrase.lower() in question.lower() for phrase in crypto_15m_phrases):
                    return True

                # Look for financial/trading related terms that are specifically related to crypto
                # Use individual words with word boundaries to avoid false positives
                crypto_financial_words = [
                    'price', 'value', 'worth', 'market', 'trading', 'trade',
                    'reach', 'hit', 'target', 'close', 'end', 'finish', 'settle',
                    'increase', 'decrease', 'above', 'below', 'higher', 'lower',
                    'volume', 'cap', 'token', 'coin', 'crypto', 'usd', 'dollar'
                ]

                combined_text = question + " " + description
                # Check if any financial word appears (with word boundaries)
                for word in crypto_financial_words:
                    word_pattern = r'\b' + re.escape(word) + r'\b'
                    if re.search(word_pattern, combined_text):
                        # Make sure it's not just the crypto name itself
                        # For example, "bitcoin" is in crypto_assets list, so ignore if it's just that
                        if word.lower() not in [asset.lower() for asset in crypto_assets]:
                            return True

        # Check for specific crypto exchanges or platforms with word boundaries
        crypto_exchanges = ['coinbase', 'binance', 'kraken', 'ftx', 'huobi', 'kucoin', 'gate.io']
        for exchange in crypto_exchanges:
            exchange_pattern = r'\b' + re.escape(exchange) + r'\b'
            if re.search(exchange_pattern, question) or re.search(exchange_pattern, description):
                return True

        # Check for DeFi/Blockchain specific terms
        defi_blockchain_terms = [
            'defi', 'decentralized finance', 'blockchain', 'nft', 'web3', 'smart contract',
            'tokenomics', 'staking', 'yield farming', 'liquidity', 'dex', 'amm',
            'lp token', 'governance', 'dao', 'erc-20', 'erc-721',
            'layer 2', 'scaling', 'gas fee', 'transaction fee', 'mining',
            'proof of stake', 'proof of work', 'validator', 'node', 'wallet'
        ]
        combined_text = question + " " + description
        for term in defi_blockchain_terms:
            term_pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(term_pattern, combined_text):
                return True

        return False

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
        Get the order book for a specific token
        :param token_id: The token ID for which to get the order book
        :return: Order book data
        """
        response = requests.get(f"{self.clob_api_base}/book", params={'token_id': token_id})
        response.raise_for_status()
        return response.json()

    def get_current_price(self, token_id: str) -> float:
        """
        Get the current price for a specific token
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
        :param use_15m_only: If True, only return 15M crypto markets (expiring in ~15 minutes)
        :param limit: Number of markets to return
        :return: List of crypto-related market dictionaries
        """
        # If 15M markets requested, use the dedicated method
        if use_15m_only:
            return self.get_15m_crypto_markets(limit)

        # Otherwise, get all markets and filter for crypto
        all_markets = self.get_markets(limit=1000)

        crypto_markets = []
        for market in all_markets:
            if self._is_crypto_market(market):
                crypto_markets.append(market)

        return crypto_markets

    def get_market_prices(self, market_id: str) -> Dict[str, float]:
        """
        Get current prices for both YES and NO outcomes of a market
        :param market_id: The market ID
        :return: Dictionary with YES and NO prices
        """
        market_details = self.get_market_by_id(market_id)

        prices = {'yes': 0.0, 'no': 0.0}

        if 'outcomes' in market_details and 'prices' in market_details:
            outcomes = market_details['outcomes']
            raw_prices = market_details['prices']

            # Convert raw prices to floats
            if len(outcomes) >= 2 and len(raw_prices) >= 2:
                prices['yes'] = float(raw_prices[0])
                prices['no'] = float(raw_prices[1])

        return prices