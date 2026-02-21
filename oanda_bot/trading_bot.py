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

    def fetch_candles(self, instrument, granularity, count=100, _from=None, to=None):
        try:
            if _from and to:
                # Pagination required for long date ranges
                all_candles = []
                current_from = _from
                import pandas as pd
                
                # Convert `to` to timestamp for comparison
                to_date = pd.to_datetime(to)
                
                while True:
                    params = {
                        "granularity": granularity,
                        "price": "M",
                        "from": current_from,
                        "includeFirst": "False" if len(all_candles) > 0 else "True",
                        "count": 5000 # Max allowed by OANDA
                    }
                    r = instruments.InstrumentsCandles(instrument=instrument, params=params)
                    self.api.request(r)
                    candles = r.response.get('candles', [])
                    
                    if not candles:
                        break
                        
                    # Add candles to our list, stopping if we pass the `to` date
                    for c in candles:
                        c_time = pd.to_datetime(c['time'])
                        if c_time <= to_date:
                            all_candles.append(c)
                            
                    last_time = pd.to_datetime(candles[-1]['time'])
                    
                    if last_time >= to_date or len(candles) < 5000:
                        break
                        
                    # Next request starts from the last candle's time
                    current_from = candles[-1]['time']
                    
                return all_candles
            else:
                # Standard request
                params = {
                    "granularity": granularity,
                    "price": "M"
                }
                if _from: params["from"] = _from
                if to: params["to"] = to
                if not _from and not to: params["count"] = count
                
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
        try:
            r = accounts.AccountDetails(accountID=self.account_id)
            self.api.request(r)
            return r.response['account']
        except V20Error as e:
            logger.error(f"Error fetching account details: {e}")
            return None

    def create_order(self, order_body):
        try:
            r = orders.OrderCreate(accountID=self.account_id, data=order_body)
            self.api.request(r)
            logger.info(f"Order created successfully: {json.dumps(r.response, indent=2)}")
            return r.response
        except V20Error as e:
            logger.error(f"Error creating order: {e}")
            return None

    def get_open_positions(self):
        try:
            r = oandapyV20.endpoints.positions.PositionList(accountID=self.account_id)
            self.api.request(r)
            return r.response.get('positions', [])
        except V20Error as e:
            logger.error(f"Error fetching positions: {e}")
            return []

class DataAnalyzer:
    @staticmethod
    def parse_candles(candles):
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
    def calculate_technical_indicators(df, sma_short=20, sma_long=50, rsi_period=14):
        df['SMA_short'] = df['close'].rolling(window=sma_short).mean()
        df['SMA_long'] = df['close'].rolling(window=sma_long).mean()
        
        # RSI 
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df

class Trader:
    def __init__(self, client, symbol, position_size, mode="realtime"):
        self.client = client
        self.symbol = symbol
        self.position_size = position_size
        self.mode = mode
        
        # Virtual Wallet for Backtesting
        self.virtual_balance = 3000000.0  # Default starting balance
        self.virtual_positions = []
        self.virtual_trades = []

    def decide_action(self, df):
        if len(df) < 50:
            return None 

        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]

        golden_cross = (prev_row['SMA_short'] < prev_row['SMA_long']) and (last_row['SMA_short'] > last_row['SMA_long'])
        dead_cross = (prev_row['SMA_short'] > prev_row['SMA_long']) and (last_row['SMA_short'] < last_row['SMA_long'])

        rsi = last_row['RSI']

        if golden_cross and rsi < 70:
            return 'BUY'
        elif dead_cross and rsi > 30:
            return 'SELL'
        
        return None

    def execute_trade(self, signal, current_price, timestamp=None):
        if signal not in ['BUY', 'SELL']:
            return

        sl_pips = 0.20 # 20 pips
        tp_pips = 0.40 # 40 pips
        
        if signal == 'BUY':
            units = self.position_size
            sl_price = round(current_price - sl_pips, 3)
            tp_price = round(current_price + tp_pips, 3)
        else:
            units = -self.position_size
            sl_price = round(current_price + sl_pips, 3)
            tp_price = round(current_price - tp_pips, 3)

        if self.mode == "backtest":
            # Very simple virtual executor (does not handle partial fills, just logs the entry)
            # Check if position already exists
            if len(self.virtual_positions) > 0:
                logger.info(f"Position already exists virtually for {self.symbol}. Skipping.")
                return
            
            self.virtual_positions.append({
                "instrument": self.symbol,
                "units": units,
                "entry_price": current_price,
                "sl": sl_price,
                "tp": tp_price,
                "time": str(timestamp)
            })
            logger.info(f"[BACKTEST] Emulated {signal} order. Price: {current_price}, SL: {sl_price}, TP: {tp_price}")
            return

        # LIVE / PRACTICE REALTIME LOGIC
        positions = self.client.get_open_positions()
        for pos in positions:
            if pos['instrument'] == self.symbol and float(pos['long']['units']) + float(pos['short']['units']) != 0:
                logger.info(f"Position already exists for {self.symbol}. Skipping trade.")
                return

        logger.info(f"Signal received: {signal} @ {current_price}")
        
        order_body = {
            "order": {
                "instrument": self.symbol,
                "units": str(units),
                "type": "MARKET",
                "positionFill": "DEFAULT",
                "takeProfitOnFill": {"price": str(tp_price)},
                "stopLossOnFill": {"price": str(sl_price)}
            }
        }
        
        logger.info(f"Placing {signal} order for {self.symbol} (Units: {units}, SL: {sl_price}, TP: {tp_price})...")
        response = self.client.create_order(order_body)
        
        if response and 'orderFillTransaction' in response:
            logger.info(f"Order Filled: {response['orderFillTransaction']['id']} @ {response['orderFillTransaction']['price']}")
        else:
            logger.warning("Order not filled or failed.")
            
    def evaluate_virtual_positions(self, current_price):
        """Evaluate backtest positions against SL/TP continuously"""
        if self.mode != "backtest": return
        
        for pos in self.virtual_positions[:]:
            closed = False
            pnl = 0
            if pos["units"] > 0: # LONG
                if current_price <= pos["sl"]:
                    pnl = (pos["sl"] - pos["entry_price"]) * pos["units"]
                    closed = True
                elif current_price >= pos["tp"]:
                    pnl = (pos["tp"] - pos["entry_price"]) * pos["units"]
                    closed = True
            else: # SHORT
                if current_price >= pos["sl"]:
                    pnl = (pos["entry_price"] - pos["sl"]) * abs(pos["units"])
                    closed = True
                elif current_price <= pos["tp"]:
                    pnl = (pos["entry_price"] - pos["tp"]) * abs(pos["units"])
                    closed = True
            
            if closed:
                self.virtual_balance += pnl
                self.virtual_trades.append({"pnl": pnl, "close_price": current_price, "entry": pos["entry_price"]})
                self.virtual_positions.remove(pos)
                logger.info(f"[BACKTEST] Position closed @ {current_price} | PNL: {pnl:.2f} | Balance: {self.virtual_balance:.2f}")

def save_state(state):
    try:
        with open("bot_state.json", "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.error(f"Error saving state: {e}")

def signal_handler(sig, frame):
    logger.info("Stopping bot...")
    save_state({"status": "stopped"})
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Reload .env at runtime to get the latest values
    load_dotenv(override=True)
    
    trade_env = os.getenv("TRADE_ENV", "practice")
    if trade_env == "practice":
        access_token = os.getenv("OANDA_PRACTICE_ACCESS_TOKEN")
        account_id = os.getenv("OANDA_PRACTICE_ACCOUNT_ID")
    else:
        access_token = os.getenv("OANDA_LIVE_ACCESS_TOKEN")
        account_id = os.getenv("OANDA_LIVE_ACCOUNT_ID")
        
    symbol = os.getenv("SYMBOL", "USD_JPY")
    timeframe = os.getenv("TIMEFRAME", "M1")
    position_size = int(os.getenv("POSITION_SIZE", "10000"))
    operate_mode = os.getenv("MODE", "realtime")
    
    if not access_token or not account_id:
        logger.error(f"API credentials for {trade_env} missing. Please check .env file.")
        save_state({"status": "error", "message": "Missing credentials"})
        return

    logger.info(f"Starting OANDA Trading Bot in {trade_env} environment | Mode: {operate_mode.upper()}")
    client = OandaClient(access_token, account_id, trade_env)
    trader = Trader(client, symbol, position_size, operate_mode)

    if operate_mode == "realtime":
        account = client.get_account_details()
        if account:
            logger.info(f"Connected to Account: {account['id']} - Balance: {account['balance']}")
            initial_balance = float(account['balance'])
            account_id_label = account['id']
        else:
            logger.error("Failed to connect to OANDA API. Exiting.")
            save_state({"status": "error", "message": "Failed to connect to API"})
            return
    else:
        # Backtest Setup
        initial_balance = trader.virtual_balance
        account_id_label = "BACKTEST-VIRTUAL"
        backtest_start = os.getenv("BACKTEST_START")
        backtest_end = os.getenv("BACKTEST_END")
        
        if not backtest_start:
            logger.error("BACKTEST_START is missing in .env")
            return
            
        logger.info(f"Starting backtest from {backtest_start} to {backtest_end if backtest_end else 'now'}")

    logger.info(f"Monitoring {symbol} on {timeframe} timeframe.")

    # Variables for state tracking
    all_historical_data = pd.DataFrame()

    if operate_mode == "backtest":
        # Fetch all historical data first
        logger.info("Fetching historical data for backtest...")
        try:
            candles = client.fetch_candles(symbol, timeframe, count=2000, _from=backtest_start, to=backtest_end if backtest_end else None)
            if not candles:
                logger.error("No historical data fetched.")
                return
                
            df = DataAnalyzer.parse_candles(candles)
            df = DataAnalyzer.calculate_technical_indicators(df)
            
            logger.info(f"Fetched {len(df)} candles for backtest.")
            
            for i in range(50, len(df)):
                # Iterate historical data
                current_df = df.iloc[:i+1]
                latest = current_df.iloc[-1]
                
                # Evaluate exiting positions first
                trader.evaluate_virtual_positions(latest['close'])
                
                # Evaluate entries
                trade_signal = trader.decide_action(current_df)
                if trade_signal:
                    trader.execute_trade(trade_signal, latest['close'], timestamp=latest['time'])
                    
                # We skip saving state/CSV on every tick to maximize speed
                
            logger.info("Backtest loop completed.")
            
            # Close any remaining open positions at the very end
            if len(trader.virtual_positions) > 0:
                logger.info("Closing open positions at end of backtest data.")
                for pos in trader.virtual_positions[:]:
                    # Force close at current market price
                    pnl = 0
                    if pos["units"] > 0:
                        pnl = (latest['close'] - pos["entry_price"]) * pos["units"]
                    else:
                        pnl = (pos["entry_price"] - latest['close']) * abs(pos["units"])
                    trader.virtual_balance += pnl
                    trader.virtual_trades.append({"pnl": pnl, "close_price": latest['close'], "entry": pos["entry_price"]})
                    trader.virtual_positions.remove(pos)

            # Calculate Backtest Metrics
            total_trades = len(trader.virtual_trades)
            wins = sum(1 for t in trader.virtual_trades if t['pnl'] > 0)
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            net_pnl = trader.virtual_balance - initial_balance

            # Update final state JSON for Dashboard
            state = {
                "status": "stopped",
                "mode": "backtest",
                "env": trade_env,
                "account_id": account_id_label,
                "balance": trader.virtual_balance,
                "symbol": symbol,
                "timeframe": timeframe,
                "position_size": trader.position_size,
                "latest_time": str(latest['time']),
                "latest_price": float(latest['close']),
                "sma_short": float(latest['SMA_short']) if 'SMA_short' in current_df.columns and not pd.isna(latest['SMA_short']) else 0,
                "sma_long": float(latest['SMA_long']) if 'SMA_long' in current_df.columns and not pd.isna(latest['SMA_long']) else 0,
                "rsi": float(latest['RSI']) if 'RSI' in current_df.columns and not pd.isna(latest['RSI']) else 0,
                "open_positions": trader.virtual_positions,
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "backtest_metrics": {
                    "total_trades": total_trades,
                    "wins": wins,
                    "win_rate": win_rate,
                    "net_pnl": net_pnl
                }
            }
            save_state(state)
            # Output final chart data
            current_df.to_csv("historical_data.csv", index=False)
            
        except Exception as e:
            logger.error(f"Error during backtest: {e}")
            save_state({"status": "error", "message": str(e)})    
            
        logger.info("Backtest process shutting down.")
        sys.exit(0) # End program immediately after backtest finishes
    
    # REALTIME LOOP
    while True:
        try:
            # reload configuration every loop to allow live editing from dashboard
            load_dotenv(override=True)
            current_trade_env = os.getenv("TRADE_ENV", "practice")
            
            # If environment changed, we should restart the script entirely to reconnect cleanly
            if current_trade_env != trade_env:
                logger.info(f"Environment changed from {trade_env} to {current_trade_env}. Restarting bot logic is required.")
                sys.exit(0)

            symbol = os.getenv("SYMBOL", "USD_JPY")
            timeframe = os.getenv("TIMEFRAME", "M1")
            trader.symbol = symbol
            trader.position_size = int(os.getenv("POSITION_SIZE", "10000"))

            # Fetch Data
            candles = client.fetch_candles(symbol, timeframe, count=60)
            if not candles:
                time.sleep(10)
                continue

            # Analyze Data
            df = DataAnalyzer.parse_candles(candles)
            df = DataAnalyzer.calculate_technical_indicators(df)

            # Decide & Execute
            latest = df.iloc[-1]
            logger.info(f"Latest: {latest['time']} | Close: {latest['close']} | SMA_short: {latest['SMA_short']:.3f} | RSI: {latest['RSI']:.1f}")
            
            trade_signal = trader.decide_action(df)
            if trade_signal:
                trader.execute_trade(trade_signal, latest['close'])
                
            # Update State JSON for Dashboard
            state = {
                "status": "running",
                "mode": "realtime",
                "env": trade_env,
                "account_id": account_id_label,
                "balance": account['balance'],
                "symbol": symbol,
                "timeframe": timeframe,
                "position_size": trader.position_size,
                "latest_time": str(latest['time']),
                "latest_price": float(latest['close']),
                "sma_short": float(latest['SMA_short']) if not pd.isna(latest['SMA_short']) else 0,
                "sma_long": float(latest['SMA_long']) if not pd.isna(latest['SMA_long']) else 0,
                "rsi": float(latest['RSI']) if not pd.isna(latest['RSI']) else 0,
                "open_positions": client.get_open_positions(),
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_state(state)
            
            # Save chart data for dashboard visualization
            df.to_csv("historical_data.csv", index=False)

            # Sleep for interval
            time.sleep(5) # check every 5 seconds for faster dashboard updates

        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            save_state({"status": "error", "message": str(e)})
            time.sleep(10)

if __name__ == "__main__":
    main()
