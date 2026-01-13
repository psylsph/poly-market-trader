import requests
from typing import Dict, List, Optional
from ..models.trade import MarketDirection
from ..config.settings import GAMMA_API_BASE, CLOB_API_BASE, DATA_API_BASE
import json


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

    def get_crypto_markets(self) -> List[Dict]:
    """
    Get all markets related to cryptocurrency
    :return: List of crypto-related market dictionaries
    """
    # First get all markets
    all_markets = self.get_markets(limit=1000)

    crypto_markets = []
    for market in all_markets:
        # Polymarket API uses 'question' instead of 'title'
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        category = market.get('category', '').lower()

        # Check if the market is in a crypto-related category (highest priority)
        is_crypto_category = any(cat in category for cat in ['crypto', 'defi', 'bitcoin', 'ethereum', 'altcoins'])

        if is_crypto_category:
            crypto_markets.append(market)
            continue

        # For non-crypto categories, use word boundary matching to avoid partial matches

        # Check for crypto asset names with specific financial context
        crypto_assets = [
            'bitcoin', 'ethereum', 'btc', 'eth', 'solana', 'sol', 'cardano', 'ada',
            'ripple', 'xrp', 'dogecoin', 'doge', 'polkadot', 'dot', 'litecoin', 'ltc',
            'bitcoin cash', 'bch', 'bnb', 'binance coin', 'chainlink', 'link',
            'polygon', 'matic', 'shiba', 'shib', 'tron', 'trx', 'monero', 'xmr',
            'stellar', 'xlm', 'vechain', 'vnx', 'zcash', 'zec', 'algorand', 'algo'
        ]

        # Check if any crypto asset is mentioned with financial/trading terms
        has_crypto_financial_context = False
        for asset in crypto_assets:
            # Use word boundaries to avoid partial matches (e.g., "coronavirus" shouldn't match "coin")
            asset_pattern = r'\b' + re.escape(asset) + r'\b'
            if re.search(asset_pattern, question) or re.search(asset_pattern, description):
                # Look for financial/trading related terms
                financial_terms = [
                    'price', 'value', 'trade', 'trading', 'market', 'cap', 'capitalization',
                    'worth', 'cost', 'buy', 'sell', 'invest', 'investment',
                    'profit', 'loss', 'gain', 'return', 'performance', 'rate', 'yield',
                    'usd', 'dollar', 'euro', 'pound', 'yen', 'currency', 'money',
                    'financial', 'economic', 'valuation',
                    'will reach', 'will hit', 'target', 'goal', 'above', 'below', 'at',
                    'goes to', 'hits', 'reaches', 'exceeds', 'falls below', 'surpasses'
                ]

                combined_text = question + " " + description
                if any(fin_term in combined_text for fin_term in financial_terms):
                    has_crypto_financial_context = True
                    break

        # Also check for specific crypto exchanges or platforms with word boundaries
        crypto_exchanges = ['coinbase', 'binance', 'kraken', 'ftx', 'huobi', 'kucoin', 'gate.io']
        has_crypto_exchange = False
        for exchange in crypto_exchanges:
            exchange_pattern = r'\b' + re.escape(exchange) + r'\b'
            if re.search(exchange_pattern, question) or re.search(exchange_pattern, description):
                has_crypto_exchange = True
                break

        # Check for DeFi/Blockchain specific terms with more precision
        defi_blockchain_terms = [
            'defi', 'decentralized finance', 'blockchain', 'nft', 'web3', 'smart contract',
            'tokenomics', 'staking', 'yield farming', 'liquidity', 'dex', 'amm',
            'lp token', 'governance', 'dao', 'erc-20', 'erc-721',
            'layer 2', 'scaling', 'gas fee', 'transaction fee', 'mining',
            'proof of stake', 'proof of work', 'validator', 'node', 'wallet'
        ]
        has_defi_blockchain = False
        combined_text = question + " " + description
        for term in defi_blockchain_terms:
            term_pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(term_pattern, combined_text):
                has_defi_blockchain = True
                break

        # Include market if it matches the criteria
        if has_crypto_financial_context or has_crypto_exchange or has_defi_blockchain:
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