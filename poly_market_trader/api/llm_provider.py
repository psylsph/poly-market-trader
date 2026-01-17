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
    recent_performance: Optional[Dict] = None  # New field for performance stats

class LLMProvider:
    """
    Provider for interacting with Local LLM via LMStudio.
    Handles model switching, retries, and JSON parsing.
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url or os.getenv('LLM_BASE_URL', settings.LLM_BASE_URL)
        self.api_key = api_key or os.getenv('LLM_API_KEY', settings.LLM_API_KEY)
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        # Try different models - some may be better at structured outputs
        # self.default_model = LLMModel.NANO.value
        # self.default_model = LLMModel.REASONING.value
        self.default_model = "mistralai/ministral-3-14b-reasoning"  # Try a different model that might be better at JSON

        
    def _get_system_prompt(self, context: MarketContext) -> str:
        """Constructs the system prompt with market context."""
        tags_str = ', '.join(context.tags) if context.tags else 'None'
        tech_str = json.dumps(context.technicals, indent=2) if context.technicals else 'None'
        
        perf_context = ""
        if context.recent_performance:
            losses = context.recent_performance.get('consecutive_losses', 0)
            if losses > 0:
                last_outcome = context.recent_performance.get('last_outcome')
                actual = context.recent_performance.get('last_actual')
                perf_context = f"\nWARNING: You have LOST the last {losses} bets on this asset. Last bet: {last_outcome}, Result: {actual}. BE EXTRA CAUTIOUS."
            elif context.recent_performance.get('win_rate', 0) < 0.4 and context.recent_performance.get('losses', 0) > 2:
                perf_context = f"\nWARNING: Low win rate ({context.recent_performance.get('win_rate', 0):.2%}) on this asset. Review past errors."

        prompt = """{question}
Prices: YES=${yes_price:.2f}, NO=${no_price:.2f}
{perf_context}

Analyze the technical indicators: {technicals}

Based on the question and technicals, decide YES, NO, or SKIP.
Return ONLY a JSON object with these exact fields:
- asset: the cryptocurrency name from the question
- decision: "YES", "NO", or "SKIP"
- confidence: number 0.0 to 1.0
- stake_factor: number 0.0 to 1.5
- reasoning: brief explanation

Example: {{"asset": "Bitcoin", "decision": "YES", "confidence": 0.8, "stake_factor": 1.0, "reasoning": "Strong uptrend"}}""".format(
            question=context.question,
            yes_price=context.yes_price,
            no_price=context.no_price,
            perf_context=perf_context,
            technicals=tech_str
        )
        return prompt

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
            logger.info(f"Sending market analysis request to LLM ({target_model}) - expecting pure JSON response...")

            response = self.client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt(context)},
                    {"role": "user", "content": "Extract the structured data for this market."}
                ],
                temperature=0.4,  # Higher temperature to encourage confidence variation
                stream=False,     # Disable streaming to ensure complete responses
                max_tokens=500,   # Limit response length to prevent truncation
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

            # Check for </think> tag pattern - content after this tag should be the actual response
            think_end_tag = "</think>"
            if think_end_tag in content:
                think_end_pos = content.find(think_end_tag) + len(think_end_tag)
                json_content = content[think_end_pos:].strip()

                if json_content:
                    logger.info(f"Found </think> tag, using content after it: {repr(json_content[:100])}")
                    # Try to parse the content after </think>
                    try:
                        data = json.loads(json_content)
                        logger.info("Successfully parsed JSON after </think> tag")
                        return data
                    except json.JSONDecodeError:
                        logger.debug(f"Direct parse after </think> failed, trying extraction")

                        # If direct parse fails, try aggressive extraction on the post-think content
                        json_content = json_content

            # AGGRESSIVE JSON EXTRACTION: If response doesn't start with JSON, find JSON anywhere in it
            if not content.startswith(('{', '[', '"', 't', 'f', 'n', '-', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
                # It's common for LLMs to wrap JSON in markdown or add text, so this is an INFO level event, not a warning
                logger.info(f"LLM response doesn't start with valid JSON token (likely markdown/text). extracting...")
                logger.debug(f"First 100 chars: {repr(content[:100])}")

                # STRATEGY 1: Find ALL potential JSON objects and try them
                json_candidates = []
                i = 0
                while i < len(content):
                    if content[i] == '{':
                        # Found potential JSON start
                        brace_count = 0
                        start_pos = i
                        for j in range(i, len(content)):
                            if content[j] == '{':
                                brace_count += 1
                            elif content[j] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    # Found complete JSON object
                                    json_candidate = content[start_pos:j+1]
                                    json_candidates.append(json_candidate)
                                    i = j + 1
                                    break
                        else:
                            i += 1
                    else:
                        i += 1

                # Try parsing each candidate, starting with the longest (most complete)
                json_candidates.sort(key=len, reverse=True)
                for candidate in json_candidates:
                    try:
                        data = json.loads(candidate)
                        logger.info(f"Successfully extracted JSON from response (length: {len(candidate)})")
                        return data
                    except json.JSONDecodeError:
                        continue

                # STRATEGY 2: Handle incomplete JSON (missing closing braces)
                if json_candidates:
                    # Try the longest incomplete candidate and add missing braces
                    longest_candidate = max(json_candidates, key=len)
                    missing_braces = longest_candidate.count('{') - longest_candidate.count('}')
                    if missing_braces > 0:
                        completed_candidate = longest_candidate + '}' * missing_braces
                        try:
                            data = json.loads(completed_candidate)
                            logger.info(f"Successfully parsed JSON by adding {missing_braces} missing braces")
                            return data
                        except json.JSONDecodeError:
                            pass

                # STRATEGY 3: Try to extract from markdown code blocks
                import re
                markdown_patterns = [
                    r'```(?:json)?\s*\n?(\{[\s\S]*?)\n?```',  # Complete markdown blocks
                    r'```(?:json)?\s*\n?(\{[\s\S]*)',  # Incomplete markdown blocks
                ]

                for pattern in markdown_patterns:
                    matches = re.findall(pattern, content, re.DOTALL)
                    for match in matches:
                        # Try direct parsing
                        try:
                            data = json.loads(match)
                            logger.info("Successfully parsed JSON from markdown block")
                            return data
                        except json.JSONDecodeError:
                            # Try completing incomplete JSON
                            completed_match = self._complete_incomplete_json(match)
                            if completed_match:
                                try:
                                    data = json.loads(completed_match)
                                    logger.info("Successfully parsed completed markdown JSON")
                                    return data
                                except json.JSONDecodeError:
                                    continue

                logger.error("Could not extract any valid JSON from LLM response")
                return self._get_default_response("No valid JSON found in LLM response")

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

            # AGGRESSIVE CHECK: Reject responses that contain thinking/chain-of-thought text
            thinking_indicators = [
                "we need to output", "must follow", "json with fields",
                "your response must be", "return only json",
                "let me analyze", "i think", "the analysis shows",
                "based on", "therefore", "so ", "thus",
                "first", "second", "finally", "in conclusion",
                "step", "approach", "method", "strategy"
            ]

            content_lower = content.strip().lower()
            if any(indicator in content_lower for indicator in thinking_indicators):
                logger.warning(f"LLM returned thinking/chain-of-thought text: {repr(content[:300])}")

                # Try to extract JSON from the response by finding the last { that leads to valid JSON
                last_brace_pos = content.rfind('{')
                if last_brace_pos >= 0:
                    potential_json = content[last_brace_pos:]
                    try:
                        data = json.loads(potential_json)
                        logger.info("Successfully extracted JSON from thinking response")
                        return data
                    except json.JSONDecodeError:
                        pass

                return self._get_default_response("LLM returned thinking text instead of JSON")

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

    def _complete_incomplete_json(self, json_str: str) -> Optional[str]:
        """Try to complete incomplete JSON by adding missing elements."""
        import re
        original_str = json_str
        json_str = json_str.strip()

        # If it ends with a complete object, add missing fields if needed
        if json_str.endswith('}'):
            try:
                data = json.loads(json_str)
                # Check for missing required fields
                required_fields = ['asset', 'decision', 'confidence', 'stake_factor', 'reasoning']
                missing_fields = [field for field in required_fields if field not in data]

                if missing_fields:
                    # Add missing fields with defaults
                    for field in missing_fields:
                        if field == 'asset':
                            data[field] = 'unknown'
                        elif field == 'decision':
                            data[field] = 'SKIP'
                        elif field == 'confidence':
                            data[field] = 0.5
                        elif field == 'stake_factor':
                            data[field] = 0.5
                        elif field == 'reasoning':
                            data[field] = 'JSON was incomplete'

                    # Re-serialize
                    json_str = json.dumps(data, indent=2)
                return json_str
            except json.JSONDecodeError:
                pass  # Continue with completion logic

        # Check for truncated string values (unclosed quotes)
        # Count effective quotes (escaped quotes count as one)
        open_quotes = json_str.count('"') - json_str.count('\\"')
        if open_quotes % 2 == 1:  # Odd number means unclosed quote
            logger.debug("Detected unclosed string quote, attempting to close it")
            # Find the last quote and add closing quote and completion
            last_quote_pos = json_str.rfind('"')
            if last_quote_pos >= 0:
                # Check what comes after the last quote
                after_quote = json_str[last_quote_pos + 1:].strip()
                if not after_quote or after_quote.startswith(','):
                    # Unclosed field value - close it and add reasoning
                    json_str = json_str + '", "reasoning": "JSON was truncated"}'
                else:
                    # Might be unclosed field name - complete differently
                    json_str = json_str + '": "unknown", "reasoning": "JSON was truncated"}'

        # Fix trailing commas before closing braces
        json_str = re.sub(r',(\s*})', r'\1', json_str)

        # Add missing closing braces
        missing_braces = json_str.count('{') - json_str.count('}')
        if missing_braces > 0:
            json_str = json_str + '}' * missing_braces

        # Try to parse and add missing fields
        try:
            data = json.loads(json_str)
            # Check for missing required fields
            required_fields = ['asset', 'decision', 'confidence', 'stake_factor', 'reasoning']
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                # Add missing fields with defaults
                for field in missing_fields:
                    if field == 'asset':
                        data[field] = 'unknown'
                    elif field == 'decision':
                        data[field] = 'SKIP'
                    elif field == 'confidence':
                        data[field] = 0.5
                    elif field == 'stake_factor':
                        data[field] = 0.5
                    elif field == 'reasoning':
                        data[field] = 'JSON was incomplete'

                # Re-serialize
                json_str = json.dumps(data, indent=2)

        except json.JSONDecodeError as e:
            logger.debug(f"JSON completion parsing failed: {e}, trying advanced completion")

            # Advanced completion: handle specific truncation patterns from logs
            original_json = json_str  # Save original for debugging
            try:

                # Pattern 1: Ends with incomplete "reas" (reasoning field)
                if json_str.strip().endswith('"reas'):
                    json_str = json_str + 'oning": "JSON was truncated"}'

                # Pattern 2: Ends with comma after complete field (like "stake_factor": 1.2, )
                elif json_str.strip().endswith(','):
                    json_str = json_str[:-1] + ', "reasoning": "JSON was truncated"}'

                # Pattern 3: Ends with quote in field position (like after "stake_factor": 1.2, ")
                elif json_str.strip().endswith('"') and not json_str.endswith('"}'):
                    # Check if it's after a field value or field name
                    last_colon = json_str.rfind(':')
                    if last_colon > 0:
                        # It's after a field value, add reasoning
                        json_str = json_str + ': "unknown", "reasoning": "JSON was truncated"}'
                    else:
                        # It's a field name, complete it
                        json_str = json_str + ': "unknown", "reasoning": "JSON was truncated"}'

                # Pattern 4: Missing closing brace but has complete fields
                elif json_str.count('{') > json_str.count('}'):
                    # Check if it has all required fields before adding reasoning
                    try:
                        temp_data = json.loads(json_str + '}')
                        required_fields = ['asset', 'decision', 'confidence', 'stake_factor']
                        has_required = all(field in temp_data for field in required_fields)
                        if has_required and 'reasoning' not in temp_data:
                            json_str = json_str + ', "reasoning": "JSON was truncated"}'
                        else:
                            json_str = json_str + '}'
                    except:
                        json_str = json_str + ', "reasoning": "JSON was truncated"}'

                # Try parsing the completed JSON
                data = json.loads(json_str)
                required_fields = ['asset', 'decision', 'confidence', 'stake_factor', 'reasoning']
                missing_fields = [field for field in required_fields if field not in data]

                if missing_fields:
                    for field in missing_fields:
                        if field == 'reasoning':
                            data[field] = 'JSON was truncated'
                    json_str = json.dumps(data, indent=2)

            except json.JSONDecodeError as e2:
                logger.debug(f"Advanced completion failed: {e2}, original: {repr(original_json)}")
                # Last resort: create a minimal valid JSON
                json_str = '{"asset": "unknown", "decision": "SKIP", "confidence": 0.0, "stake_factor": 0.0, "reasoning": "Parsing failed"}'

        return json_str

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
