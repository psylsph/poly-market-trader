import unittest
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from poly_market_trader.storage.bet_tracker import BetTracker

class TestBetHistoryFiltering(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_dir = os.path.join(self.test_dir, 'data')
        os.makedirs(self.storage_dir, exist_ok=True)
        self.bet_tracker = BetTracker(storage_dir=self.storage_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_bet_history_time_filtering(self):
        """Test filtering bet history by time"""
        now = datetime.now(timezone.utc)
        
        # Create history file manually with bets at different times
        history_data = {
            "version": "1.0",
            "bets": [
                {
                    "bet_id": "bet_recent",
                    "status": "won",
                    "settled_at": now.isoformat()
                },
                {
                    "bet_id": "bet_12h",
                    "status": "lost",
                    "settled_at": (now - timedelta(hours=12)).isoformat()
                },
                {
                    "bet_id": "bet_25h",
                    "status": "won",
                    "settled_at": (now - timedelta(hours=25)).isoformat()
                }
            ]
        }
        
        # Save to file
        self.bet_tracker._save_json_file(self.bet_tracker.bet_history_file, history_data)
        
        # 1. Test fetch all (no time limit)
        all_bets = self.bet_tracker.get_bet_history()
        self.assertEqual(len(all_bets), 3, "Should return all 3 bets")
        
        # 2. Test fetch last 24 hours
        start_time_24h = now - timedelta(hours=24)
        recent_bets = self.bet_tracker.get_bet_history(start_time=start_time_24h)
        self.assertEqual(len(recent_bets), 2, "Should return only 2 bets from last 24h")
        self.assertEqual(recent_bets[0]['bet_id'], 'bet_recent')
        self.assertEqual(recent_bets[1]['bet_id'], 'bet_12h')
        
        # 3. Test fetch last 1 hour
        start_time_1h = now - timedelta(hours=1)
        very_recent_bets = self.bet_tracker.get_bet_history(start_time=start_time_1h)
        self.assertEqual(len(very_recent_bets), 1, "Should return only 1 bet from last 1h")
        self.assertEqual(very_recent_bets[0]['bet_id'], 'bet_recent')

if __name__ == '__main__':
    unittest.main()
