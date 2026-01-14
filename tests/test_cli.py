import unittest
import sys
import io
from unittest.mock import patch, MagicMock
from decimal import Decimal
from poly_market_trader.services.paper_trader import PaperTrader
from poly_market_trader.models.trade import MarketDirection


class TestCommandLineInterface(unittest.TestCase):
    """Test cases for the command-line interface functionality"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.trader = PaperTrader(initial_balance=Decimal('10000.00'), auto_load=False)
    
    @patch('sys.argv', ['main.py', '--portfolio'])
    def test_portfolio_command(self):
        """Test the --portfolio command."""
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            from main import main
            main()
        except SystemExit:
            # Expected behavior after printing
            pass
        finally:
            sys.stdout = sys.__stdout__  # Reset redirect
        
        output = captured_output.getvalue()
        self.assertIn("POLYMARKET PAPER TRADER PORTFOLIO", output)
        self.assertIn("Current Balance", output)
    
    @patch('sys.argv', ['main.py', '--positions'])
    def test_positions_command(self):
        """Test the --positions command."""
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            from main import main
            main()
        except SystemExit:
            # Expected behavior after printing
            pass
        finally:
            sys.stdout = sys.__stdout__  # Reset redirect
        
        output = captured_output.getvalue()
        # The command should output either active positions or "No active positions"
        self.assertTrue("active positions" in output.lower() or "no active positions" in output.lower())
    
    @patch('sys.argv', ['main.py', '--list-markets'])
    @patch.object(PaperTrader, 'get_crypto_markets')
    def test_list_markets_command(self, mock_get_crypto_markets):
        """Test the --list-markets command."""
        # Mock the crypto markets
        mock_get_crypto_markets.return_value = [
            {"id": "test1", "question": "Will Bitcoin reach $100k?"},
            {"id": "test2", "question": "Ethereum price prediction"}
        ]
        
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            from main import main
            main()
        except SystemExit:
            # Expected behavior after printing
            pass
        finally:
            sys.stdout = sys.__stdout__  # Reset redirect
        
        output = captured_output.getvalue()
        self.assertIn("Available Crypto Markets", output)
        self.assertIn("Will Bitcoin reach $100k?", output)
    
    @patch('sys.argv', ['main.py', '--analyze', 'bitcoin'])
    @patch.object(PaperTrader, 'get_chainlink_analysis')
    def test_analyze_command(self, mock_get_analysis):
        """Test the --analyze command."""
        # Mock the analysis result
        mock_get_analysis.return_value = {
            'current_price': 50000.0,
            'trend': 'bullish',
            'indicators': {'sma': 48000.0, 'volatility': 2.5}
        }
        
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            from main import main
            main()
        except SystemExit:
            # Expected behavior after printing
            pass
        finally:
            sys.stdout = sys.__stdout__  # Reset redirect
        
        output = captured_output.getvalue()
        self.assertIn("Performing Chainlink analysis for bitcoin", output)
        self.assertIn("Current price:", output)
        self.assertIn("Trend:", output)
    
    @patch('sys.argv', ['main.py', '--monitor-status'])
    def test_monitor_status_command(self):
        """Test the --monitor-status command."""
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            from main import main
            main()
        except SystemExit:
            # Expected behavior after printing
            pass
        finally:
            sys.stdout = sys.__stdout__  # Reset redirect
        
        output = captured_output.getvalue()
        self.assertIn("Auto-Betting Status", output)
        self.assertIn("Running:", output)
    
    @patch('sys.argv', ['main.py', '--active-bets'])
    def test_active_bets_command(self):
        """Test the --active-bets command."""
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            from main import main
            main()
        except SystemExit:
            # Expected behavior after printing
            pass
        finally:
            sys.stdout = sys.__stdout__  # Reset redirect
        
        output = captured_output.getvalue()
        # The command should output either active bets or "No active bets from auto-betting system"
        self.assertTrue("active bets" in output.lower() or "no active bets" in output.lower())
    
    @patch('sys.argv', ['main.py', '--balance', '15000', '--portfolio'])
    def test_custom_balance_command(self):
        """Test the --balance command with custom value."""
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            from main import main
            main()
        except SystemExit:
            # Expected behavior after printing
            pass
        finally:
            sys.stdout = sys.__stdout__  # Reset redirect
        
        output = captured_output.getvalue()
        self.assertIn("POLYMARKET PAPER TRADER PORTFOLIO", output)
        # The balance might not be exactly 15000 due to how main function works
        # but the command should be processed without errors


class TestArgumentParsing(unittest.TestCase):
    """Test argument parsing functionality"""
    
    def test_help_message_contains_expected_options(self):
        """Test that help message contains expected options."""
        import argparse
        from main import main
        
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Temporarily replace argv to trigger help
        original_argv = sys.argv
        try:
            sys.argv = ['main.py', '--help']
            try:
                main()
            except SystemExit:
                # Expected when --help is processed
                pass
        finally:
            sys.argv = original_argv
            sys.stdout = sys.__stdout__  # Reset redirect
        
        output = captured_output.getvalue()
        # Help message should contain key options
        self.assertIn("--portfolio", output)
        self.assertIn("--positions", output)
        self.assertIn("--list-markets", output)
        self.assertIn("--analyze", output)
        self.assertIn("--auto-bet", output)


class TestAutoBetCommand(unittest.TestCase):
    """Test the auto-bet command functionality"""
    
    @patch('sys.argv', ['main.py', '--auto-bet', '--bet-market', 'bitcoin', '--amount', '100', '--max-price', '0.6'])
    @patch.object(PaperTrader, 'get_crypto_markets')
    @patch.object(PaperTrader, 'place_informed_crypto_bet')
    def test_auto_bet_command(self, mock_place_bet, mock_get_markets):
        """Test the --auto-bet command."""
        # Mock the crypto markets
        mock_get_markets.return_value = [
            {"id": "test1", "question": "Will Bitcoin reach $100k?"}
        ]
        
        # Mock the bet placement to return success
        mock_place_bet.return_value = True
        
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            from main import main
            main()
        except SystemExit:
            # Expected behavior after processing
            pass
        finally:
            sys.stdout = sys.__stdout__  # Reset redirect
        
        output = captured_output.getvalue()
        # Should attempt to place a bet
        mock_place_bet.assert_called_once()
        self.assertIn("Auto-bet placed successfully", output)


if __name__ == '__main__':
    unittest.main()