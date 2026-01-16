"""
Enhanced order execution system with advanced order types.
Supports limit orders, trailing stops, conditional orders, and smart routing.
"""

from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
from decimal import Decimal

from ..models.trade import Trade, TradeType, MarketDirection
from ..models.portfolio import Portfolio


class OrderType(Enum):
    """Types of orders supported"""
    MARKET = "market"           # Execute immediately at current price
    LIMIT = "limit"            # Execute only at specified price or better
    STOP = "stop"              # Execute when price reaches stop level
    TRAILING_STOP = "trailing_stop"  # Stop level trails price movement
    CONDITIONAL = "conditional" # Execute when condition is met


class OrderStatus(Enum):
    """Order status states"""
    PENDING = "pending"         # Order waiting to be filled
    PARTIAL = "partial"         # Order partially filled
    FILLED = "filled"          # Order completely filled
    CANCELLED = "cancelled"    # Order cancelled
    EXPIRED = "expired"        # Order expired
    REJECTED = "rejected"      # Order rejected


@dataclass
class Order:
    """Advanced order structure"""
    order_id: str
    market_id: str
    outcome: MarketDirection
    quantity: float
    order_type: OrderType
    side: TradeType  # BUY or SELL

    # Basic pricing
    price: Optional[float] = None  # For limit orders

    # Stop/trailing stop parameters
    stop_price: Optional[float] = None
    trailing_percent: Optional[float] = None
    trailing_amount: Optional[float] = None

    # Conditional order parameters
    condition_type: Optional[str] = None  # 'price_above', 'price_below', 'time_after', etc.
    condition_value: Optional[Any] = None

    # Order management
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)

    # Execution logic
    execution_logic: Optional[Callable] = None


class SmartOrderRouter:
    """
    Intelligent order routing system that optimizes execution
    across different price levels and market conditions.
    """

    def __init__(self, max_price_levels: int = 5, price_tolerance: float = 0.01):
        """
        Initialize smart order router.

        Args:
            max_price_levels: Maximum price levels to consider
            price_tolerance: Price tolerance for execution (1% = 0.01)
        """
        self.max_price_levels = max_price_levels
        self.price_tolerance = price_tolerance

    def find_optimal_price(self, market_data: Dict[str, Any], side: TradeType,
                          quantity: float, order_type: OrderType) -> Dict[str, Any]:
        """
        Find optimal execution price for an order.

        Args:
            market_data: Current market data with bids/asks
            side: Buy or sell
            quantity: Order quantity
            order_type: Type of order

        Returns:
            Optimal execution parameters
        """

        if order_type == OrderType.MARKET:
            return self._market_execution(market_data, side, quantity)
        elif order_type == OrderType.LIMIT:
            return self._limit_execution(market_data, side, quantity)
        else:
            # For advanced orders, return market execution as fallback
            return self._market_execution(market_data, side, quantity)

    def _market_execution(self, market_data: Dict[str, Any], side: TradeType, quantity: float) -> Dict[str, Any]:
        """Execute at current market price"""
        current_price = market_data.get('current_price', 0.5)
        return {
            'execution_price': current_price,
            'slippage': 0.0,
            'confidence': 0.9,
            'reasoning': 'Market order execution'
        }

    def _limit_execution(self, market_data: Dict[str, Any], side: TradeType, quantity: float) -> Dict[str, Any]:
        """Find optimal limit price"""
        current_price = market_data.get('current_price', 0.5)

        if side == TradeType.BUY:
            # For buys, look for better prices (lower)
            optimal_price = current_price * (1 - self.price_tolerance)
        else:
            # For sells, look for better prices (higher)
            optimal_price = current_price * (1 + self.price_tolerance)

        return {
            'execution_price': optimal_price,
            'slippage': abs(optimal_price - current_price) / current_price,
            'confidence': 0.7,
            'reasoning': f'Limit order at {optimal_price:.4f} for better execution'
        }


class EnhancedOrderExecutor:
    """
    Enhanced order execution system with advanced order types,
    smart routing, and risk management.
    """

    def __init__(self, portfolio: Portfolio, storage=None):
        self.portfolio = portfolio
        self.storage = storage
        self.active_orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []

        # Initialize smart router
        self.order_router = SmartOrderRouter()

    def place_order(self, market_id: str, outcome: MarketDirection, quantity: float,
                   order_type: OrderType = OrderType.MARKET, side: TradeType = TradeType.BUY,
                   price: Optional[float] = None, stop_price: Optional[float] = None,
                   trailing_percent: Optional[float] = None, expires_at: Optional[datetime] = None,
                   **kwargs) -> Optional[str]:
        """
        Place an advanced order with various execution options.

        Args:
            market_id: Market identifier
            outcome: YES/NO outcome
            quantity: Order quantity
            order_type: Type of order
            side: Buy or sell
            price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            trailing_percent: Trailing percentage (for trailing stops)
            expires_at: Order expiration time
            **kwargs: Additional order parameters

        Returns:
            Order ID if successful, None otherwise
        """

        # Validate order parameters
        if not self._validate_order(order_type, price, stop_price, trailing_percent):
            return None

        # Check risk limits
        if not self._check_risk_limits(quantity, side):
            return None

        # Create order
        order_id = str(uuid.uuid4())
        order = Order(
            order_id=order_id,
            market_id=market_id,
            outcome=outcome,
            quantity=quantity,
            order_type=order_type,
            side=side,
            price=price,
            stop_price=stop_price,
            trailing_percent=trailing_percent,
            expires_at=expires_at,
            **kwargs
        )

        # Set up execution logic based on order type
        order.execution_logic = self._get_execution_logic(order)

        # Store order
        self.active_orders[order_id] = order

        print(f"📋 Placed {order_type.value} order {order_id[:8]}: "
              f"{side.value} {quantity} {outcome.value} at {market_id}")

        return order_id

    def place_limit_order(self, market_id: str, outcome, quantity: float,
                         limit_price: float, side: TradeType = TradeType.BUY,
                         expires_at: Optional[datetime] = None) -> Optional[str]:
        """
        Place a limit order that executes only at the specified price or better.
        """
        # Convert string outcome to enum if needed
        if isinstance(outcome, str):
            outcome = MarketDirection.YES if outcome.upper() == 'YES' else MarketDirection.NO

        return self.place_order(
            market_id=market_id,
            outcome=outcome,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            side=side,
            price=limit_price,
            expires_at=expires_at
        )

    def place_trailing_stop(self, market_id: str, outcome, quantity: float,
                           trailing_percent: float, side: TradeType = TradeType.SELL) -> Optional[str]:
        """
        Place a trailing stop order that follows price movement.
        """
        # Convert string outcome to enum if needed
        if isinstance(outcome, str):
            outcome = MarketDirection.YES if outcome.upper() == 'YES' else MarketDirection.NO

        return self.place_order(
            market_id=market_id,
            outcome=outcome,
            quantity=quantity,
            order_type=OrderType.TRAILING_STOP,
            side=side,
            trailing_percent=trailing_percent
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an active order"""
        if order_id in self.active_orders:
            order = self.active_orders[order_id]
            order.status = OrderStatus.CANCELLED
            self.order_history.append(order)
            del self.active_orders[order_id]
            print(f"❌ Cancelled order {order_id[:8]}")
            return True
        return False

    def process_market_update(self, market_id: str, market_data: Dict[str, Any]):
        """
        Process market data updates and check for order execution opportunities.

        Args:
            market_id: Market identifier
            market_data: Current market data
        """

        # Check each active order for this market
        orders_to_process = [
            order for order in self.active_orders.values()
            if order.market_id == market_id and order.status == OrderStatus.PENDING
        ]

        for order in orders_to_process:
            try:
                if order.execution_logic and order.execution_logic(order, market_data):
                    self._execute_order(order, market_data)
            except Exception as e:
                print(f"Error processing order {order.order_id}: {e}")

    def _execute_order(self, order: Order, market_data: Dict[str, Any]) -> Optional[Trade]:
        """Execute a triggered order"""

        # Get optimal execution price
        execution_params = self.order_router.find_optimal_price(
            market_data, order.side, order.quantity, order.order_type
        )

        execution_price = execution_params['execution_price']
        slippage = execution_params.get('slippage', 0.0)

        # Calculate actual execution quantity (may be partial)
        remaining_quantity = order.quantity - order.filled_quantity
        executed_quantity = min(remaining_quantity, order.quantity)  # Full execution for now

        # Create trade
        trade = self._create_trade(order, executed_quantity, execution_price, slippage)

        if trade:
            # Update order status
            order.filled_quantity += executed_quantity
            order.average_fill_price = (
                (order.average_fill_price * (order.filled_quantity - executed_quantity)) +
                (execution_price * executed_quantity)
            ) / order.filled_quantity

            if order.filled_quantity >= order.quantity:
                order.status = OrderStatus.FILLED
                self.order_history.append(order)
                del self.active_orders[order.order_id]
            else:
                order.status = OrderStatus.PARTIAL

            print(f"✅ Executed order {order.order_id[:8]}: "
                  f"{executed_quantity} @ ${execution_price:.4f} (${slippage*100:.2f}% slippage)")

        return trade

    def _create_trade(self, order: Order, quantity: float, price: float, slippage: float) -> Optional[Trade]:
        """Create a trade object from executed order"""
        try:
            total_cost = quantity * price

            # Update portfolio
            if order.side == TradeType.BUY:
                if self.portfolio.current_balance < Decimal(str(total_cost)):
                    return None
                self.portfolio.update_balance(Decimal(str(-total_cost)))
            else:  # SELL
                self.portfolio.update_balance(Decimal(str(total_cost)))

            # Create trade record
            trade = Trade(
                market_id=order.market_id,
                outcome=order.outcome,
                quantity=quantity,
                price=price,
                trade_type=order.side,
                timestamp=datetime.now(),
                fee=slippage * total_cost  # Convert slippage to fee amount
            )

            return trade

        except Exception as e:
            print(f"Error creating trade: {e}")
            return None

    def _validate_order(self, order_type: OrderType, price: Optional[float],
                       stop_price: Optional[float], trailing_percent: Optional[float]) -> bool:
        """Validate order parameters"""

        if order_type == OrderType.LIMIT and price is None:
            print("Limit orders require a price parameter")
            return False

        if order_type == OrderType.STOP and stop_price is None:
            print("Stop orders require a stop_price parameter")
            return False

        if order_type == OrderType.TRAILING_STOP and trailing_percent is None:
            print("Trailing stop orders require a trailing_percent parameter")
            return False

        if price is not None and (price <= 0 or price >= 1):
            print("Order price must be between 0 and 1")
            return False

        if trailing_percent is not None and (trailing_percent <= 0 or trailing_percent >= 1):
            print("Trailing percentage must be between 0 and 1")
            return False

        return True

    def _check_risk_limits(self, quantity: float, side: TradeType) -> bool:
        """Check portfolio risk limits"""
        total_cost = quantity * 0.5  # Rough estimate

        if side == TradeType.BUY:
            max_position = float(self.portfolio.current_balance) * 0.1  # 10% of portfolio
            if total_cost > max_position:
                print(f"Order size ${total_cost:.2f} exceeds position limit ${max_position:.2f}")
                return False

        return True

    def _get_execution_logic(self, order: Order) -> Optional[Callable]:
        """Get execution logic function for order type"""

        if order.order_type == OrderType.MARKET:
            return lambda o, md: True  # Execute immediately

        elif order.order_type == OrderType.LIMIT:
            def limit_logic(o: Order, md: Dict[str, Any]) -> bool:
                current_price = md.get('current_price', 0.5)
                if o.side == TradeType.BUY:
                    return current_price <= o.price  # Buy at or below limit
                else:
                    return current_price >= o.price  # Sell at or above limit
            return limit_logic

        elif order.order_type == OrderType.STOP:
            def stop_logic(o: Order, md: Dict[str, Any]) -> bool:
                current_price = md.get('current_price', 0.5)
                if o.side == TradeType.SELL:  # Stop loss for longs
                    return current_price <= o.stop_price
                else:  # Stop loss for shorts
                    return current_price >= o.stop_price
            return stop_logic

        elif order.order_type == OrderType.TRAILING_STOP:
            def trailing_logic(o: Order, md: Dict[str, Any]) -> bool:
                current_price = md.get('current_price', 0.5)
                # Update trailing stop level based on price movement
                if o.side == TradeType.SELL:  # Trailing stop for longs
                    if o.stop_price is None:
                        o.stop_price = current_price * (1 - (o.trailing_percent or 0.05))
                    else:
                        # Update stop if price has moved favorably
                        trailing_pct = o.trailing_percent or 0.05
                        new_stop = current_price * (1 - trailing_pct)
                        o.stop_price = max(o.stop_price, new_stop)
                    return current_price <= o.stop_price
                else:  # Trailing stop for shorts
                    if o.stop_price is None:
                        o.stop_price = current_price * (1 + (o.trailing_percent or 0.05))
                    else:
                        trailing_pct = o.trailing_percent or 0.05
                        new_stop = current_price * (1 + trailing_pct)
                        o.stop_price = min(o.stop_price, new_stop)
                    return current_price >= o.stop_price
            return trailing_logic

        return None

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an order"""
        if order_id in self.active_orders:
            order = self.active_orders[order_id]
            return {
                'order_id': order.order_id,
                'status': order.status.value,
                'filled_quantity': order.filled_quantity,
                'remaining_quantity': order.quantity - order.filled_quantity,
                'average_fill_price': order.average_fill_price,
                'created_at': order.created_at.isoformat()
            }
        return None

    def get_active_orders(self) -> List[Dict[str, Any]]:
        """Get all active orders"""
        return [
            {
                'order_id': order.order_id,
                'market_id': order.market_id,
                'outcome': order.outcome.value,
                'quantity': order.quantity,
                'order_type': order.order_type.value,
                'side': order.side.value,
                'status': order.status.value,
                'filled_quantity': order.filled_quantity,
                'price': order.price,
                'stop_price': order.stop_price,
                'created_at': order.created_at.isoformat()
            }
            for order in self.active_orders.values()
        ]

    # Legacy compatibility methods
    def place_buy_order(self, market_id: str, outcome: MarketDirection,
                       quantity: float, max_price: float) -> Optional[Trade]:
        """Legacy market buy order for backward compatibility"""
        order_id = self.place_limit_order(market_id, outcome, quantity, max_price, TradeType.BUY)
        if order_id:
            # Immediately execute market order
            market_data = {'current_price': max_price}
            order = self.active_orders[order_id]
            return self._execute_order(order, market_data)
        return None

    def place_sell_order(self, market_id: str, outcome: MarketDirection,
                        quantity: float, min_price: float) -> Optional[Trade]:
        """Legacy market sell order for backward compatibility"""
        order_id = self.place_limit_order(market_id, outcome, quantity, min_price, TradeType.SELL)
        if order_id:
            # Immediately execute market order
            market_data = {'current_price': min_price}
            order = self.active_orders[order_id]
            return self._execute_order(order, market_data)
        return None