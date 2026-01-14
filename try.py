#!/usr/bin/env python3
"""
Download active Polymarket 15-minute crypto bets
Uses Gamma API directly with requests library
"""

import requests
import json
from datetime import datetime

def fetch_events(limit=100, offset=0):
    """Fetch events from Gamma API"""
    url = "https://gamma-api.polymarket.com/events"
    
    params = {
        'active': 'true',
        'closed': 'false',
        'limit': limit,
        'offset': offset
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching events: {e}")
        return []

def fetch_all_events():
    """Fetch all active events with pagination"""
    all_events = []
    offset = 0
    limit = 100
    
    print("Fetching events from Polymarket Gamma API...")
    
    while True:
        events = fetch_events(limit=limit, offset=offset)
        
        if not events:
            break
        
        all_events.extend(events)
        print(f"Fetched {len(all_events)} events so far...")
        
        # If we got fewer than limit, we're at the end
        if len(events) < limit:
            break
        
        offset += limit
    
    return all_events

def is_15min_crypto(event):
    """Check if event is a 15-minute crypto market"""
    title = event.get('title', '').lower()
    description = event.get('description', '').lower()
    slug = event.get('slug', '').lower()
    
    # Check for crypto keywords
    crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol', 
                       'xrp', 'dogecoin', 'doge', 'crypto']
    has_crypto = any(kw in title or kw in slug for kw in crypto_keywords)
    
    # Check for 15-minute timeframe
    time_keywords = ['15 minute', '15-minute', '15 min', '15min', '15m']
    has_15min = any(kw in title or kw in slug or kw in description for kw in time_keywords)
    
    # Also check for "up or down" pattern common in 15min markets
    has_up_down = 'up or down' in title or 'higher or lower' in title
    
    return has_crypto and (has_15min or has_up_down)

def format_event(event):
    """Extract and format event information"""
    markets = event.get('markets', [])
    
    formatted = {
        'title': event.get('title'),
        'slug': event.get('slug'),
        'event_id': event.get('id'),
        'description': event.get('description', ''),
        'start_date': event.get('startDate'),
        'end_date': event.get('endDate'),
        'active': event.get('active'),
        'closed': event.get('closed'),
        'url': f"https://polymarket.com/event/{event.get('slug', '')}",
        'markets': []
    }
    
    for market in markets:
        outcomes = market.get('outcomes', [])
        outcome_prices = market.get('outcomePrices', [])
        
        # Parse outcomes and prices if they're strings
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except:
                pass
        
        if isinstance(outcome_prices, str):
            try:
                outcome_prices = json.loads(outcome_prices)
            except:
                pass
        
        market_info = {
            'question': market.get('question'),
            'condition_id': market.get('conditionId'),
            'outcomes': outcomes,
            'outcome_prices': outcome_prices,
            'volume': market.get('volume', '0'),
            'liquidity': market.get('liquidity', '0'),
            'tokens': market.get('tokens', []),
            'clob_token_ids': market.get('clobTokenIds', []),
            'enable_order_book': market.get('enableOrderBook', False)
        }
        formatted['markets'].append(market_info)
    
    return formatted

def main():
    # Fetch all active events
    all_events = fetch_all_events()
    print(f"\nTotal events fetched: {len(all_events)}")
    
    # Filter for 15-minute crypto markets
    crypto_15min = [e for e in all_events if is_15min_crypto(e)]
    print(f"15-minute crypto events found: {len(crypto_15min)}")
    
    # Filter for markets with volume > 0
    crypto_15min_with_volume = []
    for event in crypto_15min:
        markets = event.get('markets', [])
        has_volume = any(float(m.get('volume', 0)) > 0 for m in markets)
        if has_volume:
            crypto_15min_with_volume.append(event)
    
    crypto_15min = crypto_15min_with_volume
    print(f"15-minute crypto events with volume > 0: {len(crypto_15min)}\n")
    
    if len(crypto_15min) == 0:
        print("No 15-minute crypto markets found.")
        print("\nTip: Check https://polymarket.com/crypto/15M to see if there are active markets.")
        return
    
    # Format and display results
    results = []
    for event in crypto_15min:
        formatted = format_event(event)
        results.append(formatted)
        
        print("=" * 80)
        print(f"Title: {formatted['title']}")
        print(f"Slug: {formatted['slug']}")
        print(f"URL: {formatted['url']}")
        print(f"Active: {formatted['active']} | Closed: {formatted['closed']}")
        
        if formatted['start_date']:
            print(f"Start: {formatted['start_date']}")
        if formatted['end_date']:
            print(f"End: {formatted['end_date']}")
        
        print(f"\nMarkets ({len(formatted['markets'])}):")
        for market in formatted['markets']:
            print(f"\n  Question: {market['question']}")
            
            # Display outcomes and prices
            if market['outcomes'] and market['outcome_prices']:
                print(f"  Outcomes:")
                for outcome, price in zip(market['outcomes'], market['outcome_prices']):
                    try:
                        price_val = float(price)
                        print(f"    {outcome}: ${price_val:.4f} ({price_val*100:.2f}%)")
                    except:
                        print(f"    {outcome}: {price}")
            
            # Display volume and liquidity
            try:
                vol = float(market['volume'])
                liq = float(market['liquidity'])
                print(f"  Volume: ${vol:,.2f}")
                print(f"  Liquidity: ${liq:,.2f}")
            except:
                print(f"  Volume: {market['volume']}")
                print(f"  Liquidity: {market['liquidity']}")
            
            # Display tokens
            if market['clob_token_ids']:
                print(f"  Token IDs: {', '.join(market['clob_token_ids'][:2])}")
            
            print(f"  Tradable: {market['enable_order_book']}")
    
    print("\n" + "=" * 80)
    
    # Save to JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"polymarket_crypto_15min_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Data saved to: {filename}")
    print(f"✓ Total 15-minute crypto events: {len(results)}")

if __name__ == "__main__":
    main()