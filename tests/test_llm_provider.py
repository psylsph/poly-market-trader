import unittest
from unittest.mock import MagicMock, patch
from poly_market_trader.api.llm_provider import LLMProvider, MarketContext, LLMModel

class TestLLMProvider(unittest.TestCase):
    
    def setUp(self):
        self.provider = LLMProvider(base_url="http://mock-url:1234/v1")
        self.context = MarketContext(
            question="Will Bitcoin hit $100k by 2025?",
            description="Market resolution based on Binance spot price.",
            yes_price=0.45,
            no_price=0.55,
            volume=10000.0,
            tags=["Crypto", "Bitcoin"]
        )

    @patch('poly_market_trader.api.llm_provider.OpenAI')
    def test_analyze_market_success(self, mock_openai):
        # Mock successful response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"asset": "Bitcoin", "metric": "price", "target_value": 100000}'
        
        mock_client.chat.completions.create.return_value = mock_response
        self.provider.client = mock_client
        
        result = self.provider.analyze_market(self.context)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['asset'], "Bitcoin")
        self.assertEqual(result['target_value'], 100000)
        
        # Verify prompt contained pricing info
        call_args = mock_client.chat.completions.create.call_args
        system_prompt = call_args[1]['messages'][0]['content']
        self.assertIn("YES=$0.45", system_prompt)
        self.assertIn("NO=$0.55", system_prompt)

    @patch('poly_market_trader.api.llm_provider.OpenAI')
    def test_json_parsing_fallback(self, mock_openai):
        # Mock response with markdown wrapping
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '```json\n{"asset": "Ethereum"}\n```'
        
        mock_client.chat.completions.create.return_value = mock_response
        self.provider.client = mock_client
        
        result = self.provider.analyze_market(self.context)
        
        self.assertEqual(result['asset'], "Ethereum")

    @patch('poly_market_trader.api.llm_provider.OpenAI')
    def test_connection_check(self, mock_openai):
        mock_client = MagicMock()
        self.provider.client = mock_client
        
        self.assertTrue(self.provider.check_connection())
        mock_client.models.list.assert_called_once()

if __name__ == '__main__':
    unittest.main()
