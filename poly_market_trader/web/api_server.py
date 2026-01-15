"""
PolyMarket Paper Trader - FastAPI Web Server.

A web-based interface for the Polymarket Paper Trader application.
Provides REST API endpoints and WebSocket real-time updates.
"""

import asyncio
import json
from datetime import datetime
from typing import Set, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .routes import portfolio_router, markets_router, bets_router
from .services.trader_service import TraderService

trader_service = TraderService()

connected_clients: Set[WebSocket] = set()


async def broadcast_update(data: Dict[str, Any]) -> None:
    """Broadcast dashboard update to all connected WebSocket clients."""
    message = json.dumps({
        "type": "update",
        "data": data,
        "timestamp": datetime.now().isoformat()
    })
    
    disconnected = set()
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)
    
    connected_clients.difference_update(disconnected)


async def dashboard_update_loop():
    """Background task to send periodic dashboard updates."""
    while True:
        try:
            # Settle ready bets automatically
            try:
                settle_result = trader_service.settle_bets()
                if settle_result.get('success') and settle_result.get('data', {}).get('count', 0) > 0:
                    print(f"⚡ Auto-settled {settle_result['data']['count']} bet(s)")
            except Exception as e:
                print(f"⚠️  Error during auto-settlement: {e}")
            
            # Broadcast dashboard update
            data = trader_service.get_dashboard_data()
            if data['success']:
                await broadcast_update(data['data'])
        except Exception:
            pass
        
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    task = None
    
    try:
        task = asyncio.create_task(dashboard_update_loop())
        yield
    finally:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="Polymarket Paper Trader API",
    description="Web API for the Polymarket Paper Trader application",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio_router)
app.include_router(markets_router)
app.include_router(bets_router)


@app.get("/")
async def root():
    """Serve the SPA index page."""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polymarket Paper Trader</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid #333; }
        .header h1 { color: #00d9ff; font-size: 24px; }
        .balance { font-size: 28px; font-weight: bold; }
        .balance.positive { color: #00ff88; }
        .balance.negative { color: #ff4444; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
        .card { background: #16213e; border-radius: 12px; padding: 20px; border: 1px solid #333; }
        .card h2 { color: #00d9ff; margin-bottom: 15px; font-size: 16px; display: flex; align-items: center; gap: 8px; }
        .stat-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2a2a4a; }
        .stat-row:last-child { border-bottom: none; }
        .stat-label { color: #888; }
        .stat-value { font-weight: bold; }
        .table { width: 100%; border-collapse: collapse; }
        .table th, .table td { padding: 10px; text-align: left; border-bottom: 1px solid #333; }
        .table th { color: #888; font-weight: normal; font-size: 12px; text-transform: uppercase; }
        .table tr:hover { background: rgba(0, 217, 255, 0.1); }
        .btn { background: #00d9ff; color: #1a1a2e; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: 0.2s; }
        .btn:hover { background: #00b8d9; }
        .btn:disabled { background: #555; cursor: not-allowed; opacity: 0.6; }
        .btn-success { background: #00ff88; }
        .btn-danger { background: #ff4444; color: white; }
        .btn-running { background: #00ff88; cursor: default; }
        .nav { display: flex; gap: 5px; background: #0f0f23; padding: 5px; border-radius: 8px; margin-bottom: 20px; }
        .nav-item { padding: 10px 20px; border-radius: 6px; cursor: pointer; transition: 0.2s; }
        .nav-item.active { background: #00d9ff; color: #1a1a2e; font-weight: bold; }
        .win { color: #00ff88; }
        .loss { color: #ff4444; }
        .pending { color: #ffaa00; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .live { display: inline-block; width: 8px; height: 8px; background: #00ff88; border-radius: 50%; margin-right: 8px; animation: pulse 2s infinite; }
        .status-bar { display: flex; gap: 20px; align-items: center; background: #0f0f23; padding: 10px 20px; border-radius: 8px; margin-bottom: 20px; }
        .status-item { display: flex; align-items: center; gap: 8px; }
        .status-bar { display: flex; gap: 20px; align-items: center; background: #0f0f23; padding: 10px 20px; border-radius: 8px; margin-bottom: 20px; }
        .status-item { display: flex; align-items: center; gap: 8px; }
        .scrollable-table { max-height: 400px; overflow-y: auto; display: block; }
        .scrollable-table thead th { position: sticky; top: 0; background: #16213e; z-index: 1; }
    </style>
</head>
<body>
    <div id="app">
        <div class="container">
            <div class="header">
                <h1>📊 Polymarket Paper Trader</h1>
                <div>
                    <span :class="['balance', portfolio.pnl >= 0 ? 'positive' : 'negative']">
                        ${{ portfolio.current_balance?.toFixed(2) || '0.00' }}
                        <small style="color: #888; font-size: 14px;">
                            ({{ portfolio.pnl >= 0 ? '+' : '' }}${{ portfolio.pnl?.toFixed(2) || '0.00' }})
                        </small>
                    </span>
                </div>
            </div>
            
            <div class="status-bar">
                <div class="status-item">
                    <span v-if="autoBetRunning" class="live"></span>
                    <span style="color: #888;">Auto-Bet:</span>
                    <button :class="['btn', autoBetRunning ? 'btn-running' : 'btn-success']" @click="toggleAutoBet" style="min-width: 100px;">
                        {{ autoBetRunning ? '🟢 Running' : '🔴 Start' }}
                    </button>
                </div>
                <div class="status-item">
                    <button class="btn" @click="settleBets" :disabled="settling" style="min-width: 120px;">
                        {{ settling ? '⏳ Settling...' : '⚡ Settle Bets' }}
                    </button>
                </div>
                <div class="status-item" v-if="settlementStatus.last_check">
                    <span style="color: #888;">Last Check:</span>
                    <span style="font-size: 12px;">{{ formatSettlementTime(settlementStatus.last_check) }}</span>
                    <span v-if="settlementStatus.last_count > 0" class="win" style="margin-left: 5px;">({{ settlementStatus.last_count }} settled)</span>
                    <span v-if="settlementStatus.last_error" class="loss" style="margin-left: 5px;" :title="settlementStatus.last_error">⚠️</span>
                </div>
                <div class="status-item">
                    <span style="color: #888;">Active Bets:</span>
                    <span style="font-weight: bold;">{{ activeBets.length }}</span>
                </div>
                <div class="status-item">
                    <span style="color: #888;">Win Rate:</span>
                    <span :class="portfolio.win_rate >= 50 ? 'win' : 'loss'" style="font-weight: bold;">{{ portfolio.win_rate?.toFixed(1) }}%</span>
                </div>
                <div class="status-item">
                    <span style="color: #888;">Settled:</span>
                    <span>{{ portfolio.wins }}W / {{ portfolio.losses }}L</span>
                </div>
            </div>
            
            <div class="nav">
                <div class="nav-item" :class="{ active: currentView === 'dashboard' }" @click="currentView = 'dashboard'">Dashboard</div>
                <div class="nav-item" :class="{ active: currentView === 'markets' }" @click="currentView = 'markets'">Markets</div>
                <div class="nav-item" :class="{ active: currentView === 'history' }" @click="currentView = 'history'">History</div>
            </div>
            
            <div v-if="loading" style="text-align: center; padding: 40px; color: #888;">Loading...</div>
            
            <template v-else>
                <!-- Dashboard View -->
                <div v-if="currentView === 'dashboard'">
                    <div class="grid">
                        <div class="card">
                            <h2>💰 Portfolio</h2>
                            <div class="stat-row"><span class="stat-label">Balance</span><span class="stat-value">${{ portfolio.current_balance?.toFixed(2) }}</span></div>
                            <div class="stat-row"><span class="stat-label">Invested</span><span class="stat-value">${{ portfolio.invested?.toFixed(2) }}</span></div>
                            <div class="stat-row"><span class="stat-label">P&L</span><span :class="['stat-value', portfolio.pnl >= 0 ? 'win' : 'loss']">{{ portfolio.pnl >= 0 ? '+' : '' }}${{ portfolio.pnl?.toFixed(2) }}</span></div>
                            <div class="stat-row"><span class="stat-label">ROI</span><span :class="['stat-value', portfolio.roi >= 0 ? 'win' : 'loss']">{{ portfolio.roi >= 0 ? '+' : '' }}{{ portfolio.roi?.toFixed(2) }}%</span></div>
                        </div>
                        
                        <div class="card">
                            <h2>📈 Statistics</h2>
                            <div class="stat-row"><span class="stat-label">Total Bets</span><span class="stat-value">{{ portfolio.total_bets }}</span></div>
                            <div class="stat-row"><span class="stat-label">Wins</span><span class="stat-value win">{{ portfolio.wins }}</span></div>
                            <div class="stat-row"><span class="stat-label">Losses</span><span class="stat-value loss">{{ portfolio.losses }}</span></div>
                            <div class="stat-row"><span class="stat-label">Win Rate</span><span class="stat-value">{{ portfolio.win_rate?.toFixed(1) }}%</span></div>
                        </div>
                    </div>
                    
                    <div class="card" style="margin-top: 20px;">
                        <h2>📋 Active Bets ({{ filteredActiveBets.length }})</h2>
                        <div class="scrollable-table">
                            <table class="table" v-if="filteredActiveBets.length">
                                <thead><tr><th>Market</th><th>Outcome</th><th>Quantity</th><th>Cost</th><th>Ends</th></tr></thead>
                                  <tbody>
                                      <tr v-for="bet in filteredActiveBets" :key="bet.bet_id">
                                          <td><a :href="'https://polymarket.com/event/' + (bet.market_slug || bet.market_id)" target="_blank" style="color: #00d9ff; text-decoration: none;">{{ cleanQuestion(bet.question)?.substring(0, 50) }}... ↗</a></td>
                                          <td><span :class="bet.outcome === 'YES' ? 'win' : 'loss'">{{ bet.outcome }}</span></td>
                                          <td>{{ bet.quantity?.toFixed(2) }}</td>
                                          <td>${{ bet.cost?.toFixed(2) }}</td>
                                          <td>{{ formatTimeLeft(bet.market_end_time) }}</td>
                                      </tr>
                                  </tbody>
                            </table>
                            <p v-else style="color: #888; padding: 10px;">No active bets</p>
                        </div>
                    </div>
                    
                    <div class="card" style="margin-top: 20px;">
                        <h2>📊 Token Performance</h2>
                        <table class="table" v-if="tokenStats.length">
                            <thead><tr><th>Token</th><th>Bets</th><th>Wins</th><th>Losses</th><th>Pending</th><th>P&L</th></tr></thead>
                            <tbody>
                                <tr v-for="stat in tokenStats" :key="stat.token">
                                    <td>{{ stat.token?.toUpperCase() }}</td>
                                    <td>{{ stat.total_bets }}</td>
                                    <td class="win">{{ stat.wins }}</td>
                                    <td class="loss">{{ stat.losses }}</td>
                                    <td class="pending">{{ stat.pending }}</td>
                                    <td :class="stat.total_pnl >= 0 ? 'win' : 'loss'">{{ stat.total_pnl >= 0 ? '+' : '' }}${{ stat.total_pnl?.toFixed(2) }}</td>
                                </tr>
                            </tbody>
                        </table>
                        <p v-else style="color: #888;">No statistics yet</p>
                    </div>
                </div>
                
                <!-- Markets View -->
                <div v-if="currentView === 'markets'">
                    <div class="card">
                        <h2>📈 Available Crypto Markets</h2>
                         <table class="table">
                             <thead><tr><th>Market</th></tr></thead>
                             <tbody>
                                 <tr v-for="market in markets" :key="market.id">
                                     <td><a :href="'https://polymarket.com/event/' + (market.slug || market.id)" target="_blank" style="color: #00d9ff; text-decoration: none;">{{ cleanQuestion(market.question)?.substring(0, 70) }} ↗</a></td>
                                 </tr>
                             </tbody>
                         </table>
                    </div>
                </div>
                
                <!-- History View -->
                <div v-if="currentView === 'history'">
                    <div class="card">
                        <h2>📜 Bet History</h2>
                        <table class="table">
                            <thead><tr><th>Date</th><th>Market</th><th>Outcome</th><th>Result</th><th>P&L</th></tr></thead>
                             <tbody>
                                 <tr v-for="bet in history" :key="bet.bet_id">
                                     <td>{{ formatDate(bet.settled_at || bet.placed_at) }}</td>
                                     <td><a :href="'https://polymarket.com/event/' + (bet.market_slug || bet.market_id)" target="_blank" style="color: #00d9ff; text-decoration: none;">{{ cleanQuestion(bet.question)?.substring(0, 40) }}... ↗</a></td>
                                     <td>{{ bet.outcome }}</td>
                                     <td :class="bet.status === 'won' ? 'win' : bet.status === 'lost' ? 'loss' : 'pending'">{{ bet.status }}</td>
                                     <td :class="bet.profit_loss >= 0 ? 'win' : 'loss'">{{ bet.profit_loss >= 0 ? '+' : '' }}${{ bet.profit_loss?.toFixed(2) }}</td>
                                 </tr>
                             </tbody>
                        </table>
                    </div>
                </div>
            </template>
        </div>
    </div>

    <script>
        const { createApp, ref, reactive, computed, onMounted, onUnmounted } = Vue;
        
        createApp({
            setup() {
                const loading = ref(true);
                const currentView = ref('dashboard');
                const autoBetRunning = ref(false);
                const settling = ref(false);
                
                const portfolio = reactive({
                    current_balance: 0, pnl: 0, roi: 0, invested: 0,
                    total_bets: 0, wins: 0, losses: 0, win_rate: 0
                });
                
                const activeBets = ref([]);
                const history = ref([]);
                const markets = ref([]);
                const tokenStats = ref([]);
                const settlementStatus = reactive({
                    last_check: null,
                    last_count: 0,
                    last_error: null
                });
                
                // Sort active bets by end time (nearest to finish at the top)
                const filteredActiveBets = computed(() => {
                    if (!activeBets.value.length) return [];
                    
                    // Clone array to avoid mutating source
                    const bets = [...activeBets.value];
                    
                    // Sort by end time (nearest first)
                    return bets.sort((a, b) => {
                        const farFuture = 8640000000000000;
                        
                        let timeA = farFuture;
                        if (a.market_end_time) {
                            const dateA = new Date(a.market_end_time);
                            if (!isNaN(dateA.getTime())) timeA = dateA.getTime();
                        }
                        
                        let timeB = farFuture;
                        if (b.market_end_time) {
                            const dateB = new Date(b.market_end_time);
                            if (!isNaN(dateB.getTime())) timeB = dateB.getTime();
                        }
                        
                        return timeA - timeB;
                    });
                });
                
                let ws = null;
                let refreshInterval = null;
                
                const connectWS = () => {
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    ws = new WebSocket(`${protocol}//${window.location.host}/ws/dashboard`);
                    
                    ws.onmessage = (event) => {
                        const data = JSON.parse(event.data);
                        if (data.type === 'update') {
                            updateFromData(data.data);
                        }
                    };
                    
                    ws.onclose = () => setTimeout(connectWS, 5000);
                };
                
                const updateFromData = (data) => {
                    if (data.portfolio) {
                        Object.assign(portfolio, data.portfolio);
                    }
                    if (data.active_bets) {
                        activeBets.value = data.active_bets.bets || [];
                    }
                    if (data.recent_bets) {
                        history.value = data.recent_bets.bets || [];
                    }
                    if (data.token_stats) {
                        tokenStats.value = data.token_stats.statistics || [];
                    }
                    if (data.markets) {
                        markets.value = data.markets.markets || [];
                    }
                    if (data.settlement) {
                        Object.assign(settlementStatus, data.settlement);
                    }
                    loading.value = false;
                };
                
                const loadDashboard = async () => {
                    try {
                        const res = await axios.get('/api/dashboard');
                        if (res.data.success) {
                            updateFromData(res.data.data);
                        }
                        const statusRes = await axios.get('/api/bets/auto/status');
                        if (statusRes.data.success) {
                            autoBetRunning.value = statusRes.data.data.is_monitoring || false;
                        }
                    } catch (e) {
                        console.error('Failed to load:', e);
                        loading.value = false;
                    }
                };
                
                const toggleAutoBet = async () => {
                    if (autoBetRunning.value) {
                        await axios.post('/api/bets/auto/stop');
                        autoBetRunning.value = false;
                    } else {
                        await axios.post('/api/bets/auto/start');
                        autoBetRunning.value = true;
                    }
                };
                
                const settleBets = async () => {
                    settling.value = true;
                    try {
                        const res = await axios.post('/api/bets/settle');
                        if (res.data.success) {
                            const count = res.data.data?.count || 0;
                            console.log(`Settled ${count} bet(s)`);
                            // Refresh dashboard immediately
                            await loadDashboard();
                        }
                    } catch (e) {
                        console.error('Failed to settle bets:', e);
                    } finally {
                        settling.value = false;
                    }
                };
                
                const formatTimeLeft = (endTime) => {
                    if (!endTime) return 'Pending';
                    const end = new Date(endTime);
                    const now = new Date();
                    const diff = end - now;
                    if (diff <= 0) return 'Settled';
                    const mins = Math.floor(diff / 60000);
                    if (mins < 60) return `${mins}m`;
                    const hours = Math.floor(mins / 60);
                    return `${hours}h ${mins % 60}m`;
                };
                
                const formatDate = (dateStr) => {
                    if (!dateStr) return 'N/A';
                    return new Date(dateStr).toLocaleDateString();
                };
                
                const formatSettlementTime = (dateStr) => {
                    if (!dateStr) return 'Never';
                    const date = new Date(dateStr);
                    const now = new Date();
                    const diff = Math.floor((now - date) / 1000);
                    if (diff < 60) return `${diff}s ago`;
                    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
                    return date.toLocaleTimeString();
                };
                
                const cleanQuestion = (question) => {
                    if (!question) return '';
                    return question.replace(/\\s*-\\s*\\d+\\s*minute(s)?/gi, '');
                };
                
                onMounted(() => {
                    loadDashboard();
                    connectWS();
                    refreshInterval = setInterval(loadDashboard, 30000);
                });
                
                onUnmounted(() => {
                    if (ws) ws.close();
                    if (refreshInterval) clearInterval(refreshInterval);
                });
                
                return {
                    loading, currentView, autoBetRunning, settling, portfolio,
                    activeBets, filteredActiveBets, history, markets, tokenStats, settlementStatus,
                    toggleAutoBet, settleBets, formatTimeLeft, formatDate, formatSettlementTime, cleanQuestion
                };
            }
        }).mount('#app');
    </script>
</body>
</html>
    """, media_type="text/html")


@app.get("/api/dashboard")
async def get_dashboard():
    """Get all dashboard data in a single call."""
    result = trader_service.get_dashboard_data()
    return result


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await websocket.accept()
    connected_clients.add(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get('type') == 'ping':
                    await websocket.send_json({'type': 'pong'})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(websocket)


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
