"""
News API integration for crypto sentiment analysis.
Fetches and processes cryptocurrency news from various sources.
"""

import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import os
import sys
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class NewsArticle:
    """Represents a news article with sentiment analysis"""
    title: str
    description: str
    content: str
    url: str
    source: str
    published_at: datetime
    sentiment_score: float = 0.0
    sentiment_label: str = 'neutral'
    relevance_score: float = 0.0
    crypto_mentions: List[str] = None

    def __post_init__(self):
        if self.crypto_mentions is None:
            self.crypto_mentions = []


class NewsAPIClient:
    """
    Client for fetching cryptocurrency news from NewsAPI.
    Provides filtering and processing for crypto-specific content.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize NewsAPI client.

        Args:
            api_key: NewsAPI key (can be set via NEWSAPI_KEY env var)
        """
        self.api_key = api_key or os.getenv('NEWSAPI_KEY', '')
        self.base_url = 'https://newsapi.org/v2'

        # Crypto-specific keywords for filtering
        self.crypto_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
            'solana', 'sol', 'ripple', 'xrp', 'cardano', 'ada', 'polygon', 'matic',
            'chainlink', 'link', 'uniswap', 'uni', 'avalanche', 'avax', 'polkadot', 'dot',
            'binance', 'coinbase', 'crypto exchange', 'defi', 'nft', 'web3', 'blockchain'
        ]

        # Source credibility scores (higher = more credible)
        self.source_credibility = {
            'coindesk': 0.9, 'cointelegraph': 0.85, 'cryptonews': 0.8,
            'decrypt': 0.85, 'the-block': 0.9, 'bloomberg': 0.95,
            'reuters': 0.95, 'cnbc': 0.9, 'wsj': 0.95, 'ft': 0.95,
            'yahoo-finance': 0.8, 'marketwatch': 0.85
        }

    def fetch_crypto_news(self,
                          hours_back: int = 24,
                          limit: int = 100,
                          language: str = 'en') -> List[NewsArticle]:
        """
        Fetch cryptocurrency news from the last N hours.

        Args:
            hours_back: Number of hours to look back
            limit: Maximum number of articles to return
            language: Language filter ('en', 'all', etc.)

        Returns:
            List of processed news articles
        """

        if not self.api_key:
            print("Warning: No NewsAPI key provided, returning empty results")
            return []

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours_back)

        # Build query with crypto keywords
        query = ' OR '.join(f'"{keyword}"' for keyword in self.crypto_keywords[:5])  # Limit for API

        params = {
            'q': query,
            'from': start_date.strftime('%Y-%m-%dT%H:%M:%S'),
            'to': end_date.strftime('%Y-%m-%dT%H:%M:%S'),
            'sortBy': 'publishedAt',
            'language': language,
            'pageSize': min(limit, 100),  # NewsAPI limit
            'apiKey': self.api_key
        }

        try:
            response = requests.get(f"{self.base_url}/everything", params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            articles = []

            for item in data.get('articles', []):
                article = self._process_article(item)
                if article:
                    articles.append(article)

            return articles[:limit]

        except Exception as e:
            print(f"Error fetching news: {e}")
            return []

    def _process_article(self, raw_article: Dict[str, Any]) -> Optional[NewsArticle]:
        """Process raw article data into NewsArticle object"""

        try:
            # Extract basic info
            title = raw_article.get('title', '').strip()
            description = raw_article.get('description', '').strip()
            content = raw_article.get('content', '').strip()
            url = raw_article.get('url', '')
            source = raw_article.get('source', {}).get('name', 'unknown')

            # Parse publication date
            published_str = raw_article.get('publishedAt', '')
            try:
                published_at = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
            except:
                published_at = datetime.now()

            # Skip if missing essential data
            if not title or not url:
                return None

            # Calculate relevance score based on crypto mentions
            crypto_mentions = []
            text_to_check = f"{title} {description}".lower()

            for keyword in self.crypto_keywords:
                if keyword in text_to_check:
                    crypto_mentions.append(keyword)

            # Relevance score based on mentions and source credibility
            relevance_score = min(len(crypto_mentions) * 0.2, 1.0)
            credibility = self.source_credibility.get(source.lower(), 0.5)
            relevance_score = (relevance_score + credibility) / 2

            # Create article object (sentiment will be added later)
            article = NewsArticle(
                title=title,
                description=description,
                content=content,
                url=url,
                source=source,
                published_at=published_at,
                relevance_score=relevance_score,
                crypto_mentions=crypto_mentions
            )

            return article

        except Exception as e:
            print(f"Error processing article: {e}")
            return None

    def get_news_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get summary statistics about recent crypto news"""

        articles = self.fetch_crypto_news(hours_back=hours_back)

        if not articles:
            return {
                'total_articles': 0,
                'avg_sentiment': 0.0,
                'sentiment_distribution': {'positive': 0, 'neutral': 0, 'negative': 0},
                'top_sources': [],
                'crypto_mentions': {}
            }

        # Calculate sentiment distribution
        sentiment_dist = {'positive': 0, 'neutral': 0, 'negative': 0}
        for article in articles:
            if article.sentiment_label == 'positive':
                sentiment_dist['positive'] += 1
            elif article.sentiment_label == 'negative':
                sentiment_dist['negative'] += 1
            else:
                sentiment_dist['neutral'] += 1

        # Calculate average sentiment
        avg_sentiment = sum(article.sentiment_score for article in articles) / len(articles)

        # Top sources
        source_counts = {}
        for article in articles:
            source_counts[article.source] = source_counts.get(article.source, 0) + 1

        top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # Crypto mentions
        crypto_counts = {}
        for article in articles:
            for crypto in article.crypto_mentions:
                crypto_counts[crypto] = crypto_counts.get(crypto, 0) + 1

        return {
            'total_articles': len(articles),
            'avg_sentiment': avg_sentiment,
            'sentiment_distribution': sentiment_dist,
            'top_sources': top_sources,
            'crypto_mentions': crypto_counts,
            'time_range': f"{hours_back} hours"
        }


class CryptoPanicClient:
    """
    Alternative news source using CryptoPanic API (free tier available).
    Provides crypto-specific news with better filtering.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize CryptoPanic client.

        Args:
            api_key: CryptoPanic API key (optional, has free tier)
        """
        self.api_key = api_key or os.getenv('CRYPTOPANIC_API_KEY', '')
        self.base_url = 'https://cryptopanic.com/api/v1'

        # CryptoPanic has a free tier with rate limits
        self.free_tier = not bool(self.api_key)

    def fetch_posts(self,
                   hours_back: int = 24,
                   limit: int = 50,
                   currencies: Optional[List[str]] = None) -> List[NewsArticle]:
        """
        Fetch crypto posts from CryptoPanic.

        Args:
            hours_back: Hours to look back
            limit: Maximum posts to return
            currencies: Specific currencies to filter for

        Returns:
            List of processed news articles
        """

        params = {
            'auth_token': self.api_key,
            'limit': min(limit, 50),  # API limit
        }

        if currencies:
            # Map to CryptoPanic currency codes
            currency_map = {
                'bitcoin': 'BTC', 'btc': 'BTC',
                'ethereum': 'ETH', 'eth': 'ETH',
                'solana': 'SOL', 'sol': 'SOL',
                'ripple': 'XRP', 'xrp': 'XRP'
            }
            codes = [currency_map.get(c.lower(), c.upper()) for c in currencies if c.lower() in currency_map]
            if codes:
                params['currencies'] = ','.join(codes)

        try:
            response = requests.get(f"{self.base_url}/posts/", params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            articles = []

            for item in data.get('results', []):
                article = self._process_cryptopanic_post(item)
                if article:
                    articles.append(article)

            return articles

        except Exception as e:
            print(f"Error fetching CryptoPanic posts: {e}")
            return []

    def _process_cryptopanic_post(self, post: Dict[str, Any]) -> Optional[NewsArticle]:
        """Process CryptoPanic post into NewsArticle"""

        try:
            title = post.get('title', '').strip()
            content = post.get('body', '').strip()
            url = post.get('url', '')
            source = 'CryptoPanic'

            # Parse publication date
            published_str = post.get('published_at', '')
            try:
                published_at = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
            except:
                published_at = datetime.now()

            # Extract currencies mentioned
            currencies = post.get('currencies', [])
            crypto_mentions = [curr.get('code', '').lower() for curr in currencies]

            # Calculate relevance score
            relevance_score = min(len(crypto_mentions) * 0.3 + 0.7, 1.0)  # High relevance for CryptoPanic

            article = NewsArticle(
                title=title,
                description=content[:200] + '...' if len(content) > 200 else content,
                content=content,
                url=url,
                source=source,
                published_at=published_at,
                relevance_score=relevance_score,
                crypto_mentions=crypto_mentions
            )

            return article

        except Exception as e:
            print(f"Error processing CryptoPanic post: {e}")
            return None


# Fallback mock data for when APIs are unavailable
def get_mock_news_data() -> List[NewsArticle]:
    """Generate mock news data for testing when APIs are unavailable"""

    mock_articles = [
        NewsArticle(
            title="Bitcoin Surges Past $60,000 as Institutional Adoption Grows",
            description="Major financial institutions continue to add Bitcoin to their balance sheets...",
            content="Bitcoin has reached new all-time highs as institutional adoption accelerates...",
            url="https://example.com/bitcoin-surge",
            source="CryptoNews",
            published_at=datetime.now() - timedelta(hours=2),
            sentiment_score=0.8,
            sentiment_label='positive',
            relevance_score=0.9,
            crypto_mentions=['bitcoin', 'btc']
        ),
        NewsArticle(
            title="Ethereum Network Congestion Raises Gas Fees Concerns",
            description="Recent DeFi activity has caused significant network congestion...",
            content="Ethereum gas fees have spiked dramatically due to increased DeFi activity...",
            url="https://example.com/eth-congestion",
            source="DeFi Pulse",
            published_at=datetime.now() - timedelta(hours=4),
            sentiment_score=-0.3,
            sentiment_label='negative',
            relevance_score=0.8,
            crypto_mentions=['ethereum', 'eth', 'defi']
        ),
        NewsArticle(
            title="Solana Ecosystem Continues to Expand with New DeFi Protocols",
            description="Multiple new projects launching on Solana network...",
            content="The Solana ecosystem shows strong growth with new DeFi protocols...",
            url="https://example.com/solana-growth",
            source="Solana Labs",
            published_at=datetime.now() - timedelta(hours=6),
            sentiment_score=0.6,
            sentiment_label='positive',
            relevance_score=0.85,
            crypto_mentions=['solana', 'sol', 'defi']
        )
    ]

    return mock_articles