from datetime import datetime
from glob import glob
import re
import streamlit as st
import pandas as pd
import json
import yaml
import os
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from collectors.nasdaq import fetch_historical_quotes, fetch_nasdaq_data, fetch_stock_news, fetch_stock_press_releases
from analysis.ta import fetch_technical_indicators, prepare_dataframe
from storage.cache import cached, DAY_TTL

# Configure page settings
st.set_page_config(page_title="QSBets Dashboard", layout="wide", initial_sidebar_state="expanded")

# Apply dark theme styling (Optional, can be customized)
st.markdown(
    """
    <style>
    /* Base theme adjustments */
    body { background-color: #1e1e1e; color: white; }
    .stApp { background-color: #1e1e1e; }
    .css-1d391kg { /* Main content area */ background-color: #2a2a2a; }
    .css-1lcbmhc { /* Sidebar */ background-color: #333333; }
    
    /* Text and Headers */
    h1, h2, h3, h4, h5, h6, p, .stMarkdown, .stMetricLabel, .stMetricValue, .stDataFrame, .stSelectbox label, .stSlider label, .stTextInput label { color: white; }
    
    /* Widgets */
    .stButton>button { background-color: #4CAF50; color: white; border: none; padding: 10px 24px; text-align: center; text-decoration: none; display: inline-block; font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 8px; }
    .stButton>button:hover { background-color: #45a049; }
    .stSelectbox > div > div { background-color: #444; color: white; border-radius: 4px; }
    .stTextInput > div > div > input { background-color: #444; color: white; border-radius: 4px; }
    .stSlider > div > div > div[role="slider"] { background-color: #4CAF50; }
    
    /* Plotly Chart Background */
    .plotly-graph-div { background-color: rgba(42, 42, 42, 0.8); border-radius: 8px; } 
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { background-color: #333; border-radius: 8px 8px 0 0; }
    .stTabs [data-baseweb="tab"] { color: #ccc; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background-color: #4CAF50; color: white; border-radius: 4px 4px 0 0; }
    
    </style>
    """,
    unsafe_allow_html=True
)


def find_latest_file(directory, pattern, symbol=None):
    """
    Find the most recent file in the date hierarchy directory that matches
    the pattern and optionally contains the symbol.
    Handles potential errors during file system traversal.
    """
    latest_file = None
    latest_date = None

    try:
        # Walk through the date hierarchy directories
        for root, dirs, files in os.walk(directory):
            # Optimize: Skip hidden directories or irrelevant paths early
            dirs[:] = [d for d in dirs if not d.startswith('.')] 
            
            for file in files:
                if file.endswith(pattern):
                    # Check if the file name contains the symbol (if specified)
                    if symbol and symbol.lower() not in file.lower():
                        continue

                    # Extract date from directory path
                    # Path format: analysis_docs/YYYY/MM/DD/ or results/YYYY/MM/DD/
                    path_parts = root.split(os.sep)
                    if len(path_parts) >= 4:  # Ensure enough parts
                        try:
                            year = int(path_parts[-3])
                            month = int(path_parts[-2])
                            day = int(path_parts[-1])
                            file_date = datetime(year, month, day)

                            # Update if this is the most recent file found so far
                            if latest_date is None or file_date > latest_date:
                                latest_date = file_date
                                latest_file = os.path.join(root, file)
                        except (ValueError, IndexError):
                            # Log or handle paths not conforming to expected format
                            # st.warning(f"Skipping path with unexpected format: {root}")
                            continue
    except OSError as e:
        st.error(f"Error accessing directory {directory}: {e}")
        return None # Return None on directory access error

    return latest_file


def load_analysis_doc(symbol):
    """Load the analysis document for a specific symbol."""
    analysis_docs_path = "./analysis_docs"
    latest_file = find_latest_file(analysis_docs_path, f"{symbol.lower()}.yaml", symbol) # More specific pattern

    if not latest_file:
        # Fallback: Find any latest yaml file if symbol-specific not found (consider if this is desired)
        # latest_file = find_latest_file(analysis_docs_path, ".yaml") 
        st.warning(f"No analysis document found specifically for {symbol}.")
        return None, None

    try:
        with open(latest_file, "r") as file:
            return yaml.safe_load(file), os.path.basename(latest_file)
    except FileNotFoundError:
        st.error(f"Analysis file not found: {latest_file}")
        return None, None
    except yaml.YAMLError as e:
        st.error(f"Error parsing YAML file {latest_file}: {e}")
        return None, None
    except Exception as e:
        st.error(f"Error loading analysis document {latest_file}: {e}")
        return None, None


def load_result_for_symbol(results_path, symbol):
    """Find the result for a specific symbol in a results file."""
    try:
        with open(results_path, "r") as file:
            # Handle potential JSON decoding errors per line
            results = []
            for i, line in enumerate(file):
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError as e:
                    st.warning(f"Skipping invalid JSON on line {i+1} in {results_path}: {e}")
                    continue
        
        for result in results:
            # Case-insensitive symbol comparison
            if result.get("symbol", "").upper() == symbol.upper():
                return result
        
        return None # Symbol not found in this file
    except FileNotFoundError:
        st.error(f"Results file not found: {results_path}")
        return None
    except Exception as e:
        st.error(f"Error loading results from {results_path}: {e}")
        return None


def load_results():
    """Load the latest results file from ../results/results_YYYY-MM-DD.jsonl."""
    results_dir = "../results" # Corrected path
    results = []
    latest_results_filename = None
    latest_date = None

    try:
        # Find files matching the pattern
        file_pattern = os.path.join(results_dir, "results_*.jsonl")
        result_files = glob(file_pattern)

        # Regex to extract date from filename
        date_pattern = re.compile(r"results_(\d{4}-\d{2}-\d{2})\.jsonl")

        for file_path in result_files:
            match = date_pattern.search(os.path.basename(file_path))
            if match:
                try:
                    file_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                    if latest_date is None or file_date > latest_date:
                        latest_date = file_date
                        latest_results_filename = os.path.basename(file_path)
                except ValueError:
                    st.warning(f"Skipping file with invalid date format: {os.path.basename(file_path)}")
                    continue
        
        if latest_results_filename:
            latest_results_file_path = os.path.join(results_dir, latest_results_filename)
            try:
                with open(latest_results_file_path, "r") as file:
                    # Handle potential JSON decoding errors per line
                    for i, line in enumerate(file):
                        try:
                            results.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            st.warning(f"Skipping invalid JSON on line {i+1} in {latest_results_filename}: {e}")
                            continue
                st.sidebar.success(f"Loaded results: {latest_results_filename}")
            except FileNotFoundError:
                 st.sidebar.error(f"Results file not found: {latest_results_file_path}")
                 results = [{"symbol": "AAPL"}] # Default on error
            except Exception as e:
                st.sidebar.error(f"Error loading results file {latest_results_filename}: {e}")
                results = [{"symbol": "AAPL"}] # Default on error
        else:
            st.sidebar.error(f"No results files found matching pattern in {results_dir}")
            results = [{"symbol": "AAPL"}]  # Default if no results found

    except OSError as e:
        st.sidebar.error(f"Error accessing results directory {results_dir}: {e}")
        results = [{"symbol": "AAPL"}] # Default on error
        
    return results, latest_results_filename # Return filename, not full path

def create_technical_chart(indicators):
    """Create a comprehensive technical analysis chart with improved readability."""
    
    # Ensure essential indicators are present
    if not all(k in indicators for k in ['rsi', 'macd', 'bollinger_bands', 'historical_quotes']):
        st.warning("Missing essential indicator data for charting.")
        return go.Figure() # Return empty figure

    # Create figure with subplots and secondary y-axes
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05, # Slightly reduced spacing
        row_heights=[0.45, 0.15, 0.20, 0.20], # Adjusted heights
        subplot_titles=("<b>Price & Volume</b>", "<b>Trend (BB, EMA, ADX)</b>", "<b>Oscillators (RSI, Stoch, CCI)</b>", "<b>Momentum (MACD)</b>"),
        specs=[[{"secondary_y": True}], # Row 1: Price/Volume
               [{"secondary_y": True}], # Row 2: Trend (ADX on secondary)
               [{"secondary_y": True}], # Row 3: Oscillators (CCI on secondary)
               [{"secondary_y": False}]] # Row 4: MACD
    )

    # Prepare X-axis data (use datetime index if available)
    historical_quotes = indicators.get('historical_quotes', {})
    quotes_df = None
    x_axis = None
    if historical_quotes:
        try:
            quotes_df = pd.DataFrame.from_dict(historical_quotes, orient='index')
            quotes_df.index = pd.to_datetime(quotes_df.index)
            quotes_df = quotes_df.sort_index() # Ensure chronological order
            x_axis = quotes_df.index
        except Exception as e:
            st.warning(f"Could not process historical quotes index: {e}")
            # Fallback to simple range if dates fail
            x_axis = list(range(len(indicators.get('rsi', [])))) # Use RSI length as fallback
    else:
         x_axis = list(range(len(indicators.get('rsi', [])))) # Use RSI length if no quotes

    # FIX: Correctly check if x_axis is None or empty
    is_xaxis_empty = False
    if x_axis is None:
        is_xaxis_empty = True
    elif isinstance(x_axis, (pd.DatetimeIndex, pd.Index)):
        is_xaxis_empty = x_axis.empty
    elif isinstance(x_axis, list):
        is_xaxis_empty = len(x_axis) == 0

    if is_xaxis_empty:
        st.warning("No valid X-axis data for charting.")
        return go.Figure()

    # --- Row 1: Price & Volume ---
    if quotes_df is not None:
        # Candlestick chart for price
        fig.add_trace(
            go.Candlestick(
                x=x_axis,
                open=quotes_df['open'], high=quotes_df['high'],
                low=quotes_df['low'], close=quotes_df['close'],
                name='Price',
                increasing_line_color='cyan', decreasing_line_color='gray'
            ),
            row=1, col=1, secondary_y=False
        )
        # Volume chart on secondary axis
        fig.add_trace(
            go.Bar(
                x=x_axis, y=quotes_df['volume'] / 1_000_000, # Scale to millions
                name='Volume (M)', marker_color='rgba(100, 100, 200, 0.5)', # Lighter blue
                opacity=0.6
            ),
            row=1, col=1, secondary_y=True
        )
    else:
        # Fallback: Line chart for closing price if candlestick fails
        close_prices = indicators.get('sma_20', []) # Use SMA as proxy if needed
        if close_prices:
             fig.add_trace(go.Scatter(x=x_axis, y=close_prices, mode='lines', name='Price (Close)'), row=1, col=1, secondary_y=False)

    # Add Moving Averages to Price Chart
    for sma, color, dash in [('sma_20', 'blue', 'solid'), ('sma_50', 'orange', 'solid'), ('sma_100', 'green', 'dash')]:
        if sma in indicators and indicators[sma]:
            fig.add_trace(go.Scatter(x=x_axis, y=indicators[sma], mode='lines', 
                                    name=sma.upper(), line=dict(color=color, dash=dash, width=1)), 
                          row=1, col=1, secondary_y=False)

    # --- Row 2: Trend Indicators (BB, EMA, ADX) ---
    # Bollinger Bands
    if 'bollinger_bands' in indicators and indicators['bollinger_bands']:
        bb_data = indicators['bollinger_bands']
        # Ensure bb_data is a list of dicts
        if isinstance(bb_data, list) and all(isinstance(item, dict) for item in bb_data):
            upper_band = [bb.get('upper') for bb in bb_data]
            middle_band = [bb.get('middle') for bb in bb_data]
            lower_band = [bb.get('lower') for bb in bb_data]

            fig.add_trace(go.Scatter(x=x_axis, y=upper_band, mode='lines', line=dict(color='rgba(250,128,114,0.5)', width=1), name='Upper BB'), row=2, col=1, secondary_y=False)
            fig.add_trace(go.Scatter(x=x_axis, y=middle_band, mode='lines', line=dict(color='rgba(0,128,0,0.5)', width=1), name='Middle BB'), row=2, col=1, secondary_y=False)
            fig.add_trace(go.Scatter(x=x_axis, y=lower_band, mode='lines', line=dict(color='rgba(250,128,114,0.5)', width=1), fill='tonexty', fillcolor='rgba(250,128,114,0.1)', name='Lower BB'), row=2, col=1, secondary_y=False)

    # EMA
    if 'ema_20' in indicators and indicators['ema_20']:
        fig.add_trace(go.Scatter(x=x_axis, y=indicators['ema_20'], mode='lines', name='EMA 20', line=dict(color='purple', width=1)), row=2, col=1, secondary_y=False)

    # ADX on secondary axis
    if 'adx' in indicators and indicators['adx']:
        fig.add_trace(go.Scatter(x=x_axis, y=indicators['adx'], mode='lines', name='ADX', line=dict(color='brown', width=1.5)), row=2, col=1, secondary_y=True)
        # ADX reference line
        fig.add_shape(type="line", x0=x_axis[0], x1=x_axis[-1], y0=25, y1=25, line=dict(color="brown", width=1, dash="dash"), row=2, col=1, secondary_y=True)

    # --- Row 3: Oscillators (RSI, Stoch, CCI) ---
    # RSI
    if 'rsi' in indicators and indicators['rsi']:
        fig.add_trace(go.Scatter(x=x_axis, y=indicators['rsi'], mode='lines', name='RSI', line=dict(color='blue', width=1.5)), row=3, col=1, secondary_y=False)
        # RSI reference lines
        fig.add_shape(type="line", x0=x_axis[0], x1=x_axis[-1], y0=70, y1=70, line=dict(color="red", width=1, dash="dash"), row=3, col=1, secondary_y=False)
        fig.add_shape(type="line", x0=x_axis[0], x1=x_axis[-1], y0=30, y1=30, line=dict(color="green", width=1, dash="dash"), row=3, col=1, secondary_y=False)

    # Stochastic
    if 'stochastic_14_3_3' in indicators and indicators['stochastic_14_3_3']:
        stoch_data = indicators['stochastic_14_3_3']
        if isinstance(stoch_data, list) and all(isinstance(item, dict) for item in stoch_data):
            stoch_k = [stoch.get('stochastic_k') for stoch in stoch_data]
            stoch_d = [stoch.get('stochastic_d') for stoch in stoch_data]
            fig.add_trace(go.Scatter(x=x_axis, y=stoch_k, mode='lines', name='Stoch %K', line=dict(color='orange', width=1)), row=3, col=1, secondary_y=False)
            fig.add_trace(go.Scatter(x=x_axis, y=stoch_d, mode='lines', name='Stoch %D', line=dict(color='green', width=1)), row=3, col=1, secondary_y=False)
            # Stochastic reference lines
            fig.add_shape(type="line", x0=x_axis[0], x1=x_axis[-1], y0=80, y1=80, line=dict(color="red", width=1, dash="dash"), row=3, col=1, secondary_y=False)
            fig.add_shape(type="line", x0=x_axis[0], x1=x_axis[-1], y0=20, y1=20, line=dict(color="green", width=1, dash="dash"), row=3, col=1, secondary_y=False)

    # CCI on secondary axis
    if 'cci' in indicators and indicators['cci']:
        fig.add_trace(go.Scatter(x=x_axis, y=indicators['cci'], mode='lines', name='CCI', line=dict(color='purple', width=1.5)), row=3, col=1, secondary_y=True)
        # CCI reference lines
        fig.add_shape(type="line", x0=x_axis[0], x1=x_axis[-1], y0=100, y1=100, line=dict(color="red", width=1, dash="dot"), row=3, col=1, secondary_y=True)
        fig.add_shape(type="line", x0=x_axis[0], x1=x_axis[-1], y0=-100, y1=-100, line=dict(color="green", width=1, dash="dot"), row=3, col=1, secondary_y=True)


    # --- Row 4: Momentum (MACD) ---
    if 'macd' in indicators and indicators['macd']:
        macd_data = indicators['macd']
        if isinstance(macd_data, list) and all(isinstance(item, dict) for item in macd_data):
            macd_values = [macd.get('macd') for macd in macd_data]
            signal_values = [macd.get('signal') for macd in macd_data]
            hist_values = [macd.get('hist') for macd in macd_data]

            # MACD Line
            fig.add_trace(go.Scatter(x=x_axis, y=macd_values, mode='lines', name='MACD', line=dict(color='blue', width=1.5)), row=4, col=1)
            # Signal Line
            fig.add_trace(go.Scatter(x=x_axis, y=signal_values, mode='lines', name='Signal', line=dict(color='red', width=1.5)), row=4, col=1)
            # Histogram
            colors = ['green' if val >= 0 else 'red' for val in hist_values]
            fig.add_trace(go.Bar(x=x_axis, y=hist_values, name='Histogram', marker_color=colors, opacity=0.7), row=4, col=1)
            # Zero Line
            fig.add_shape(type="line", x0=x_axis[0], x1=x_axis[-1], y0=0, y1=0, line=dict(color="grey", width=1, dash="solid"), row=4, col=1)

    # --- Update Layout and Axes ---
    fig.update_layout(
        height=1000, # Adjust height as needed
        title_text=f"<b>Technical Analysis Dashboard</b>",
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        plot_bgcolor='rgba(30, 30, 30, 0.9)', # Darker plot background
        paper_bgcolor='rgba(30, 30, 30, 1)', # Dark paper background
        font_color='white',
        hovermode='x unified', # Improved hover information
        margin=dict(l=50, r=50, t=80, b=50) # Adjust margins
    )

    # Update axes properties for clarity and dark theme
    fig.update_xaxes(showgrid=True, gridwidth=0.5, gridcolor='rgba(100, 100, 100, 0.5)', zeroline=False, row=1, col=1)
    fig.update_xaxes(showgrid=True, gridwidth=0.5, gridcolor='rgba(100, 100, 100, 0.5)', zeroline=False, row=2, col=1)
    fig.update_xaxes(showgrid=True, gridwidth=0.5, gridcolor='rgba(100, 100, 100, 0.5)', zeroline=False, row=3, col=1)
    fig.update_xaxes(showgrid=True, gridwidth=0.5, gridcolor='rgba(100, 100, 100, 0.5)', zeroline=False, row=4, col=1, title_text="Date") # Add X-axis title to last row

    # Row 1 Axes
    fig.update_yaxes(title_text="Price ($)", showgrid=True, gridwidth=0.5, gridcolor='rgba(100, 100, 100, 0.5)', zeroline=False, row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Volume (M)", showgrid=False, zeroline=False, row=1, col=1, secondary_y=True, range=[0, (quotes_df['volume'].max() / 1_000_000) * 3 if quotes_df is not None else 100]) # Adjust volume range

    # Row 2 Axes
    fig.update_yaxes(title_text="Price Scale", showgrid=True, gridwidth=0.5, gridcolor='rgba(100, 100, 100, 0.5)', zeroline=False, row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="ADX", showgrid=False, zeroline=False, row=2, col=1, secondary_y=True, range=[0, 100]) # ADX range 0-100

    # Row 3 Axes
    fig.update_yaxes(title_text="RSI / Stoch", showgrid=True, gridwidth=0.5, gridcolor='rgba(100, 100, 100, 0.5)', zeroline=False, range=[0, 100], row=3, col=1, secondary_y=False) # Fixed range 0-100
    fig.update_yaxes(title_text="CCI", showgrid=False, zeroline=False, row=3, col=1, secondary_y=True) # CCI autorange

    # Row 4 Axes
    fig.update_yaxes(title_text="MACD", showgrid=True, gridwidth=0.5, gridcolor='rgba(100, 100, 100, 0.5)', zeroline=False, row=4, col=1)

    return fig

def display_key_indicators(indicators):
    """Display key indicator values in a well-formatted way."""
    # Ensure indicators is a dict and has the required keys
    if not isinstance(indicators, dict):
        st.warning("Invalid indicator data format.")
        return
        
    # Safely get the last value from lists, handle None or missing keys
    def get_last(key, subkey=None, default=None):
        data = indicators.get(key, default)
        if isinstance(data, list) and data:
            item = data[-1]
            if subkey and isinstance(item, dict):
                return item.get(subkey, default)
            return item
        elif subkey and isinstance(data, dict): # Handle case where data is already the last dict
             return data.get(subkey, default)
        return data # Return data if not list or empty list

    rsi_last = get_last('rsi')
    adx_last = get_last('adx')
    macd_last_dict = get_last('macd', default={})
    macd_val = macd_last_dict.get('macd')
    macd_hist = macd_last_dict.get('hist')
    macd_signal = macd_last_dict.get('signal')
    atr_last = get_last('atr')
    bb_last = get_last('bollinger_bands', default={})
    bb_upper = bb_last.get('upper')
    bb_lower = bb_last.get('lower')
    bb_middle = bb_last.get('middle')

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Trend")
        if rsi_last is not None:
            rsi_delta = "Overbought" if rsi_last > 70 else "Oversold" if rsi_last < 30 else "Neutral"
            st.metric("RSI (14)", f"{rsi_last:.2f}", delta=rsi_delta)
        else:
            st.metric("RSI (14)", "N/A")
            
        if adx_last is not None:
            adx_delta = "Strong Trend" if adx_last > 25 else "Weak/No Trend"
            st.metric("ADX (14)", f"{adx_last:.2f}", delta=adx_delta)
        else:
            st.metric("ADX (14)", "N/A")
    
    with col2:
        st.subheader("Momentum")
        if macd_val is not None and macd_hist is not None:
            macd_delta = "Bullish" if macd_hist > 0 else "Bearish"
            st.metric("MACD", f"{macd_val:.2f}", delta=macd_delta)
        else:
             st.metric("MACD", "N/A")
             
        if macd_signal is not None:
            st.metric("Signal Line", f"{macd_signal:.2f}")
        else:
            st.metric("Signal Line", "N/A")
    
    with col3:
        st.subheader("Volatility")
        if atr_last is not None:
            st.metric("ATR (14)", f"{atr_last:.2f}")
        else:
            st.metric("ATR (14)", "N/A")
            
        if all(v is not None for v in [bb_upper, bb_lower, bb_middle]) and bb_middle != 0:
            bb_width = (bb_upper - bb_lower) / bb_middle * 100
            bb_delta = "High Volatility" if bb_width > 5 else "Low Volatility" # Example threshold
            st.metric("BB Width (%)", f"{bb_width:.2f}%", delta=bb_delta)
        else:
            st.metric("BB Width (%)", "N/A")


def display_recommendation_info(result_data):
    """Display the recommendation information for a stock."""
    if not result_data:
        st.warning("No recommendation data available.")
        return
        
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Rating")
        rating_val = result_data.get("rating", "N/A")
        confidence_val = result_data.get("confidence", "N/A")
        st.metric("Overall Rating", rating_val if rating_val != "N/A" else "N/A")
        st.metric("Confidence", f"{confidence_val}/5" if confidence_val != "N/A" else "N/A")
    
    with col2:
        st.subheader("Recommendation")
        rating = result_data.get("rating") # Keep as number for comparison
        recommendation = "N/A"
        color = "grey" # Default color

        if isinstance(rating, (int, float)):
            recommendation_map = {
                (80, 101): ("Strong Buy", "green"),
                (70, 80): ("Buy", "lightgreen"),
                (60, 70): ("Hold", "yellow"),
                (50, 60): ("Neutral", "orange"),
                (0, 50): ("Sell", "red")
            }
            for (lower, upper), (rec, clr) in recommendation_map.items():
                if lower <= rating < upper:
                    recommendation, color = rec, clr
                    break
        elif rating == "N/A":
             pass # Keep default N/A and grey
        else:
             st.warning(f"Unexpected rating format: {rating}")


        st.markdown(f"<h3 style='color: {color}; text-shadow: 1px 1px 2px #333;'>{recommendation}</h3>", unsafe_allow_html=True)


def display_strategy_section(result_data, section_name):
    """Display entry or exit strategy information, handling potential variations in keys."""
    section_key_base = section_name.lower()
    possible_keys = [
        f"{section_key_base}_strategy",
        f"{section_key_base} strategy", # With space
        f"preliminary_{section_key_base}_strategy" # From analysis doc
    ]
    strategy = None

    if not result_data:
        st.write(f"No {section_key_base} strategy information available (no data).")
        return

    # Look for possible keys
    for key in possible_keys:
        if key in result_data:
            strategy = result_data[key]
            break
        # Check case-insensitively as a fallback
        for data_key in result_data.keys():
            if data_key.lower() == key:
                 strategy = result_data[data_key]
                 break
        if strategy:
            break

    if strategy:
        st.markdown("---") # Add separator
        if isinstance(strategy, dict):
            for key, value in strategy.items():
                # Format key nicely
                display_key = key.replace('_', ' ').title()
                if isinstance(value, list):
                    st.markdown(f"**{display_key}:**")
                    if value:
                        for item in value:
                            st.markdown(f"- {item}")
                    else:
                        st.markdown("- *None specified*")
                elif value is not None:
                    st.markdown(f"**{display_key}:** {value}")
                else:
                     st.markdown(f"**{display_key}:** *N/A*")
        elif isinstance(strategy, str):
            # If strategy is just a string, display it
            st.write(strategy)
        else:
             st.write(f"Unexpected format for {section_key_base} strategy.")
    else:
        st.write(f"No {section_key_base} strategy information available.")


@st.cache_data(ttl=DAY_TTL) # Cache the combined data fetching
def fetch_stock_data(symbol, period):
    """Fetch basic stock data, news, press releases, and technical indicators."""
    try:
        nasdaq_data = fetch_nasdaq_data() # Fetches all stocks
        stock_data = nasdaq_data[nasdaq_data["symbol"] == symbol.upper()] if not nasdaq_data.empty else pd.DataFrame()

        news = fetch_stock_news(symbol)
        news_df = pd.DataFrame([json.loads(item) for item in news]) if news else pd.DataFrame()

        press_releases = fetch_stock_press_releases(symbol)
        press_df = pd.DataFrame([json.loads(item) for item in press_releases]) if press_releases else pd.DataFrame()

        # Fetch indicators for the full period needed for calculation, but chart might show 'days'
        # Note: fetch_technical_indicators needs enough 'period' data for calculations like SMA100
        indicators = fetch_technical_indicators(symbol, period=max(period, 150), days=period) # Ensure enough data for calculation

        # Fetch historical data separately for the exact period requested for display consistency
        historical_data = fetch_historical_quotes(symbol, period=period) 
        
        # Add historical quotes into indicators dict if available
        if historical_data:
            df = prepare_dataframe(historical_data, date_format="%m/%d/%Y")
            if not df.empty:
                 # Ensure index is datetime before converting
                if not pd.api.types.is_datetime64_any_dtype(df.index):
                    df.index = pd.to_datetime(df.index)
                df = df.sort_index()
                # Convert Timestamp keys to string for JSON compatibility if needed later
                # historical_dict = {k.strftime('%Y-%m-%d %H:%M:%S'): v for k, v in df.to_dict("index").items()}
                indicators["historical_quotes"] = df.to_dict("index") # Keep as dict with datetime index for charting

        return nasdaq_data, stock_data, news_df, press_df, indicators

    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {e}")
        # Return empty structures on error
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}


# Main Dashboard UI
def main():
    st.title("📈 QSBets Stock Analysis Dashboard")

    # --- Sidebar ---
    st.sidebar.header("⚙️ Controls")
    # Load results first to populate symbol list
    results, latest_results_file = load_results()
    available_symbols = sorted([res.get("symbol") for res in results if res.get("symbol")]) or ["AAPL"]
    
    # Use selectbox for symbols found in results
    default_symbol = "AAPL" if "AAPL" in available_symbols else available_symbols[0] if available_symbols else "AAPL"
    selected_symbol_sidebar = st.sidebar.selectbox("Select Stock Symbol", available_symbols, index=available_symbols.index(default_symbol) if default_symbol in available_symbols else 0)
    
    # Allow entering a new symbol
    manual_symbol = st.sidebar.text_input("Or Enter Symbol Manually", value=selected_symbol_sidebar).upper()
    
    # Decide which symbol to use
    symbol = manual_symbol if manual_symbol != selected_symbol_sidebar else selected_symbol_sidebar
    
    period = st.sidebar.slider("Select Chart Period (days)", min_value=30, max_value=365, value=150, step=10)
    
    st.sidebar.markdown("---")
    st.sidebar.info(f"Current Date: {datetime.now().strftime('%Y-%m-%d')}")
    if latest_results_file:
        st.sidebar.markdown(f"**Latest Results:** `{latest_results_file}`")

    # --- Data Fetching ---
    # Use the selected symbol (either from selectbox or manual input)
    nasdaq_data, stock_data, news_df, press_df, indicators = fetch_stock_data(symbol, period)

    # --- Main Content Area ---
    
    # --- Stock Info & News ---
    st.header(f"📊 {symbol} Overview")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Key Info")
        if not stock_data.empty:
            st.metric("Last Price", stock_data['lastsale'].iloc[0])
            st.metric("Market Cap", stock_data['marketCap'].iloc[0])
            st.metric("Sector", stock_data['sector'].iloc[0])
            st.metric("Industry", stock_data['industry'].iloc[0])
        else:
            st.warning(f"No basic stock data found for {symbol} in Nasdaq screener.")

    with col2:
        st.subheader("Recent Activity")
        # Display news and press releases in tabs
        news_tab, press_tab = st.tabs(["News", "Press Releases"])
        with news_tab:
            if not news_df.empty:
                st.dataframe(news_df[['created', 'title', 'publisher']], height=200)
            else:
                st.write("No recent news available.")
        with press_tab:
            if not press_df.empty:
                st.dataframe(press_df[['created', 'title', 'publisher']], height=200)
            else:
                st.write("No recent press releases available.")

    st.markdown("---")

    # --- Technical Analysis Chart & Key Indicators ---
    st.header(f"📈 Technical Analysis ({symbol} - {period} days)")
    if indicators and 'rsi' in indicators: # Check if indicators were fetched
        # Display key indicators summary above the chart
        display_key_indicators(indicators)
        st.markdown("---")
        
        # Create and display technical chart
        fig = create_technical_chart(indicators)
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.warning(f"Could not fetch or display technical indicators for {symbol}.")

    st.markdown("---")

    # --- Analysis & Consultation Tabs ---
    st.header("📝 Analysis & Consultation")
    
    # Load analysis doc and consultation result for the selected symbol
    analysis_data, analysis_file_name = load_analysis_doc(symbol)
    consultation_result_data = None
    if latest_results_file:
        results_full_path = os.path.join("./results", latest_results_file) # Reconstruct full path if needed
        consultation_result_data = load_result_for_symbol(results_full_path, symbol)

    tab_analysis, tab_consultation = st.tabs(["Analysis Report", "Consultation Results"])

    with tab_analysis:
        if analysis_data:
            st.success(f"Loaded Analysis Report: `{analysis_file_name}`")
            
            # Company Description
            st.subheader("Company Description")
            st.write(analysis_data.get("description", "*No description available*"))
            st.markdown("---")

            # Key Metrics & Rating
            col1, col2, col3 = st.columns(3)
            with col1:
                st.subheader("Stock Metrics")
                meta = analysis_data.get("meta", {})
                st.metric("Symbol", meta.get("symbol", "N/A"))
                st.metric("Name", meta.get("name", "N/A"))
                st.metric("Last Price", meta.get("lastsale", "N/A"))
                mcap = meta.get('marketCap')
                st.metric("Market Cap", f"${mcap:,.0f}" if isinstance(mcap, (int, float)) else "N/A")
                st.metric("Industry", meta.get("industry", "N/A"))
                st.metric("Sector", meta.get("sector", "N/A"))
            
            with col2:
                st.subheader("Key Technicals (from report)")
                tech_indicators = analysis_data.get("technical_indicators", {})
                # Safely access nested dicts/values
                rsi_val = tech_indicators.get('rsi', 'N/A')
                macd_dict = tech_indicators.get('macd', {})
                macd_val = macd_dict.get('macd', 'N/A') if isinstance(macd_dict, dict) else 'N/A'
                sma20_val = tech_indicators.get('sma_20', 'N/A')
                
                st.metric("RSI", f"{rsi_val:.2f}" if isinstance(rsi_val, (int, float)) else 'N/A')
                st.metric("MACD", f"{macd_val:.2f}" if isinstance(macd_val, (int, float)) else 'N/A')
                st.metric("SMA-20", f"{sma20_val:.2f}" if isinstance(sma20_val, (int, float)) else 'N/A')
            
            with col3:
                st.subheader("Preliminary Rating (from report)")
                prelim_rating = analysis_data.get("preliminary_rating", {})
                st.metric("Rating", prelim_rating.get("rating", "N/A"))
                st.metric("Confidence", f"{prelim_rating.get('confidence', 'N/A')}/5")
                st.metric("Technical Score", prelim_rating.get("technical_score", "N/A"))
                st.metric("Fundamental Score", prelim_rating.get("fundamental_score", "N/A"))
            
            st.markdown("---")
            
            # Revenue & Earnings
            st.subheader("Revenue & Earnings (from report)")
            revenue_data = analysis_data.get("revenue_earnings", [])
            if revenue_data:
                try:
                    df_revenue = pd.DataFrame(revenue_data)
                    st.dataframe(df_revenue)
                except Exception as e:
                    st.warning(f"Could not display revenue data: {e}")
                    st.write(revenue_data) # Show raw data if DataFrame fails
            else:
                st.write("*No revenue data available in report*")
            
            st.markdown("---")

            # Institutional Holdings
            st.subheader("Institutional Holdings (from report)")
            inst_holdings = analysis_data.get("institutional_holdings", {})
            if inst_holdings:
                ownership = inst_holdings.get("ownership_summary", {})
                if ownership: # Check if ownership dict exists
                    cols = st.columns(len(ownership))
                    i = 0
                    for key, item in ownership.items():
                         if isinstance(item, dict): # Ensure item is a dict
                            with cols[i]:
                                st.metric(item.get("label", key).replace(":", ""), item.get("value", "N/A"))
                                i += 1
                         if i >= len(cols): break # Avoid index error if more items than columns

                st.write("**Key Institutional Transactions:**")
                transactions = inst_holdings.get("holdings_transactions", []) # Use correct key
                if transactions:
                    try:
                        df_trans = pd.DataFrame(transactions)
                        st.dataframe(df_trans)
                    except Exception as e:
                         st.warning(f"Could not display transactions data: {e}")
                         st.write(transactions)
                else:
                    st.write("*No key transactions listed in report*")
            else:
                st.write("*No institutional holdings data available in report*")
            
            st.markdown("---")

            # Explanations & Strategy
            st.subheader("Analysis Explanations (from report)")
            explanations = analysis_data.get("preliminary_rating", {}).get("explanations", [])
            if explanations:
                for exp in explanations:
                    st.markdown(f"- {exp}")
            else:
                st.write("*No explanations provided in report*")

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Entry Strategy (from report)")
                display_strategy_section(analysis_data, "preliminary_entry") # Use base name
            with col2:
                st.subheader("Exit Strategy (from report)")
                display_strategy_section(analysis_data, "preliminary_exit") # Use base name
        else:
            st.warning(f"No analysis report found for {symbol}")

    with tab_consultation:
        if consultation_result_data:
            st.success(f"Loaded Consultation Results from: `{latest_results_file}`")
            
            # Recommendation Info
            display_recommendation_info(consultation_result_data)
            st.markdown("---")
            
            # Reasoning
            st.subheader("Analysis Reasoning")
            st.write(consultation_result_data.get("reasoning", "*No reasoning provided*"))
            st.markdown("---")
            
            # Bullish/Bearish Factors
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Bullish Factors")
                bullish = consultation_result_data.get("bullish_factors", [])
                if bullish:
                    for factor in bullish:
                        st.markdown(f"✅ {factor}")
                else:
                    st.write("*None listed*")
            with col2:
                st.subheader("Bearish Factors")
                bearish = consultation_result_data.get("bearish_factors", [])
                if bearish:
                    for factor in bearish:
                        st.markdown(f"⚠️ {factor}")
                else:
                    st.write("*None listed*")
            st.markdown("---")
            
            # Macro Impact
            st.subheader("Macroeconomic Impact")
            st.write(consultation_result_data.get("macro_impact", "*No macroeconomic impact analysis provided*"))
            st.markdown("---")
            
            # Entry/Exit Strategies
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Entry Strategy")
                display_strategy_section(consultation_result_data, "entry") # Use base name
            with col2:
                st.subheader("Exit Strategy")
                display_strategy_section(consultation_result_data, "exit") # Use base name
        else:
            st.warning(f"No consultation results found for {symbol} in the latest results file.")

    st.markdown("---")

    # --- Comparison Section ---
    st.header("🔄 Compare Recommendations")
    if results: # Check if results were loaded
        compare_symbols = st.multiselect("Select Symbols to Compare", available_symbols, default=available_symbols[:min(3, len(available_symbols))]) # Default to first 3

        if compare_symbols:
            compare_data = [res for res in results if res.get("symbol") in compare_symbols]
            
            if compare_data:
                # Create DataFrame for comparison
                compare_rows = []
                for res in compare_data:
                    exit_strategy = res.get("exit_strategy", {}) if isinstance(res.get("exit_strategy"), dict) else {}
                    compare_rows.append({
                        "Symbol": res.get("symbol", "N/A"),
                        "Rating": res.get("rating", "N/A"),
                        "Confidence": res.get("confidence", "N/A"),
                        "Profit Target": exit_strategy.get("profit_target", "N/A"),
                        "Stop Loss": exit_strategy.get("stop_loss", "N/A"),
                        "Time Horizon": exit_strategy.get("time_horizon", "N/A")
                    })
                
                compare_df = pd.DataFrame(compare_rows)
                st.dataframe(compare_df)
                
                # Bar chart for ratings (handle non-numeric ratings)
                compare_df_numeric = compare_df.copy()
                compare_df_numeric["Rating"] = pd.to_numeric(compare_df_numeric["Rating"], errors='coerce')
                compare_df_numeric.dropna(subset=["Rating"], inplace=True)

                if not compare_df_numeric.empty:
                    fig_compare = px.bar(
                        compare_df_numeric,
                        x="Symbol",
                        y="Rating",
                        color="Rating",
                        color_continuous_scale=px.colors.sequential.RdYlGn, # Red-Yellow-Green scale
                        range_color=[0, 100], # Explicit range 0-100
                        labels={"Rating": "Recommendation Rating (0-100)"},
                        title="Comparison of Stock Ratings"
                    )
                    fig_compare.update_layout(
                         plot_bgcolor='rgba(30, 30, 30, 0.9)',
                         paper_bgcolor='rgba(30, 30, 30, 1)',
                         font_color='white'
                    )
                    st.plotly_chart(fig_compare, use_container_width=True)
                else:
                    st.warning("No numeric ratings available for comparison chart.")
            else:
                 st.info("Select symbols to compare.")
        else:
            st.info("Select symbols to compare.")
    else:
        st.warning("No results loaded for comparison.")

    # Placeholder for strategy testing
    # st.header("🧪 Strategy Testing and Backtesting")
    # st.write("*(Future Implementation)*")

if __name__ == "__main__":
    main()