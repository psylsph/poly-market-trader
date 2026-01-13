from decimal import Decimal
import json
from typing import Dict, Any


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format a currency amount with proper symbols and precision"""
    return f"${amount:.2f}"


def format_percentage(value: float) -> str:
    """Format a decimal as a percentage"""
    return f"{value * 100:.2f}%"


def save_to_json(data: Dict[Any, Any], filename: str):
    """Save data to a JSON file"""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def load_from_json(filename: str) -> Dict[Any, Any]:
    """Load data from a JSON file"""
    with open(filename, 'r') as f:
        return json.load(f)


def calculate_pnl(entry_price: float, exit_price: float, quantity: float) -> float:
    """Calculate profit and loss for a trade"""
    return (exit_price - entry_price) * quantity


def validate_amount(amount: float, max_amount: float) -> bool:
    """Validate that an amount is positive and within limits"""
    return 0 < amount <= max_amount


def truncate_text(text: str, length: int) -> str:
    """Truncate text to a specified length with ellipsis"""
    if len(text) <= length:
        return text
    return text[:length] + "..."


def safe_divide(numerator: float, denominator: float) -> float:
    """Safely divide two numbers, returning 0 if denominator is 0"""
    if denominator == 0:
        return 0.0
    return numerator / denominator