import os
import json
import logging
from typing import Dict, Optional, Any
from enum import Enum
from openai import OpenAI, APIError, APITimeoutError
from dataclasses import dataclass
from ..config import settings

# Configure logging
logger = logging.getLogger(__name__)

class LLMModel(Enum):
    NANO = settings.LLM_MODEL_NANO
    REASONING = settings.LLM_MODEL_REASONING

@dataclass
class MarketContext:
    question: str
    description: str
    yes_price: float
    no_price: float
    volume: float = 0.0
    tags: Optional[list] = None
    technicals: Optional[Dict] = None
    balance: float = 0.0

class LLMProvider:
    """
    Provider for interacting with Local LLM via LMStudio.
    Handles model switching, retries, and JSON parsing.
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url or os.getenv('LLM_BASE_URL', settings.LLM_BASE_URL)
        self.api_key = api_key or os.getenv('LLM_API_KEY', settings.LLM_API_KEY)
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.default_model = LLMModel.NANO.value # Default to nano model for faster responses
        #self.default_model = LLMModel.REASONING.value

        
    def _get_system_prompt(self, context: MarketContext) -> str:
        """Constructs the system prompt with market context."""
        tags_str = ', '.join(context.tags) if context.tags else 'None'
        tech_str = json.dumps(context.technicals, indent=2) if context.technicals else 'None'
        
        return f"""You are an expert financial analyst for Polymarket, a crypto-based prediction market. 
Your goal is to extract structured data AND provide a trading recommendation based on technical and fundamental analysis.

POLYMARKET MECHANICS:
- Binary System: Users buy/sell shares of "Yes" or "No".
- Payouts: Correct shares redeem for $1.00. Incorrect shares are worth $0.00.
- Price as Probability: A price of $0.75 means the market assigns a 75% probability.
- Trading: This is a live market. You can sell before the event concludes to lock in profits if the price moves in your favor.

CONTEXT:
- Market Question: "{context.question}"
- Market Description: "{context.description}"
- Current Prices: YES=${context.yes_price:.2f}, NO=${context.no_price:.2f}
- Volume: ${context.volume:,.2f}
- Tags: {tags_str}
- Current Portfolio Balance: ${context.balance:,.2f}
- Technical Indicators (Chainlink):
{tech_str}

TASK:
Analyze the market and provide a JSON response with the following fields:
1. "asset": The primary asset (e.g., "Bitcoin").
2. "decision": Your trading recommendation ("YES", "NO", "BOTH", or "SKIP").
3. "confidence": A score from 0.0 to 1.0 indicating your conviction.
4. "stake_factor": A multiplier (0.0 to 1.5) for the standard bet size. Use 0.0 for SKIP.
5. "reasoning": A brief explanation of your decision, citing technicals or market sentiment.

STRATEGY GUIDELINES:
- **Arbitrage**: If (YES Price + NO Price) <= 0.99, this is free money. Decision MUST be "BOTH" and stake_factor 1.5.
- **Trend Strength (ADX)**: If ADX > 25, the trend is STRONG.
    - **Bullish Trend (Up) + ADX > 25**: BET WITH TREND (YES). Do NOT bet NO even if RSI > 70.
    - **Bearish Trend (Down) + ADX > 25**: BET WITH TREND (NO). Do NOT bet YES even if RSI < 30.
- **Mean Reversion**: ONLY valid if ADX < 25 (Weak Trend).
    - If ADX < 25 and RSI > 70 (Overbought) -> Bet NO.
    - If ADX < 25 and RSI < 30 (Oversold) -> Bet YES.
- **Bollinger Bands**:
    - Price > Upper Band: Overbought (bearish signal).
    - Price < Lower Band: Oversold (bullish signal).
- **Value**: If your confidence > market price, it's a value bet.
- **Stake Sizing**: Higher confidence = higher stake_factor. Max 1.5x for high conviction (>0.8).

CRITICAL INSTRUCTIONS:
- You must return ONLY valid JSON.
- Do not include markdown formatting like ```json ... ```.
"""

    def analyze_market(self, context: MarketContext, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Analyzes a market question using the LLM.
        
        Args:
            context: MarketContext object containing price, question, etc.
            model: Optional model override. Defaults to self.default_model.
            
        Returns:
            Dictionary containing the extracted JSON data, or None if failure.
        """
        target_model = model or self.default_model
        
        try:
            logger.info(f"Sending market analysis request to LLM ({target_model})...")
            
            response = self.client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt(context)},
                    {"role": "user", "content": "Extract the structured data for this market."}
                ],
                temperature=0.1, # Low temperature for deterministic output
            )
            
            content = response.choices[0].message.content
            if not content:
                logger.error("LLM returned empty content")
                return None
                
            logger.debug(f"LLM Response: {content}")
            
            # Parse JSON
            try:
                data = json.loads(content)
                return data
            except json.JSONDecodeError:
                # Fallback: Try to find JSON blob if wrapped in markdown
                import re
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                else:
                    logger.error(f"Failed to parse JSON from LLM response: {content}")
                    return None
                    
        except (APIError, APITimeoutError) as e:
            logger.error(f"LLM API Error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in LLM analysis: {e}")
            return None

    def check_connection(self) -> bool:
        """Verifies connection to LMStudio."""
        try:
            self.client.models.list()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to LMStudio: {e}")
            return False
