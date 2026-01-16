"""
NLP-based sentiment analysis for crypto news and social media.
Uses multiple sentiment analysis libraries for robust scoring.
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poly_market_trader.sentiment.sources.news_api import NewsArticle

# Optional imports for NLP libraries
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    HAS_VADER = True
except ImportError:
    HAS_VADER = False
    SentimentIntensityAnalyzer = None

try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False
    TextBlob = None

try:
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer as NLTKSentimentAnalyzer
    HAS_NLTK = True
except ImportError:
    HAS_NLTK = False
    NLTKSentimentAnalyzer = None


@dataclass
class SentimentResult:
    """Comprehensive sentiment analysis result"""
    compound_score: float  # -1 to 1 scale
    positive_score: float  # 0 to 1 scale
    negative_score: float  # 0 to 1 scale
    neutral_score: float   # 0 to 1 scale
    label: str            # 'positive', 'negative', 'neutral'
    confidence: float     # 0 to 1 confidence in classification
    sources: List[str]    # Which sentiment analyzers were used


class SentimentAnalyzer:
    """
    Multi-library sentiment analysis for crypto news and text.
    Combines Vader, TextBlob, and NLTK for robust sentiment scoring.
    """

    def __init__(self):
        """Initialize sentiment analyzers"""
        self.vader_analyzer = None
        self.nltk_analyzer = None

        if HAS_VADER:
            self.vader_analyzer = SentimentIntensityAnalyzer()
            # Add crypto-specific lexicon
            self._enhance_vader_lexicon()

        if HAS_NLTK:
            try:
                nltk.download('vader_lexicon', quiet=True)
                self.nltk_analyzer = NLTKSentimentAnalyzer()
            except:
                self.nltk_analyzer = None

    def _enhance_vader_lexicon(self):
        """Add crypto-specific words to Vader lexicon"""
        if not self.vader_analyzer:
            return

        # Crypto-positive words
        crypto_positive = {
            'bullish': 2.0, 'bull': 1.5, 'moon': 2.5, 'pump': 1.8,
            'surge': 2.0, 'rally': 1.8, 'breakthrough': 2.0,
            'adoption': 1.5, 'institutional': 1.5, 'mainstream': 1.5,
            'partnership': 1.8, 'integration': 1.5, 'upgrade': 1.5,
            'launch': 1.2, 'listing': 1.2, 'staking': 1.2
        }

        # Crypto-negative words
        crypto_negative = {
            'bearish': -2.0, 'bear': -1.5, 'dump': -1.8, 'crash': -2.5,
            'decline': -1.8, 'fall': -1.5, 'drop': -1.2, 'sell-off': -2.0,
            'hack': -2.5, 'exploit': -2.0, 'scam': -3.0, 'rug': -3.0,
            'liquidation': -2.0, 'bankruptcy': -2.5, 'lawsuit': -2.0,
            'regulation': -1.5, 'ban': -2.0, 'crackdown': -2.0
        }

        # Neutral/technical words (slight positive bias for innovation)
        crypto_neutral = {
            'blockchain': 0.3, 'defi': 0.2, 'nft': 0.1, 'web3': 0.2,
            'mining': 0.1, 'validator': 0.1, 'consensus': 0.1,
            'token': 0.0, 'coin': 0.0, 'crypto': 0.0
        }

        # Update lexicon
        self.vader_analyzer.lexicon.update(crypto_positive)
        self.vader_analyzer.lexicon.update(crypto_negative)
        self.vader_analyzer.lexicon.update(crypto_neutral)

    def analyze_text(self, text: str) -> SentimentResult:
        """
        Analyze sentiment of text using multiple libraries.

        Args:
            text: Text to analyze

        Returns:
            Comprehensive sentiment result
        """

        if not text or not text.strip():
            return SentimentResult(0.0, 0.0, 0.0, 1.0, 'neutral', 0.0, [])

        # Clean and preprocess text
        clean_text = self._preprocess_text(text)

        results = []
        sources = []

        # Vader analysis
        if HAS_VADER and self.vader_analyzer:
            vader_result = self.vader_analyzer.polarity_scores(clean_text)
            results.append({
                'compound': vader_result['compound'],
                'pos': vader_result['pos'],
                'neg': vader_result['neg'],
                'neu': vader_result['neu']
            })
            sources.append('vader')

        # TextBlob analysis
        if HAS_TEXTBLOB:
            blob = TextBlob(clean_text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity

            # Convert TextBlob polarity (-1 to 1) to Vader-like scores
            tb_result = {
                'compound': polarity,
                'pos': max(0, polarity) if polarity > 0 else 0,
                'neg': max(0, -polarity) if polarity < 0 else 0,
                'neu': 1 - abs(polarity)
            }
            results.append(tb_result)
            sources.append('textblob')

        # NLTK analysis (if available)
        if HAS_NLTK and self.nltk_analyzer:
            nltk_result = self.nltk_analyzer.polarity_scores(clean_text)
            results.append({
                'compound': nltk_result['compound'],
                'pos': nltk_result['pos'],
                'neg': nltk_result['neg'],
                'neu': nltk_result['neu']
            })
            sources.append('nltk')

        # Aggregate results
        if not results:
            # Fallback: simple keyword-based analysis
            return self._keyword_sentiment_analysis(clean_text)

        # Average the results
        avg_compound = sum(r['compound'] for r in results) / len(results)
        avg_pos = sum(r['pos'] for r in results) / len(results)
        avg_neg = sum(r['neg'] for r in results) / len(results)
        avg_neu = sum(r['neu'] for r in results) / len(results)

        # Determine label
        if avg_compound >= 0.05:
            label = 'positive'
        elif avg_compound <= -0.05:
            label = 'negative'
        else:
            label = 'neutral'

        # Calculate confidence based on agreement between analyzers
        if len(results) > 1:
            compounds = [r['compound'] for r in results]
            std_dev = np.std(compounds) if len(compounds) > 1 else 0
            confidence = max(0.1, 1.0 - std_dev)  # Lower std = higher confidence
        else:
            confidence = 0.5  # Single analyzer = medium confidence

        return SentimentResult(
            compound_score=avg_compound,
            positive_score=avg_pos,
            negative_score=avg_neg,
            neutral_score=avg_neu,
            label=label,
            confidence=confidence,
            sources=sources
        )

    def analyze_articles(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """
        Analyze sentiment for a list of news articles.

        Args:
            articles: List of news articles to analyze

        Returns:
            Articles with sentiment analysis added
        """

        analyzed_articles = []

        for article in articles:
            # Combine title and description for analysis
            text_to_analyze = f"{article.title} {article.description}"

            sentiment_result = self.analyze_text(text_to_analyze)

            # Update article with sentiment data
            article.sentiment_score = sentiment_result.compound_score
            article.sentiment_label = sentiment_result.label

            analyzed_articles.append(article)

        return analyzed_articles

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for better sentiment analysis"""

        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove URLs
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)

        # Remove special characters but keep some crypto symbols
        text = re.sub(r'[^\w\s\$#%&]', ' ', text)

        # Normalize whitespace
        text = ' '.join(text.split())

        # Remove common noise words in crypto context
        noise_words = ['breaking', 'news', 'update', 'alert', 'exclusive']
        for word in noise_words:
            text = text.replace(f' {word} ', ' ')

        return text.strip()

    def _keyword_sentiment_analysis(self, text: str) -> SentimentResult:
        """Fallback keyword-based sentiment analysis"""

        positive_words = [
            'bullish', 'surge', 'rally', 'breakthrough', 'adoption', 'partnership',
            'upgrade', 'launch', 'growth', 'success', 'profit', 'gain', 'rise',
            'bull', 'moon', 'pump', 'hodl', 'diamond', 'hands'
        ]

        negative_words = [
            'bearish', 'crash', 'dump', 'decline', 'fall', 'drop', 'hack', 'exploit',
            'scam', 'rug', 'liquidation', 'bankruptcy', 'lawsuit', 'ban', 'crackdown',
            'bear', 'sell', 'panic', 'fear', 'crash'
        ]

        words = text.lower().split()
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)

        total_sentiment_words = positive_count + negative_count

        if total_sentiment_words == 0:
            return SentimentResult(0.0, 0.0, 0.0, 1.0, 'neutral', 0.1, ['keyword'])

        # Calculate sentiment score
        sentiment_ratio = (positive_count - negative_count) / total_sentiment_words
        compound_score = max(-1.0, min(1.0, sentiment_ratio))

        # Determine label
        if compound_score > 0.1:
            label = 'positive'
        elif compound_score < -0.1:
            label = 'negative'
        else:
            label = 'neutral'

        return SentimentResult(
            compound_score=compound_score,
            positive_score=positive_count / max(len(words), 1),
            negative_score=negative_count / max(len(words), 1),
            neutral_score=1.0 - (positive_count + negative_count) / max(len(words), 1),
            label=label,
            confidence=0.3,  # Lower confidence for keyword analysis
            sources=['keyword']
        )

    def get_sentiment_summary(self, articles: List[NewsArticle]) -> Dict[str, Any]:
        """Get summary statistics about sentiment across articles"""

        if not articles:
            return {
                'total_articles': 0,
                'avg_sentiment': 0.0,
                'sentiment_distribution': {'positive': 0, 'neutral': 0, 'negative': 0},
                'sentiment_volatility': 0.0,
                'most_positive': None,
                'most_negative': None
            }

        sentiments = [article.sentiment_score for article in articles]
        labels = [article.sentiment_label for article in articles]

        # Basic statistics
        avg_sentiment = sum(sentiments) / len(sentiments)
        sentiment_volatility = np.std(sentiments) if len(sentiments) > 1 else 0

        # Distribution
        label_counts = {}
        for label in labels:
            label_counts[label] = label_counts.get(label, 0) + 1

        # Most extreme articles
        most_positive = max(articles, key=lambda x: x.sentiment_score) if sentiments else None
        most_negative = min(articles, key=lambda x: x.sentiment_score) if sentiments else None

        return {
            'total_articles': len(articles),
            'avg_sentiment': avg_sentiment,
            'sentiment_distribution': label_counts,
            'sentiment_volatility': sentiment_volatility,
            'most_positive': {
                'title': most_positive.title if most_positive else None,
                'sentiment': most_positive.sentiment_score if most_positive else None
            },
            'most_negative': {
                'title': most_negative.title if most_negative else None,
                'sentiment': most_negative.sentiment_score if most_negative else None
            }
        }


class CryptoSentimentScorer:
    """
    Specialized sentiment scoring for cryptocurrency context.
    Considers market-specific factors and terminology.
    """

    def __init__(self):
        """Initialize crypto-specific sentiment scorer"""
        self.sentiment_analyzer = SentimentAnalyzer()

        # Crypto-specific sentiment modifiers
        self.market_context_multipliers = {
            'fud': -0.3,      # Fear, Uncertainty, Doubt
            'ngmi': -0.2,     # Not Gonna Make It
            'wagmi': 0.2,     # We're All Gonna Make It
            'diamond': 0.4,   # Strong positive
            'moon': 0.5,      # Very strong positive
            'rekt': -0.4,     # Got liquidated/bad loss
            'ape': 0.1,       # Going all in (risky but positive intent)
        }

    def score_crypto_sentiment(self, text: str, market_context: Optional[Dict[str, Any]] = None) -> SentimentResult:
        """
        Score sentiment with crypto-specific context.

        Args:
            text: Text to analyze
            market_context: Additional market context (price changes, volume, etc.)

        Returns:
            Enhanced sentiment result
        """

        # Get base sentiment
        base_sentiment = self.sentiment_analyzer.analyze_text(text)

        # Apply crypto-specific modifiers
        modified_score = self._apply_crypto_modifiers(text, base_sentiment.compound_score)

        # Adjust based on market context if provided
        if market_context:
            modified_score = self._apply_market_context(modified_score, market_context)

        # Update label based on modified score
        if modified_score >= 0.05:
            label = 'positive'
        elif modified_score <= -0.05:
            label = 'negative'
        else:
            label = 'neutral'

        return SentimentResult(
            compound_score=modified_score,
            positive_score=base_sentiment.positive_score,
            negative_score=base_sentiment.negative_score,
            neutral_score=base_sentiment.neutral_score,
            label=label,
            confidence=base_sentiment.confidence,
            sources=base_sentiment.sources + ['crypto_modifiers']
        )

    def _apply_crypto_modifiers(self, text: str, base_score: float) -> float:
        """Apply crypto-specific sentiment modifiers"""

        text_lower = text.lower()
        modifier_sum = 0
        modifier_count = 0

        for term, modifier in self.market_context_multipliers.items():
            if term in text_lower:
                modifier_sum += modifier
                modifier_count += 1

        if modifier_count > 0:
            avg_modifier = modifier_sum / modifier_count
            # Apply modifier as a weighted adjustment
            modified_score = base_score * (1 + avg_modifier * 0.3)  # 30% influence
            return max(-1.0, min(1.0, modified_score))

        return base_score

    def _apply_market_context(self, sentiment_score: float, market_context: Dict[str, Any]) -> float:
        """Adjust sentiment based on market context"""

        # Price change context
        price_change_pct = market_context.get('price_change_pct', 0)
        volume_change_pct = market_context.get('volume_change_pct', 0)

        # If sentiment is positive but price is falling, moderate the score
        if sentiment_score > 0 and price_change_pct < -0.02:  # Price down 2%
            sentiment_score *= 0.8  # Reduce by 20%

        # If sentiment is negative but price is rising, moderate the score
        elif sentiment_score < 0 and price_change_pct > 0.02:  # Price up 2%
            sentiment_score *= 0.8  # Reduce negative impact

        # High volume can amplify sentiment
        if abs(volume_change_pct) > 0.5:  # 50% volume change
            sentiment_score *= 1.1  # Amplify by 10%

        return max(-1.0, min(1.0, sentiment_score))