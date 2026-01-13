    def get_crypto_markets(self) -> List[Dict]:
        """
        Get all markets related to cryptocurrency
        :return: List of crypto-related market dictionaries
        """
        import re  # Import at the beginning of the function
        
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