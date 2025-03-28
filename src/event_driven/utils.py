# --- Helper functions similar to load_results.py ---
from pathlib import Path
import sqlite3


def _get_db_connection():
    """Establish connection to the recommendations database."""
    # Use a path relative to the backtesting directory for the database
    db_path = Path(__file__).parents[1] / 'backtesting' / 'recommendations.db'
    conn = sqlite3.connect(db_path, timeout=10) # Added timeout
    cursor = conn.cursor()
    # Ensure table exists (optional, create_database in load_results should handle it)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        recommendation_date DATE NOT NULL,
        rating INTEGER,
        confidence INTEGER,
        entry_price TEXT,
        entry_timing TEXT,
        profit_target TEXT,
        stop_loss TEXT,
        time_horizon TEXT,
        exit_conditions TEXT,
        strategy_json TEXT, 
        UNIQUE(symbol, recommendation_date)
    )
    ''')
    conn.commit()
    return conn, cursor

def _parse_profit_target_db(pt_data):
    """Parses profit target for DB storage, focusing on primary."""
    if isinstance(pt_data, dict):
        primary = pt_data.get('primary')
        if isinstance(primary, dict):
            price = primary.get('price')
            perc = primary.get('percentage')
            if price is not None:
                pt_str = f"${price}"
                if perc is not None:
                    pt_str += f" ({perc}%)"
                return pt_str
    return '' # Default empty string

def _parse_stop_loss_db(sl_data):
    """Parses stop loss for DB storage."""
    if isinstance(sl_data, dict):
        price = sl_data.get('price')
        perc = sl_data.get('percentage')
        if price is not None:
            sl_str = f"${price}"
            if perc is not None:
                sl_str += f" ({perc}%)"
            return sl_str
    return '' # Default empty string

def _parse_conditions_db(cond_data):
    """Parses conditions list into a semicolon-separated string for DB."""
    if isinstance(cond_data, list):
        conditions_str = []
        for item in cond_data:
            if isinstance(item, dict):
                desc = item.get('description')
                if desc: # Prefer description if available
                     conditions_str.append(desc)
                else: # Fallback to constructing from parts
                    indicator = item.get('indicator', '?')
                    operator = item.get('operator', '?')
                    value = item.get('value', '?')
                    conditions_str.append(f"{indicator} {operator} {value}")
            elif isinstance(item, str): # Handle simple string conditions if they occur
                 conditions_str.append(item)
        return '; '.join(conditions_str)
    return '' # Default empty string