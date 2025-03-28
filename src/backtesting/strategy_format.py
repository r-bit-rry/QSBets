from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Literal, Any
from datetime import datetime

class Condition(BaseModel):
    """A single condition in a trading strategy."""
    indicator: str  # "price", "rsi", "macd", "sma20", "volume", etc.
    operator: str  # ">", "<", "crosses_above", "crosses_below", "=="
    value: Union[float, str]  # Numeric value or reference (e.g., 50, "signal_line")
    description: Optional[str] = None  # Human-readable description

class EntryStrategy(BaseModel):
    """Entry rules for a trading strategy."""
    price: Optional[Union[float, str]] = None  # Target entry price or reference level
    timing: Optional[str] = None  # Timing instructions
    conditions: List[Condition] = []  # Conditions that must be met for entry

class ProfitTarget(BaseModel):
    """Profit target specification."""
    price: float
    percentage: Optional[float] = None  # Gain percentage from entry

class StopLoss(BaseModel):
    """Stop loss specification."""
    price: float
    percentage: Optional[float] = None  # Loss percentage from entry

class ExitStrategy(BaseModel):
    """Exit rules for a trading strategy."""
    profit_target: Optional[Union[ProfitTarget, Dict[str, ProfitTarget]]] = None
    stop_loss: Optional[Union[StopLoss, float]] = None
    time_horizon: Optional[str] = None
    conditions: List[Condition] = []  # Conditions that trigger exit

class TradingStrategy(BaseModel):
    """Complete trading strategy definition."""
    symbol: str
    created_date: datetime = Field(default_factory=datetime.now)
    strategy_type: Literal["long", "short"] = "long"
    risk_reward_ratio: Optional[float] = None
    entry: EntryStrategy
    exit: ExitStrategy
    notes: Optional[str] = None  # Any additional information

if __name__ == "__main__":
    strategy = TradingStrategy(
        symbol="WBD",
        risk_reward_ratio=1.0,
        entry=EntryStrategy(
            price="10.75",  # SMA20
            timing="Immediate on pullback to SMA20 or after consolidation",
            conditions=[
                Condition(
                    indicator="macd",
                    operator=">",
                    value="signal_line",
                    description="MACD above signal line with increasing histogram",
                ),
                Condition(
                    indicator="price",
                    operator=">",
                    value="bollinger_middle",
                    description="Price above Bollinger middle band",
                ),
                Condition(
                    indicator="volume",
                    operator=">",
                    value=33255100,
                    description="Volume exceeds average",
                ),
            ],
        ),
        exit=ExitStrategy(
            profit_target={
                "primary": ProfitTarget(price=11.52, percentage=4.9),
                "secondary": ProfitTarget(price=11.92, percentage=8.6),
            },
            stop_loss=StopLoss(price=10.43, percentage=5.3),
            time_horizon="Short-term (1-2 weeks)",
            conditions=[
                Condition(
                    indicator="price",
                    operator="<",
                    value="sma100",
                    description="Close below SMA100 ($10.25)",
                ),
                Condition(
                    indicator="rsi", operator=">", value=70, description="RSI overbought"
                ),
                Condition(
                    indicator="stochastic_k",
                    operator="crosses_below",
                    value=80,
                    description="Stochastic K crosses below 80 from above",
                ),
            ],
        ),
    )
