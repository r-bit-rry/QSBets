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

# Apply dark theme styling
st.markdown(
    """
    <style>
    .reportview-container { background: #1e1e1e; color: white; }
    .sidebar .sidebar-content { background: #333333; color: white; }
    .stButton>button { background: #4CAF50; color: white; }
    .stCheckbox>div, .stSelectbox>div, .stSlider>div { color: white; }
    </style>
    """,
    unsafe_allow_html=True
)

# Helper functions
def find_latest_file(directory, pattern, symbol=None):
    """Find the most recent file in the directory that matches the pattern and optionally contains the symbol."""
    files = [f for f in os.listdir(directory) if f.endswith(pattern)]
    files.sort(key=lambda x: x.split('_')[-1].split('.')[0] if '_' in x else '', reverse=True)
    
    if symbol:
        symbol_files = [f for f in files if symbol.lower() in f.lower()]
        if symbol_files:
            return symbol_files[0]
    
    return files[0] if files else None

def load_analysis_doc(symbol):
    """Load the analysis document for a specific symbol."""
    analysis_docs_path = "./analysis_docs"
    files = [f for f in os.listdir(analysis_docs_path) if f.startswith(f"{symbol}_") and f.endswith(".yaml")]
    
    if not files:
        latest_file = find_latest_file(analysis_docs_path, ".yaml")
        if not latest_file:
            return None, None
        file_path = os.path.join(analysis_docs_path, latest_file)
    else:
        files.sort(key=lambda x: x.split('_')[-1].split('.')[0], reverse=True)
        file_path = os.path.join(analysis_docs_path, files[0])
    
    with open(file_path, "r") as file:
        return yaml.safe_load(file), os.path.basename(file_path)

def load_result_for_symbol(results_path, symbol):
    """Find the result for a specific symbol in a results file."""
    with open(results_path, "r") as file:
        results = [json.loads(line) for line in file]
    
    for result in results:
        if result.get("symbol") == symbol:
            return result
    
    return None

def load_results():
    """Load the latest results file."""
    results_path = "./results"
    latest_results_file = find_latest_file(results_path, ".jsonl")
    results = []

    if latest_results_file:
        full_path = os.path.join(results_path, latest_results_file)
        with open(full_path, "r") as file:
            results = [json.loads(line) for line in file]
        st.sidebar.success(f"Loaded results file: {latest_results_file}")
    else:
        st.sidebar.error("No results files found")
        results = [{"symbol": "AAPL"}]  # Default if no results found
        
    return results, latest_results_file

def create_technical_chart(indicators):
    """Create a comprehensive technical analysis chart from indicators."""
    # Create figure with subplots: price/volume, trend indicators, oscillators, momentum
    fig = make_subplots(rows=4, cols=1, 
                        shared_xaxes=True,
                        vertical_spacing=0.05,
                        row_heights=[0.4, 0.2, 0.2, 0.2],
                        subplot_titles=("Price & Volume", "Trend Indicators", "Oscillators", "Momentum"))
    
    x_range = list(range(len(indicators['rsi'])))
    
    # 1. Price chart (if available) and volume
    historical_quotes = indicators.get('historical_quotes', {})
    if historical_quotes:
        quotes_df = pd.DataFrame.from_dict(historical_quotes, orient='index')
        quotes_df.index = pd.to_datetime(quotes_df.index)
        fig.add_trace(
            go.Candlestick(
                x=quotes_df.index,
                open=quotes_df['open'],
                high=quotes_df['high'],
                low=quotes_df['low'],
                close=quotes_df['close'],
                name='Price'
            ),
            row=1, col=1
        )
    else:
        # If no historical quotes, just use the last available closing prices
        close_prices = indicators.get('sma_20', [])
        if close_prices:
            fig.add_trace(
                go.Scatter(x=x_range, y=close_prices, mode='lines', name='Price'),
                row=1, col=1
            )
    
    # Volume - Scale to millions for readability
    volume_data = [vol['recent_volume'] / 1000000 for vol in indicators['volume_profile']]
    fig.add_trace(
        go.Bar(x=x_range, y=volume_data, name='Volume (M)', marker_color='rgba(0,0,255,0.3)'),
        row=1, col=1
    )
    
    # Add moving averages to price chart
    for sma, color, dash in [('sma_20', 'blue', 'solid'), ('sma_50', 'orange', 'solid'), ('sma_100', 'green', 'dash')]:
        if sma in indicators:
            fig.add_trace(go.Scatter(x=x_range, y=indicators[sma], mode='lines', 
                                    name=sma.upper(), line=dict(color=color, dash=dash)), row=1, col=1)
    
    # 2. Trend indicators
    # Bollinger Bands
    upper_band = [bb['upper'] for bb in indicators['bollinger_bands']]
    middle_band = [bb['middle'] for bb in indicators['bollinger_bands']]
    lower_band = [bb['lower'] for bb in indicators['bollinger_bands']]
    
    fig.add_trace(go.Scatter(x=x_range, y=upper_band, mode='lines', 
                            line=dict(color='rgba(250,128,114,0.7)'),
                            name='Upper BB'), row=2, col=1)
    fig.add_trace(go.Scatter(x=x_range, y=middle_band, mode='lines', 
                            line=dict(color='rgba(0,128,0,0.7)'),
                            name='Middle BB'), row=2, col=1)
    fig.add_trace(go.Scatter(x=x_range, y=lower_band, mode='lines', 
                            line=dict(color='rgba(250,128,114,0.7)'),
                            fill='tonexty', fillcolor='rgba(250,128,114,0.1)',
                            name='Lower BB'), row=2, col=1)
    
    # Add EMA
    if 'ema_20' in indicators:
        fig.add_trace(go.Scatter(x=x_range, y=indicators['ema_20'], mode='lines', 
                                name='EMA 20', line=dict(color='purple')), row=2, col=1)
    
    # ADX - Add to trend indicators panel
    if 'adx' in indicators:
        fig.add_trace(go.Scatter(x=x_range, y=indicators['adx'], mode='lines', 
                                name='ADX', line=dict(color='brown')), row=2, col=1)
        # Add reference line at ADX = 25 (strong trend)
        fig.add_shape(type="line", x0=0, x1=len(x_range)-1, y0=25, y1=25,
                    line=dict(color="brown", width=1, dash="dash"),
                    row=2, col=1)
    
    # 3. Oscillators - RSI, Stochastic, CCI
    # RSI
    fig.add_trace(go.Scatter(x=x_range, y=indicators['rsi'], 
                            mode='lines', name='RSI', line=dict(color='blue')), row=3, col=1)
    
    # Add RSI reference lines at 70 and 30
    fig.add_shape(type="line", x0=0, x1=len(x_range)-1, y0=70, y1=70,
                line=dict(color="red", width=1, dash="dash"),
                row=3, col=1)
    fig.add_shape(type="line", x0=0, x1=len(x_range)-1, y0=30, y1=30,
                line=dict(color="green", width=1, dash="dash"),
                row=3, col=1)
    
    # Stochastic
    if 'stochastic_14_3_3' in indicators:
        stoch_k = [stoch['stochastic_k'] for stoch in indicators['stochastic_14_3_3']]
        stoch_d = [stoch['stochastic_d'] for stoch in indicators['stochastic_14_3_3']]
        fig.add_trace(go.Scatter(x=x_range, y=stoch_k, mode='lines', 
                                name='Stoch %K', line=dict(color='orange')), row=3, col=1)
        fig.add_trace(go.Scatter(x=x_range, y=stoch_d, mode='lines', 
                                name='Stoch %D', line=dict(color='green')), row=3, col=1)
        
        # Add Stochastic reference lines at 80 and 20
        fig.add_shape(type="line", x0=0, x1=len(x_range)-1, y0=80, y1=80,
                    line=dict(color="red", width=1, dash="dash"),
                    row=3, col=1)
        fig.add_shape(type="line", x0=0, x1=len(x_range)-1, y0=20, y1=20,
                    line=dict(color="green", width=1, dash="dash"),
                    row=3, col=1)
    
    # CCI
    if 'cci' in indicators:
        fig.add_trace(go.Scatter(x=x_range, y=indicators['cci'], mode='lines', 
                                name='CCI', line=dict(color='purple')), row=3, col=1)
        # Add CCI reference lines at +100 and -100
        fig.add_shape(type="line", x0=0, x1=len(x_range)-1, y0=100, y1=100,
                    line=dict(color="red", width=1, dash="dash"),
                    row=3, col=1)
        fig.add_shape(type="line", x0=0, x1=len(x_range)-1, y0=-100, y1=-100,
                    line=dict(color="green", width=1, dash="dash"),
                    row=3, col=1)
    
    # 4. Momentum - MACD
    macd_values = [macd['macd'] for macd in indicators['macd']]
    signal_values = [macd['signal'] for macd in indicators['macd']]
    hist_values = [macd['hist'] for macd in indicators['macd']]
    
    fig.add_trace(go.Scatter(x=x_range, y=macd_values, mode='lines', 
                            name='MACD', line=dict(color='blue')), row=4, col=1)
    fig.add_trace(go.Scatter(x=x_range, y=signal_values, mode='lines', 
                            name='Signal', line=dict(color='red')), row=4, col=1)
    
    # Add histogram bars for MACD
    colors = ['green' if val >= 0 else 'red' for val in hist_values]
    fig.add_trace(go.Bar(x=x_range, y=hist_values, name='Histogram', 
                        marker_color=colors, opacity=0.6), row=4, col=1)
    
    # Add zero line for MACD
    fig.add_shape(type="line", x0=0, x1=len(x_range)-1, y0=0, y1=0,
                line=dict(color="black", width=1),
                row=4, col=1)
    
    # Update layout
    fig.update_layout(
        height=1000,
        title_text=f"Technical Analysis Dashboard",
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    
    # Set y-axis titles and ranges
    fig.update_yaxes(title_text="Price", row=1, col=1, autorange=True)
    fig.update_yaxes(title_text="BB & ADX", row=2, col=1, autorange=True)
    fig.update_yaxes(title_text="Oscillators", row=3, col=1, range=[0, 100])
    fig.update_yaxes(title_text="MACD", row=4, col=1, autorange=True)
    
    return fig

def display_key_indicators(indicators):
    """Display key indicator values in a well-formatted way."""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Trend Indicators")
        st.metric("RSI (14)", f"{indicators['rsi'][-1]:.2f}", 
                  delta="Overbought" if indicators['rsi'][-1] > 70 else 
                  "Oversold" if indicators['rsi'][-1] < 30 else "Neutral")
        if 'adx' in indicators:
            st.metric("ADX (14)", f"{indicators['adx'][-1]:.2f}", 
                     delta="Strong Trend" if indicators['adx'][-1] > 25 else "Weak Trend")
    
    with col2:
        st.subheader("Momentum")
        if 'macd' in indicators:
            macd_last = indicators['macd'][-1]
            st.metric("MACD", f"{macd_last['macd']:.2f}", 
                     delta=f"Bullish" if macd_last['hist'] > 0 else "Bearish")
            st.metric("Signal Line", f"{macd_last['signal']:.2f}")
    
    with col3:
        st.subheader("Volatility")
        if 'atr' in indicators:
            st.metric("ATR (14)", f"{indicators['atr'][-1]:.2f}")
        if 'bollinger_bands' in indicators:
            bb = indicators['bollinger_bands'][-1]
            bb_width = (bb['upper'] - bb['lower']) / bb['middle'] * 100
            st.metric("BB Width", f"{bb_width:.2f}%", 
                     delta="High Volatility" if bb_width > 5 else "Low Volatility")

def display_recommendation_info(result_data):
    """Display the recommendation information for a stock."""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Rating")
        st.metric("Overall Rating", result_data.get("rating", "N/A"))
        st.metric("Confidence", f"{result_data.get('confidence', 'N/A')}/5")
    
    with col2:
        st.subheader("Recommendation")
        rating = result_data.get("rating", 0)
        recommendation_map = {
            (80, 101): ("Strong Buy", "green"),
            (70, 80): ("Buy", "lightgreen"),
            (60, 70): ("Hold", "yellow"),
            (50, 60): ("Neutral", "orange"),
            (0, 50): ("Sell", "red")
        }
        
        for (lower, upper), (rec, color) in recommendation_map.items():
            if lower <= rating < upper:
                recommendation, color = rec, color
                break
        else:
            recommendation, color = "N/A", "gray"
            
        st.markdown(f"<h3 style='color: {color};'>{recommendation}</h3>", unsafe_allow_html=True)

def display_strategy_section(result_data, section_name):
    """Display entry or exit strategy information."""
    section_key = f"{section_name.lower()}_strategy"
    strategy = None
    
    # Look for key with and without spaces
    for key in result_data.keys():
        if key.strip() == section_key:
            strategy = result_data[key]
            break
    
    if strategy is None:
        strategy = result_data.get(section_key, {})
    
    if strategy:
        if isinstance(strategy, dict):
            for key, value in strategy.items():
                if isinstance(value, list):
                    st.write(f"**{key.replace('_', ' ').title()}:**")
                    for item in value:
                        st.write(f"- {item}")
                else:
                    st.write(f"**{key.replace('_', ' ').title()}:** {value}")
        else:
            # If strategy is a string, just display it directly
            st.write(strategy)
    else:
        st.write(f"No {section_name.lower()} strategy information available")

def fetch_stock_data(symbol, period):
    """Fetch basic stock data and related indicators."""
    nasdaq_data = fetch_nasdaq_data()
    stock_data = nasdaq_data[nasdaq_data["symbol"] == symbol.upper()]
    
    news = fetch_stock_news(symbol) if not stock_data.empty else []
    news_df = pd.DataFrame([json.loads(item) for item in news]) if news else pd.DataFrame()
    
    press_releases = fetch_stock_press_releases(symbol) if not stock_data.empty else []
    press_df = pd.DataFrame([json.loads(item) for item in press_releases]) if press_releases else pd.DataFrame()
    
    indicators = fetch_technical_indicators(symbol, period, days=30)
    historical_data = fetch_historical_quotes(symbol, period)
    df = prepare_dataframe(historical_data, date_format="%m/%d/%Y")
    
    # Return historical quotes as part of indicators to enable better charting
    historical_dict = df.to_dict('index')
    indicators['historical_quotes'] = historical_dict
    
    return nasdaq_data, stock_data, news_df, press_df, indicators

# Main Dashboard UI
def main():
    # Sidebar for user input
    st.sidebar.header("Stock Analysis")
    symbol = st.sidebar.text_input("Enter stock symbol", value="AAPL")
    period = st.sidebar.slider("Select period (days)", min_value=5, max_value=365, value=150)
    
    # Load results for available symbols
    results, latest_results_file = load_results()
    available_symbols = [res.get("symbol") for res in results if res.get("symbol")] or ["AAPL"]

    # Fetch stock data
    nasdaq_data, stock_data, news_df, press_df, indicators = fetch_stock_data(symbol, period)

    # Main content area - display stock data
    st.header(f"Stock Data for {symbol}")
    if not stock_data.empty:
        st.write(stock_data)
    else:
        st.write("No data found for the specified symbol.")

    # Display news and press releases in tabs to save space
    news_tab, press_tab = st.tabs(["News", "Press Releases"])
    with news_tab:
        st.header(f"News for {symbol}")
        st.write(news_df if not news_df.empty else "No news available.")
        
    with press_tab:
        st.header(f"Press Releases for {symbol}")
        st.write(press_df if not press_df.empty else "No press releases available.")

    # Technical Analysis Section
    st.header(f"Technical Indicators for {symbol}")
    if indicators:
        # Create and display technical chart
        fig = create_technical_chart(indicators)
        st.plotly_chart(fig, use_container_width=True)
        
        # Show key indicators summary
        display_key_indicators(indicators)
    else:
        st.warning(f"No technical indicators available for {symbol}")

    # Analysis Dashboard
    st.header("Stock Analysis Dashboard")
    
    # Create tabs to separate different types of information
    tab1, tab2, tab3 = st.tabs(["Stock Selection", "Analysis Report", "Consultation Results"])

    with tab1:
        # Stock selection with defined available_symbols
        selected_symbol = st.selectbox(
            "Select Stock Symbol", 
            available_symbols,
            key="stock_selector"
        )
        
        # Display basic stock info
        st.subheader(f"Selected Stock: {selected_symbol}")
        
        # Try to get stock data from nasdaq_data
        if 'nasdaq_data' in locals():
            stock_info = nasdaq_data[nasdaq_data["symbol"] == selected_symbol.upper()]
            if not stock_info.empty:
                st.write("Stock Information:")
                st.write(stock_info)
            else:
                st.write("No basic data available for this stock.")

    with tab2:
        st.header(f"Analysis Report for {selected_symbol}")
        
        # Load analysis doc for selected symbol
        analysis_data, file_name = load_analysis_doc(selected_symbol)
        
        if analysis_data:
            st.success(f"Loaded report: {file_name}")
            
            # Display company description
            st.subheader("Company Description")
            st.write(analysis_data.get("description", "No description available"))
            
            # Display key metrics in columns
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader("Stock Metrics")
                meta = analysis_data.get("meta", {})
                metrics_data = {
                    "Symbol": meta.get("symbol"),
                    "Name": meta.get("name"),
                    "Last Price": meta.get("lastsale"),
                    "Market Cap": f"${meta.get('marketCap'):,.0f}" if meta.get('marketCap') else None,
                    "Industry": meta.get("industry"),
                    "Sector": meta.get("sector")
                }
                for key, value in metrics_data.items():
                    if value:
                        st.metric(key, value)
            
            with col2:
                st.subheader("Technical Indicators")
                tech_indicators = analysis_data.get("technical_indicators", {})
                st.metric("RSI", f"{tech_indicators.get('rsi', 'N/A'):.2f}" if isinstance(tech_indicators.get('rsi'), (int, float)) else 'N/A')
                if 'macd' in tech_indicators:
                    st.metric("MACD", f"{tech_indicators['macd'].get('macd', 'N/A'):.2f}" if isinstance(tech_indicators['macd'].get('macd'), (int, float)) else 'N/A')
                st.metric("SMA-20", f"{tech_indicators.get('sma_20', 'N/A'):.2f}" if isinstance(tech_indicators.get('sma_20'), (int, float)) else 'N/A')
            
            with col3:
                st.subheader("Analysis Rating")
                prelim_rating = analysis_data.get("preliminary_rating", {})
                st.metric("Rating", prelim_rating.get("rating", "N/A"))
                st.metric("Confidence", f"{prelim_rating.get('confidence', 'N/A')}/5")
                st.metric("Technical Score", prelim_rating.get("technical_score", "N/A"))
                st.metric("Fundamental Score", prelim_rating.get("fundamental_score", "N/A"))
            
            # Display revenue and earnings
            st.subheader("Revenue & Earnings")
            revenue_data = analysis_data.get("revenue_earnings", [])
            if revenue_data:
                # Handle different data structures that might come in revenue_data
                if isinstance(revenue_data, dict):
                    # If it's a dictionary, convert to DataFrame with keys as index
                    df_revenue = pd.DataFrame([revenue_data]).T
                    df_revenue.columns = ['Value']
                    # Reset the index to make the dictionary keys a column
                    df_revenue = df_revenue.reset_index().rename(columns={'index': 'Metric'})
                elif isinstance(revenue_data, list) and all(isinstance(item, dict) for item in revenue_data):
                    # If it's a list of dictionaries, we can create the DataFrame directly
                    df_revenue = pd.DataFrame(revenue_data)
                else:
                    # For simple list or scalar values, create a single column DataFrame with an index
                    df_revenue = pd.DataFrame({'Value': revenue_data})
                
                st.dataframe(df_revenue)
            else:
                st.write("No revenue data available")
            
            # Display institutional holdings
            st.subheader("Institutional Holdings")
            inst_holdings = analysis_data.get("institutional_holdings", {})
            if inst_holdings:
                ownership = inst_holdings.get("ownership_summary", {})
                for key, item in ownership.items():
                    st.metric(item.get("label", key), item.get("value", "N/A"))
                
                st.write("Key Institutional Investors:")
                transactions = inst_holdings.get("key_transactions", [])
                if transactions:
                    df_trans = pd.DataFrame(transactions)
                    st.dataframe(df_trans)
            else:
                st.write("No institutional holdings data available")
            
            # Display explanations and strategy
            st.subheader("Analysis Explanations")
            explanations = prelim_rating.get("explanations", [])
            if explanations:
                for exp in explanations:
                    st.write(f"- {exp}")
            
            # Entry and exit strategy
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Entry Strategy")
                entry = analysis_data.get("preliminary_entry_strategy", {})
                if entry:
                    st.write(f"Entry Price: {entry.get('entry_price', 'N/A')}")
                    st.write(f"Entry Timing: {entry.get('entry_timing', 'N/A')}")
                    st.write("Technical Indicators:")
                    for indicator in entry.get("technical_indicators", []):
                        st.write(f"- {indicator}")
            
            with col2:
                st.subheader("Exit Strategy")
                exit_strat = analysis_data.get("preliminary_exit_strategy", {})
                if exit_strat:
                    st.write(f"Profit Target: {exit_strat.get('profit_target', 'N/A')}")
                    st.write(f"Stop Loss: {exit_strat.get('stop_loss', 'N/A')}")
                    st.write(f"Time Horizon: {exit_strat.get('time_horizon', 'N/A')}")
                    st.write("Exit Conditions:")
                    for condition in exit_strat.get("exit_conditions", []):
                        st.write(f"- {condition}")
        else:
            st.warning(f"No analysis report found for {selected_symbol}")

    with tab3:
        st.header(f"Consultation Results for {selected_symbol}")
        
        # Find the latest results file
        results_path = "./results"
        if latest_results_file:
            full_path = os.path.join(results_path, latest_results_file)
            st.success(f"Loaded results: {latest_results_file}")
            
            # Load the result for the selected symbol
            result_data = load_result_for_symbol(full_path, selected_symbol)
            
            if result_data:
                # Display recommendation information
                display_recommendation_info(result_data)
                
                # Display reasoning
                st.subheader("Analysis Reasoning")
                st.write(result_data.get("reasoning", "No reasoning provided"))
                
                # Display bullish and bearish factors in columns
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Bullish Factors")
                    bullish = result_data.get("bullish_factors", [])
                    for factor in bullish:
                        st.write(f"✅ {factor}")
                
                with col2:
                    st.subheader("Bearish Factors")
                    bearish = result_data.get("bearish_factors", [])
                    for factor in bearish:
                        st.write(f"⚠️ {factor}")
                
                # Display macro impact
                st.subheader("Macroeconomic Impact")
                st.write(result_data.get("macro_impact", "No macroeconomic impact analysis provided"))
                
                # Display entry and exit strategies
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Entry Strategy")
                    display_strategy_section(result_data, "Enter")
                
                with col2:
                    st.subheader("Exit Strategy")
                    display_strategy_section(result_data, "Exit")
            else:
                st.warning(f"No consultation results found for {selected_symbol}")
        else:
            st.error("No results files found")

    # Comparison section
    st.header("Compare Recommendations")
    compare_symbols = st.multiselect("Select Symbols to Compare", [res["symbol"] for res in results])

    if compare_symbols:
        compare_data = [res for res in results if res["symbol"] in compare_symbols]
        
        # Create a DataFrame for easier comparison
        compare_df = pd.DataFrame([{
            "Symbol": res["symbol"],
            "Rating": res["rating"],
            "Confidence": res["confidence"],
            "Profit Target": res.get("exit_strategy", {}).get("profit_target", "N/A") if isinstance(res.get("exit_strategy"), dict) else "N/A",
            "Stop Loss": res.get("exit_strategy", {}).get("stop_loss", "N/A") if isinstance(res.get("exit_strategy"), dict) else "N/A",
            "Time Horizon": res.get("exit_strategy", {}).get("time_horizon", "N/A") if isinstance(res.get("exit_strategy"), dict) else "N/A"
        } for res in compare_data])
        
        st.dataframe(compare_df)
        
        # Bar chart for ratings
        fig = px.bar(
            compare_df,
            x="Symbol",
            y="Rating",
            color="Rating",
            color_continuous_scale=["red", "orange", "yellow", "lightgreen", "green"],
            labels={"Rating": "Recommendation Rating"},
            title="Comparison of Stock Ratings"
        )
        st.plotly_chart(fig, use_container_width=True)

    # Placeholder for strategy testing and backtesting
    st.header("Strategy Testing and Backtesting")
    st.write("This section will be used to test and backtest market strategies.")

if __name__ == "__main__":
    main()
