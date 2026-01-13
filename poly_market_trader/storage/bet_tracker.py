import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from ..api.chainlink_data_provider import ChainlinkDataProvider
from ..models.portfolio import Portfolio
from ..models.trade import TradeType, MarketDirection
from ..services.order_executor import OrderExecutor


class BetTracker:
    """Tracks active bets and settlement logic"""
    
    def __init__(self, storage_dir: str = "data"):
        self.storage_dir = Path(storage_dir)
        self.active_bets_file = self.storage_dir / "active_bets.json"
        self.bet_history_file = self.storage_dir / "bet_history.json"
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """Create data directory if it doesn't exist"""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def add_active_bet(self, bet_info: Dict) -> str:
        """
        Add a new active bet for tracking
        :param bet_info: Dictionary containing bet details
        :return: bet_id (UUID string)
        """
        # Load existing active bets
        active_bets_data = self._load_json_file(self.active_bets_file)
        
        # Generate unique bet ID
        bet_id = str(uuid.uuid4())
        
        # Create bet record
        bet_record = {
            "bet_id": bet_id,
            "market_id": bet_info.get("market_id"),
            "question": bet_info.get("question", ""),
            "crypto_name": bet_info.get("crypto_name", ""),
            "outcome": bet_info.get("outcome"),
            "quantity": bet_info.get("quantity", 0.0),
            "entry_price": bet_info.get("entry_price", 0.0),
            "cost": bet_info.get("cost", 0.0),
            "placed_at": datetime.now(timezone.utc).isoformat(),
            "market_start_time": bet_info.get("market_start_time"),
            "market_end_time": bet_info.get("market_end_time"),
            "status": "active",
            "entry_crypto_price": bet_info.get("entry_crypto_price"),
            "start_crypto_price": None,
            "end_crypto_price": None,
            "actual_outcome": None,
            "payout": None,
            "profit_loss": None,
            "settled_at": None
        }
        
        # Add to active bets
        active_bets_data.setdefault("bets", []).append(bet_record)
        active_bets_data["version"] = "1.0"
        
        # Save to file
        self._save_json_file(self.active_bets_file, active_bets_data)
        
        print(f"📝 Bet tracked: {bet_id[:8]}... | {bet_record['outcome']} | Cost: ${bet_record['cost']:.2f}")
        
        return bet_id
    
    def get_active_bets(self) -> List[Dict]:
        """
        Get all active bets
        :return: List of active bet dictionaries
        """
        data = self._load_json_file(self.active_bets_file)
        return data.get("bets", [])
    
    def settle_bet(self, bet_id: str, chainlink_data: ChainlinkDataProvider, 
                   portfolio: Portfolio, order_executor: Optional[OrderExecutor] = None) -> Dict:
        """
        Settle a bet and update portfolio
        :param bet_id: ID of bet to settle
        :param chainlink_data: Chainlink data provider for price lookup
        :param portfolio: Portfolio to update with winnings
        :return: Settlement result dictionary
        """
        # Load active bets
        data = self._load_json_file(self.active_bets_file)
        active_bets = data.get("bets", [])
        
        # Find the bet
        bet_index = None
        bet_record = None
        for i, bet in enumerate(active_bets):
            if bet["bet_id"] == bet_id:
                bet_index = i
                bet_record = bet
                break
        
        if bet_record is None:
            return {"success": False, "error": "Bet not found"}
        
        print(f"\n🔍 Settling bet: {bet_record['question'][:50]}...")
        
        # Get market times
        market_start_time = self._parse_time(bet_record.get("market_start_time"))
        market_end_time = self._parse_time(bet_record.get("market_end_time"))
        crypto_name = bet_record.get("crypto_name", "")
        
        if not market_start_time or not market_end_time or not crypto_name:
            return {"success": False, "error": "Missing bet metadata"}
        
        # Determine actual outcome based on price movement
        try:
            actual_outcome, start_price, end_price = self._determine_outcome(
                crypto_name, market_start_time, market_end_time, chainlink_data
            )
            
            # Update bet record with settlement info
            bet_record["start_crypto_price"] = start_price
            bet_record["end_crypto_price"] = end_price
            bet_record["actual_outcome"] = actual_outcome
            bet_record["settled_at"] = datetime.now(timezone.utc).isoformat()
            
            # Calculate payout
            if bet_record["outcome"] == actual_outcome:
                # WIN: Payout $1.00 per share
                bet_record["payout"] = bet_record["quantity"] * 1.0
                bet_record["profit_loss"] = bet_record["payout"] - bet_record["cost"]
                bet_record["status"] = "won"
                
                if order_executor:
                    # Execute SELL trade at $1.00
                    order_executor.execute_trade(
                        market_id=bet_record["market_id"],
                        outcome=MarketDirection(bet_record["outcome"]),
                        quantity=bet_record["quantity"],
                        price=1.0,
                        trade_type=TradeType.SELL
                    )
                else:
                    # Legacy fallback: manual update
                    portfolio.update_balance(Decimal(str(bet_record["payout"])))
                    portfolio.remove_position(bet_record["market_id"], bet_record["outcome"])
                
                print(f"✅ BET WON! Outcome: {actual_outcome} | Payout: ${bet_record['payout']:.2f} | Profit: ${bet_record['profit_loss']:.2f}")
            else:
                # LOSS: Payout $0.00 per share
                bet_record["payout"] = 0.0
                bet_record["profit_loss"] = -bet_record["cost"]
                bet_record["status"] = "lost"
                
                if order_executor:
                    # Execute SELL trade at $0.00
                    order_executor.execute_trade(
                        market_id=bet_record["market_id"],
                        outcome=MarketDirection(bet_record["outcome"]),
                        quantity=bet_record["quantity"],
                        price=0.0,
                        trade_type=TradeType.SELL
                    )
                else:
                    # Legacy fallback: manual update
                    portfolio.remove_position(bet_record["market_id"], bet_record["outcome"])
                
                print(f"❌ BET LOST! Outcome: {actual_outcome} | Payout: $0.00 | Loss: ${bet_record['profit_loss']:.2f}")
            
            # Remove from active bets
            active_bets.pop(bet_index)
            
            # Add to history
            history_data = self._load_json_file(self.bet_history_file)
            history_data.setdefault("bets", []).append(bet_record)
            history_data["version"] = "1.0"
            self._save_json_file(self.bet_history_file, history_data)
            
            # Save updated active bets
            self._save_json_file(self.active_bets_file, {"bets": active_bets, "version": "1.0"})
            
            return {
                "success": True,
                "status": bet_record["status"],
                "payout": bet_record["payout"],
                "profit_loss": bet_record["profit_loss"]
            }
        
        except Exception as e:
            print(f"❌ Error settling bet: {e}")
            return {"success": False, "error": str(e)}
    
    def settle_all_ready_bets(self, chainlink_data: ChainlinkDataProvider, 
                            portfolio: Portfolio, order_executor: Optional[OrderExecutor] = None) -> List[Dict]:
        """
        Check and settle all bets that are ready (market end time + 5 min buffer passed)
        :param chainlink_data: Chainlink data provider
        :param portfolio: Portfolio to update
        :param order_executor: Order executor for trade processing (optional)
        :return: List of settlement results
        """
        active_bets = self.get_active_bets()
        current_time = datetime.now(timezone.utc)
        
        settlement_buffer = timedelta(minutes=5)
        settled = []
        
        for bet in active_bets:
            market_end_time = self._parse_time(bet.get("market_end_time"))
            
            if market_end_time and current_time > market_end_time + settlement_buffer:
                # Bet is ready for settlement
                result = self.settle_bet(bet["bet_id"], chainlink_data, portfolio, order_executor)
                settled.append(result)
        
        return settled
    
    def get_bet_history(self, limit: int = None, status_filter: str = None) -> List[Dict]:
        """
        Get bet history with optional filtering
        :param limit: Maximum number of bets to return (None = all)
        :param status_filter: Filter by status ('won', 'lost', 'active')
        :return: List of bet dictionaries
        """
        data = self._load_json_file(self.bet_history_file)
        bets = data.get("bets", [])
        
        # Filter by status if specified
        if status_filter:
            bets = [b for b in bets if b.get("status") == status_filter]
        
        # Sort by settled_at (most recent first)
        bets.sort(key=lambda x: x.get("settled_at", ""), reverse=True)
        
        # Apply limit
        if limit:
            bets = bets[:limit]
        
        return bets
    
    def _determine_outcome(self, crypto_name: str, start_time: datetime, 
                         end_time: datetime, chainlink_data: ChainlinkDataProvider) -> tuple:
        """
        Determine the actual outcome of an "Up or Down" market
        :param crypto_name: Cryptocurrency to check
        :param start_time: Market start time
        :param end_time: Market end time
        :param chainlink_data: Chainlink data provider
        :return: (outcome: "YES"/"NO", start_price, end_price)
        """
        print(f"   Checking {crypto_name} prices from {start_time} to {end_time}...")
        
        # Get price at start time
        start_price = chainlink_data.get_price_at_time(crypto_name, start_time)
        
        # Get price at end time
        end_price = chainlink_data.get_price_at_time(crypto_name, end_time)
        
        if start_price is None or end_price is None:
            raise Exception(f"Could not retrieve prices for {crypto_name}")
        
        print(f"   Start price: ${start_price:.2f} | End price: ${end_price:.2f}")
        
        # Determine outcome
        if end_price > start_price:
            outcome = "YES"  # Price went up
        else:
            outcome = "NO"   # Price went down or stayed same
        
        return outcome, start_price, end_price
    
    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """Parse ISO format time string to datetime"""
        if not time_str:
            return None
        
        # Handle different date formats
        try:
            if 'T' in time_str:
                return datetime.fromisoformat(time_str)
            else:
                return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"Error parsing time '{time_str}': {e}")
            return None
    
    def _load_json_file(self, file_path: Path) -> Dict:
        """Load JSON file, return empty dict if doesn't exist"""
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return {}
    
    def _save_json_file(self, file_path: Path, data: Dict) -> None:
        """Save data to JSON file"""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
