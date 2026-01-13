#!/usr/bin/env python3
"""
CoinGecko API Key Setup Script

This script helps you set up a free CoinGecko API key for the app.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_api_key():
    """Interactive setup for CoinGecko API key"""

    print("=" * 70)
    print("COINGECKO API KEY SETUP")
    print("=" * 70)
    print()

    print("This will help you set up a free CoinGecko API key.")
    print("The API key is needed to avoid rate limiting errors.")
    print()

    # Check if API key already exists
    existing_key = os.getenv('COINGECKO_API_KEY', '')

    if existing_key:
        print(f"✓ Found existing API key: {existing_key[:10]}...{existing_key[-4:]}")
        print()
        change = input("Do you want to change it? (y/n): ").strip().lower()
        if change != 'y':
            print("Keeping existing API key.")
            return

    print()
    print("STEPS TO GET FREE API KEY:")
    print("-" * 70)
    print("1. Go to: https://www.coingecko.com/en/api")
    print("2. Click the 'Get API Key' button (top of page)")
    print("3. Sign up for a FREE account")
    print("4. Click 'API Keys' in the left menu")
    print("5. Click 'Add New Key'")
    print("6. Give it a name (e.g., 'Polymarket Trader')")
    print("7. Select 'Free' plan")
    print("8. Click 'Create'")
    print("9. Copy your API key")
    print("-" * 70)
    print()

    # Get API key from user
    while True:
        api_key = input("Paste your CoinGecko API key: ").strip()

        if not api_key:
            print("✗ API key cannot be empty. Please try again.")
            continue

        # Basic validation (CoinGecko keys are ~32 alphanumeric chars)
        if len(api_key) < 10:
            print("✗ API key seems too short. Please check and try again.")
            continue

        if ' ' in api_key:
            print("✗ API key should not contain spaces. Please try again.")
            continue

        break

    print()
    print("=" * 70)

    # Save to .env file
    env_file = os.path.join(os.path.dirname(__file__), '.env')

    # Check if .env exists and has existing content
    existing_env = ""
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            existing_env = f.read()

    # Update or add COINGECKO_API_KEY
    lines = existing_env.split('\n') if existing_env else []
    updated = False

    for i, line in enumerate(lines):
        if line.startswith('COINGECKO_API_KEY='):
            lines[i] = f'COINGECKO_API_KEY={api_key}'
            updated = True
            break

    if not updated:
        lines.append(f'COINGECKO_API_KEY={api_key}')

    # Write to .env
    with open(env_file, 'w') as f:
        f.write('\n'.join(lines))

    print("✓ API key saved to .env file")
    print(f"  File: {env_file}")
    print()

    # Also set environment variable for current session
    os.environ['COINGECKO_API_KEY'] = api_key
    print("✓ API key set for current session")
    print()

    print("=" * 70)
    print("✅ SETUP COMPLETE")
    print("=" * 70)
    print()
    print("Your CoinGecko API key is now configured.")
    print()
    print("To start using it:")
    print()
    print("  Option 1: Run this script again")
    print("    python setup_api_key.py")
    print()
    print("  Option 2: Load .env file")
    print("    export $(cat .env | xargs)")
    print("    python main.py --start-monitoring")
    print()
    print("  Option 3: Set in each command")
    print("    COINGECKO_API_KEY=your_key python main.py --start-monitoring")
    print()
    print("=" * 70)
    print("BENEFITS OF API KEY:")
    print("=" * 70)
    print("  ✅ Higher rate limits (30-50 calls/minute)")
    print("  ✅ No 429 errors (within limits)")
    print("  ✅ Analyze 5+ markets per cycle (not just 2)")
    print("  ✅ Faster API response times")
    print("  ✅ Better reliability")
    print()

def test_api_key():
    """Test if the API key works"""
    api_key = os.getenv('COINGECKO_API_KEY', '')

    if not api_key:
        print("✗ No API key found in environment")
        print("  Please run: python setup_api_key.py")
        return False

    try:
        import requests
        from poly_market_trader.api.chainlink_data_provider import ChainlinkDataProvider

        print("Testing CoinGecko API key...")
        print(f"  Key: {api_key[:10]}...{api_key[-4:]}")
        print()

        # Test with Pro API
        provider = ChainlinkDataProvider()

        # Try to fetch Bitcoin price
        price = provider.get_current_price('bitcoin')

        if price:
            print(f"✓ API key works!")
            print(f"  Bitcoin price: ${price:.2f}")
            print()
            print("=" * 70)
            print("✅ API KEY TEST PASSED")
            print("=" * 70)
            return True
        else:
            print("✗ Could not fetch price (API key may be invalid)")
            return False

    except Exception as e:
        print(f"✗ Error testing API key: {e}")
        return False

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Setup or test CoinGecko API key')
    parser.add_argument('--setup', action='store_true',
                        help='Interactive setup for CoinGecko API key')
    parser.add_argument('--test', action='store_true',
                        help='Test if API key is working')
    parser.add_argument('--key', type=str,
                        help='API key to set directly')

    args = parser.parse_args()

    if args.key:
        # Set API key directly from command line
        os.environ['COINGECKO_API_KEY'] = args.key
        print(f"API key set for current session: {args.key[:10]}...{args.key[-4:]}")
    elif args.setup:
        setup_api_key()
    elif args.test:
        test_api_key()
    else:
        # Default: show menu
        print("CoinGecko API Key Setup")
        print()
        print("Usage:")
        print("  python setup_api_key.py --setup    # Interactive setup")
        print("  python setup_api_key.py --test     # Test API key")
        print("  python setup_api_key.py --key XXX  # Set API key directly")
        print()
        print("Recommended: Start with setup to configure your key")
        print()
