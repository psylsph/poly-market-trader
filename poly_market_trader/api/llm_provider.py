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
        #self.default_model = LLMModel.NANO.value # Default to nano model for faster responses
        self.default_model = LLMModel.REASONING.value

        
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

            raw_content = response.choices[0].message.content
            logger.debug(f"Raw LLM response (type: {type(raw_content)}, repr: {repr(raw_content)})")

            if raw_content is None:
                logger.error("LLM returned None content")
                return self._get_default_response("None content from LLM")

            content = raw_content
            if not content:
                logger.error("LLM returned empty content")
                return self._get_default_response("Empty content from LLM")

            # Strip whitespace and check for empty content
            content = content.strip()
            if not content:
                logger.error("LLM returned only whitespace")
                return self._get_default_response("Only whitespace from LLM")

            # Check if content starts with valid JSON characters
            if not content.startswith(('{', '[', '"', 't', 'f', 'n', '-', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
                logger.warning(f"LLM response doesn't start with valid JSON token. First 100 chars: {repr(content[:100])}")

                # Special handling for markdown-wrapped JSON
                if content.strip().startswith('```'):
                    import re
                    # Try to extract JSON from markdown code blocks immediately
                    markdown_match = re.search(r'```(?:json)?\s*\n?(\{[\s\S]*?\})\s*\n?```', content, re.DOTALL)
                    if markdown_match:
                        try:
                            json_str = markdown_match.group(1)
                            data = json.loads(json_str)
                            logger.info("Successfully parsed JSON from markdown code block")
                            return data
                        except json.JSONDecodeError as e:
                            logger.debug(f"Markdown JSON parsing failed: {e}")

                # Try multiple strategies to extract JSON from explanatory text

                import re

                # Strategy 1: Look for properly formatted JSON objects with balanced braces
                json_candidates = []

                # Find all potential JSON object starts
                brace_positions = []
                for i, char in enumerate(content):
                    if char == '{':
                        brace_positions.append(i)

                # Try each potential JSON start position
                for start_pos in brace_positions:
                    # Use brace counting to find matching end brace
                    brace_count = 0
                    end_pos = -1

                    for i in range(start_pos, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i
                                break

                    if end_pos > start_pos:
                        candidate = content[start_pos:end_pos + 1]
                        json_candidates.append(candidate)

                # Try parsing each candidate, starting with the longest/most complete ones
                json_candidates.sort(key=len, reverse=True)
                for candidate in json_candidates:
                    try:
                        data = json.loads(candidate)
                        logger.info(f"Successfully extracted JSON using brace counting: {len(candidate)} chars")
                        return data
                    except json.JSONDecodeError:
                        continue

                # Strategy 2: Look for JSON in code blocks or after keywords
                patterns = [
                    r'```(?:json)?\s*\n?(\{[\s\S]*?\})\s*\n?```',  # Multiline JSON in code blocks
                    r'```json\s*(\{.*?\})\s*```',
                    r'```\s*(\{.*?\})\s*```',
                    r'JSON:\s*(\{.*?\})',
                    r'Response:\s*(\{.*?\})',
                    r'Output:\s*(\{.*?\})',
                    r'(\{[\s\S]*?\})',  # Last resort - multiline brace-enclosed content
                ]

                for pattern in patterns:
                    matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                    for match in matches:
                        try:
                            data = json.loads(match)
                            logger.info(f"Successfully extracted JSON using pattern: {pattern}")
                            return data
                        except json.JSONDecodeError:
                            continue

                # Strategy 3: Try to construct response from keywords in text
                constructed_response = self._construct_response_from_text(content)
                if constructed_response:
                    logger.info("Constructed response from text analysis")
                    return constructed_response

            logger.debug(f"LLM Response (length: {len(content)}): {content[:500]}{'...' if len(content) > 500 else ''}")

            # Parse JSON with multiple fallback strategies
            try:
                data = json.loads(content)
                return data
            except json.JSONDecodeError as e:
                logger.warning(f"Initial JSON parse failed: {e}. Attempting cleanup...")
                logger.debug(f"Raw LLM response: {content}")

                # Fallback 0: Check if content starts with non-JSON and find JSON later
                if not content.startswith(('{', '[')):
                    # Look for JSON object/array anywhere in the content
                    json_start = content.find('{')
                    if json_start == -1:
                        json_start = content.find('[')

                    if json_start != -1 and json_start > 0:
                        # Try parsing from the JSON start position
                        json_content = content[json_start:]
                        try:
                            data = json.loads(json_content)
                            logger.info("Successfully parsed JSON by finding start position")
                            return data
                        except json.JSONDecodeError:
                            pass  # Continue to other fallbacks

                # Fallback 1: Extract JSON from markdown code blocks
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    try:
                        json_str = json_match.group(1)
                        data = json.loads(json_str)
                        logger.info("Successfully parsed JSON from markdown code block")
                        return data
                    except json.JSONDecodeError as e2:
                        logger.debug(f"Markdown extraction failed: {e2}")

                # Fallback 2: Extract first complete JSON object by brace counting
                try:
                    brace_count = 0
                    start_idx = -1
                    in_string = False
                    escape_next = False

                    for i, char in enumerate(content):
                        if escape_next:
                            escape_next = False
                            continue

                        if char == '\\' and in_string:
                            escape_next = True
                            continue

                        if char == '"' and not escape_next:
                            in_string = not in_string
                            continue

                        if not in_string:
                            if char == '{':
                                if brace_count == 0:
                                    start_idx = i
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0 and start_idx != -1:
                                    json_candidate = content[start_idx:i+1]
                                    try:
                                        data = json.loads(json_candidate)
                                        logger.info("Successfully parsed first JSON object with brace counting")
                                        return data
                                    except json.JSONDecodeError:
                                        logger.debug(f"Brace counting candidate failed: {json_candidate[:100]}...")
                                        continue
                except Exception as e3:
                    logger.debug(f"Brace counting failed: {e3}")

                # Fallback 3: Try to find any JSON-like structure and clean it
                try:
                    # Find potential JSON start/end
                    start_pos = content.find('{')
                    end_pos = content.rfind('}')

                    if start_pos != -1 and end_pos != -1 and end_pos > start_pos:
                        json_candidate = content[start_pos:end_pos+1]
                        # Try to fix common issues
                        json_candidate = json_candidate.replace('```', '').strip()
                        if json_candidate.startswith('json'):
                            json_candidate = json_candidate[4:].strip()

                        try:
                            data = json.loads(json_candidate)
                            logger.info("Successfully parsed JSON with position-based extraction")
                            return data
                        except json.JSONDecodeError as e4:
                            logger.debug(f"Position extraction failed: {e4}")

                except Exception as e5:
                    logger.debug(f"Position extraction failed: {e5}")

                # Final fallback: Return a default response
                logger.error(f"Failed to parse JSON from LLM response after all attempts")
                logger.debug(f"Raw content (first 1000 chars): {content[:1000]}...")

                return self._get_default_response("Failed to parse JSON after all attempts")
                    
        except (APIError, APITimeoutError) as e:
            logger.error(f"LLM API Error: {e}")
            return self._get_default_response(f"API Error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in LLM analysis: {e}")
            return self._get_default_response(f"Unexpected error: {str(e)}")

    def check_connection(self) -> bool:
        """Verifies connection to LMStudio."""
        try:
            self.client.models.list()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to LMStudio: {e}")
            return False

    def _construct_response_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to construct a trading response from text analysis."""
        import re
        text_lower = text.lower()

        # Extract decision
        decision = "SKIP"
        if "yes" in text_lower and "no" not in text_lower:
            decision = "YES"
        elif "no" in text_lower and "yes" not in text_lower:
            decision = "NO"
        elif "both" in text_lower or ("yes" in text_lower and "no" in text_lower):
            decision = "BOTH"

        # Extract confidence (look for percentages or decimal numbers)
        confidence = 0.5  # Default moderate confidence
        confidence_patterns = [
            r'confidence[:\s]*([0-9.]+)',
            r'([0-9.]+)%',
            r'([0-9.]+)/10',
            r'([0-9.]+)/5'
        ]

        for pattern in confidence_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    value = float(match.group(1))
                    if '%' in match.group(0):
                        value = value / 100.0
                    elif '/10' in match.group(0):
                        value = value / 10.0
                    elif '/5' in match.group(0):
                        value = value / 5.0
                    confidence = min(1.0, max(0.0, value))
                    break
                except ValueError:
                    continue

        # Extract stake factor
        stake_factor = 0.5  # Default
        if confidence > 0.8:
            stake_factor = 1.0
        elif confidence > 0.6:
            stake_factor = 0.8
        elif confidence < 0.3:
            stake_factor = 0.2

        # Try to identify asset
        asset = "unknown"
        asset_keywords = {
            "bitcoin": "bitcoin", "btc": "bitcoin",
            "ethereum": "ethereum", "eth": "ethereum",
            "xrp": "xrp", "ripple": "xrp",
            "solana": "solana", "sol": "solana"
        }

        for keyword, asset_name in asset_keywords.items():
            if keyword in text_lower:
                asset = asset_name
                break

        reasoning = f"Extracted from text analysis: decision={decision}, confidence={confidence:.2f}"

        return {
            "asset": asset,
            "decision": decision,
            "confidence": confidence,
            "stake_factor": stake_factor,
            "reasoning": reasoning
        }

    def _get_default_response(self, reason: str) -> Dict[str, Any]:
        """Return a safe default response to prevent crashes."""
        logger.warning(f"Using default LLM response: {reason}")
        return {
            "asset": "unknown",
            "decision": "SKIP",
            "confidence": 0.0,
            "stake_factor": 0.0,
            "reasoning": f"LLM analysis failed: {reason}"
        }
