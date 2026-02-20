import os
import time
import logging
import signal
import sys
import json
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.positions as positions
from oandapyV20.exceptions import V20Error
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
ACCESS_TOKEN = os.getenv("OANDA_ACCESS_TOKEN")
ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
TRADE_ENV = os.getenv("TRADE_ENV", "practice")
SYMBOL = os.getenv("SYMBOL", "USD_JPY")
TIMEFRAME = os.getenv("TIMEFRAME", "M1")
POSITION_SIZE = int(os.getenv("POSITION_SIZE", "10000"))

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class OandaClient:
    """
    OANDA API Client Wrapper
    Handles connection, data fetching, and order execution with error handling.
    """
    def __init__(self, access_token, account_id, environment="practice"):
        self.account_id = account_id
        self.api = oandapyV20.API(access_token=access_token, environment=environment)

    def fetch_candles(self, instrument, granularity, count=100):
        """
        Fetch historical candle data.
        """
        params = {
            "count": count,
            "granularity": granularity,
            "price": "M"  # Midpoint candles
        }
        try:
            r = instruments.InstrumentsCandles(instrument=instrument, params=params)
            self.api.request(r)
            return r.response['candles']
        except V20Error as e:
            logger.error(f"Error fetching candles: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching candles: {e}")
            return None

    def get_account_details(self):
        """
        Fetch account details to check balance and margin.
        """
        try:
            r = accounts.AccountDetails(accountID=self.account_id)
            self.api.request(r)
            return r.response['account']
        except V20Error as e:
            logger.error(f"Error fetching account details: {e}")
            return None

    def create_order(self, order_body):
        """
        Send an order request to OANDA.
        """
        try:
            r = orders.OrderCreate(accountID=self.account_id, data=order_body)
            self.api.request(r)
            logger.info(f"Order created successfully: {json.dumps(r.response, indent=2)}")
            return r.response
        except V20Error as e:
            logger.error(f"Error creating order: {e}")
            return None

    def get_open_positions(self):
        """
        Fetch open positions to avoid duplicate trades.
        """
        try:
            r = oandapyV20.endpoints.positions.PositionList(accountID=self.account_id)
            self.api.request(r)
            return r.response.get('positions', [])
        except V20Error as e:
            logger.error(f"Error fetching positions: {e}")
            return []

class DataAnalyzer:
    """
    Analyzes market data and calculates technical indicators.
    """
    @staticmethod
    def parse_candles(candles):
        """
        Convert OANDA candle data to pandas DataFrame.
        """
        data = []
        for candle in candles:
            if candle['complete']:
                data.append({
                    'time': candle['time'],
                    'open': float(candle['mid']['o']),
                    'high': float(candle['mid']['h']),
                    'low': float(candle['mid']['l']),
                    'close': float(candle['mid']['c']),
                    'volume': candle['volume']
                })
        df = pd.DataFrame(data)
        df['time'] = pd.to_datetime(df['time'])
        return df

    @staticmethod
    def calculate_technical_indicators(df):
        """
        Calculate SMA, and other indicators.
        Example: SMA 20 and SMA 50 for Golden Cross strategy.
        """
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        
        # RSI (Relative Strength Index)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df

class Trader:
    """
    Core Trading Logic.
    Decides when to buy/sell based on DataAnalyzer results.
    """
    def __init__(self, client):
        self.client = client
        self.position = None # Track current position 'BUY', 'SELL', or None

    def decide_action(self, df):
        """
        Simple Strategy: Golden Cross / Dead Cross with RSI filter.
        Buy: SMA20 crosses above SMA50 and RSI < 70
        Sell: SMA20 crosses below SMA50 and RSI > 30
        """
        if len(df) < 50:
            return None # Not enough data

        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]

        # Check for Crossovers
        golden_cross = (prev_row['SMA_20'] < prev_row['SMA_50']) and (last_row['SMA_20'] > last_row['SMA_50'])
        dead_cross = (prev_row['SMA_20'] > prev_row['SMA_50']) and (last_row['SMA_20'] < last_row['SMA_50'])

        rsi = last_row['RSI']

        if golden_cross and rsi < 70:
            return 'BUY'
        elif dead_cross and rsi > 30:
            return 'SELL'
        
        return None

    def execute_trade(self, signal, current_price):
        """
        Execute trade based on signal with Risk Management.
        """
        if signal not in ['BUY', 'SELL']:
            return

        # Check for existing positions for this symbol
        positions = self.client.get_open_positions()
        for pos in positions:
            if pos['instrument'] == SYMBOL and float(pos['long']['units']) + float(pos['short']['units']) != 0:
                logger.info(f"Position already exists for {SYMBOL}. Skipping trade.")
                return

        logger.info(f"Signal received: {signal} @ {current_price}")

        # Risk Management: Stop Loss and Take Profit (pips)
        # Assuming JPY pair (0.01 = 1 pip)
        sl_pips = 0.20 # 20 pips
        tp_pips = 0.40 # 40 pips
        
        if signal == 'BUY':
            units = POSITION_SIZE
            sl_price = round(current_price - sl_pips, 3)
            tp_price = round(current_price + tp_pips, 3)
        else:
            units = -POSITION_SIZE
            sl_price = round(current_price + sl_pips, 3)
            tp_price = round(current_price - tp_pips, 3)
        
        order_body = {
            "order": {
                "instrument": SYMBOL,
                "units": str(units),
                "type": "MARKET",
                "positionFill": "DEFAULT",
                "takeProfitOnFill": {"price": str(tp_price)},
                "stopLossOnFill": {"price": str(sl_price)}
            }
        }
        
        logger.info(f"Placing {signal} order for {SYMBOL} (Units: {units}, SL: {sl_price}, TP: {tp_price})...")
        response = self.client.create_order(order_body)
        
        if response and 'orderFillTransaction' in response:
            logger.info(f"Order Filled: {response['orderFillTransaction']['id']} @ {response['orderFillTransaction']['price']}")
        else:
            logger.warning("Order not filled or failed.")

def signal_handler(sig, frame):
    """Handle Ctrl+C to exit gracefully."""
    logger.info("Stopping bot...")
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    if not ACCESS_TOKEN or not ACCOUNT_ID:
        logger.error("API credentials missing. Please check .env file.")
        return

    logger.info("Starting OANDA Trading Bot...")
    client = OandaClient(ACCESS_TOKEN, ACCOUNT_ID, TRADE_ENV)
    trader = Trader(client)

    # Initial Connection Check
    account = client.get_account_details()
    if account:
        logger.info(f"Connected to Account: {account['id']} - Balance: {account['balance']}")
    else:
        logger.error("Failed to connect to OANDA API. Exiting.")
        return

    logger.info(f"Monitoring {SYMBOL} on {TIMEFRAME} timeframe.")

    while True:
        try:
            # 1. Fetch Data
            candles = client.fetch_candles(SYMBOL, TIMEFRAME, count=60)
            if not candles:
                time.sleep(10)
                continue

            # 2. Analyze Data
            df = DataAnalyzer.parse_candles(candles)
            df = DataAnalyzer.calculate_technical_indicators(df)

            # 3. Decide & Execute
            # Log latest data for debugging
            latest = df.iloc[-1]
            logger.info(f"Latest: {latest['time']} | Close: {latest['close']} | SMA20: {latest['SMA_20']:.3f} | RSI: {latest['RSI']:.1f}")
            
            signal = trader.decide_action(df)
            if signal:
                trader.execute_trade(signal, latest['close'])
            
            # Sleep for interval (e.g., 60 seconds for 1 min candle)
            # In production, align with candle close time
            time.sleep(60)

        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(10) # Wait before retrying

if __name__ == "__main__":
    main()
