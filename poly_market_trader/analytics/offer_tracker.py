from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
import time


class OfferTracker:
    """Tracks new betting opportunities (rolling offers)"""
    
    def __init__(self):
        self.offers = []
        self.max_offers = 10
    
    def analyze_market(self, market: Dict, crypto_name: str, 
                    current_price: float, trend: str, volatility: float) -> Optional[Dict]:
        """
        Analyze a market and create an offer entry
        :param market: Market data from Polymarket
        :param crypto_name: Name of cryptocurrency
        :param current_price: Current crypto price
        :param trend: Trend direction (bullish, bearish, neutral)
        :param volatility: Volatility percentage
        :return: Offer dictionary or None if not suitable
        """
        if trend == 'neutral':
            return None
        
        if trend == 'bullish':
            if volatility > 2.0:
                confidence = 0.8
                recommended_outcome = 'YES'
            else:
                confidence = 0.7
                recommended_outcome = 'YES'
        elif trend == 'bearish':
            if volatility > 2.0:
                confidence = 0.8
                recommended_outcome = 'NO'
            else:
                confidence = 0.7
                recommended_outcome = 'NO'
        else:
            return None
        
        if confidence >= 0.8:
            action = 'place'
            confidence_text = 'HIGH'
        elif confidence >= 0.6:
            action = 'place'
            confidence_text = 'MEDIUM'
        else:
            action = 'skip'
            confidence_text = 'LOW'
        
        offer = {
            'offer_id': f"{market.get('id', '')[:8]}...{int(time.time())}",
            'market_id': market.get('id', ''),
            'question': market.get('question', ''),
            'token': crypto_name,
            'trend': trend,
            'confidence': confidence,
            'confidence_text': confidence_text,
            'recommended_outcome': recommended_outcome,
            'action': action,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'market_end_time': market.get('endDate', ''),
            'current_price': current_price,
            'user_action': 'pending'
        }
        
        return offer
    
    def add_offer(self, offer: Dict) -> None:
        self.offers.append(offer)
        if len(self.offers) > self.max_offers:
            self.offers = self.offers[-self.max_offers:]
    
    def get_pending_offers(self) -> List[Dict]:
        return [o for o in self.offers if o.get('user_action') == 'pending']
    
    def get_all_offers(self) -> List[Dict]:
        return self.offers
    
    def update_offer_action(self, offer_id: str, action: str) -> None:
        for offer in self.offers:
            if offer.get('offer_id') == offer_id:
                offer['user_action'] = action
                break
    
    def print_offers_table(self, offers: List[Dict], title: str = "NEW OFFERS") -> None:
        if not offers:
            print("\n🎲 No new offers available.\n")
            return
        
        print(f"\n🎲 {title}")
        print("┌────────────────────────────────────────────────────────────────────┐")
        print("│ Market              │ Token │ Trend │ Conf │ Action    │")
        print("├────────────────────┼──────┼──────┼──────┼──────────┤")
        
        for i, offer in enumerate(offers, 1):
            market = offer.get('question', 'N/A')[:18]
            token = offer.get('token', 'N/A')[:7]
            trend = offer.get('trend', 'N/A')[0].upper()
            conf = f"{offer.get('confidence', 0.0):.0%}"
            action = offer.get('user_action', 'pending').upper()[:10]
            
            print(f"│ {i}. {market}│ {token}│ {trend}│ {conf}│ {action}    │")
        
        print("└────────────────────────────────────────────────────────────────────┘\n")
