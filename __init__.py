"""
QSBets - Quantitative Stock Betting System
"""
import os
import sys

# Make sure the package directory is in path so modules can be imported
package_dir = os.path.dirname(os.path.abspath(__file__))
if package_dir not in sys.path:
    sys.path.append(package_dir)

# Import key modules and functions to expose at the package level
from .analysis.ta_interpretation import (
    interpret_rsi,
    interpret_macd,
    interpret_moving_averages,
    interpret_bollinger_bands,
    interpret_adx,
    interpret_insider_activity,
    interpret_institutional_holdings,
    generate_preliminary_rating,
    generate_entry_exit_strategy
)

# Import summarization utilities
from .summarize.utils import (
    SummaryResponse,
    SYSTEM_PROMPT
)

from .summarize.ollama_summarize import ollama_summarize
from .cache.cache import cached, MONTH_TTL, DAY_TTL, WEEK_TTL, HOUR_TTL
from analysis.stock import Stock
# Package metadata
__version__ = "0.1.0"
__author__ = "Roy Belio"

# Make QSBets a proper package
