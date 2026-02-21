import streamlit as st
import os
import time
import json
import subprocess
import pandas as pd
import plotly.graph_objects as go
from dotenv import set_key, load_dotenv

# Set page config
st.set_page_config(page_title="OANDA 自動売買ダッシュボード", layout="wide")

st.title("📈 OANDA 自動売買ダッシュボード")

ENV_FILE = ".env"
STATE_FILE = "bot_state.json"
HISTORICAL_DATA = "historical_data.csv"

# Load initial environment variables
load_dotenv(override=True)

def update_env(key, value):
    set_key(ENV_FILE, key, str(value))
    # We call load_dotenv to update the local process environment as well
    load_dotenv(override=True)

def load_bot_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            return None
    return None

def is_bot_running():
    state = load_bot_state()
    if state and state.get("status") == "running":
        # Check if the process is actually still alive by examining the generic update time
        last_update = state.get("last_update")
        if last_update:
            try:
                import datetime
                last_time = datetime.datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S")
                # If the bot hasn't updated its state in over 30 seconds, consider it dead
                if (datetime.datetime.now() - last_time).total_seconds() > 30:
                    return False
            except:
                pass
        return True
    return False

# ----- SIDEBAR CONFIGURATION -----
st.sidebar.header("Bot 設定")

# Environment Switcher (One-Click Toggle)
current_env = os.getenv("TRADE_ENV", "practice")
env_options = ["practice", "live"]
env_index = env_options.index(current_env) if current_env in env_options else 0

selected_env = st.sidebar.radio("🌐 取引環境", options=env_options, index=env_index, format_func=lambda x: "デモ口座 (Practice)" if x == "practice" else "本番口座 (Live)")
if selected_env != current_env:
    update_env("TRADE_ENV", selected_env)
    st.sidebar.success(f"{'デモ' if selected_env == 'practice' else '本番'}環境に切り替えました！")

# Mode Selection
st.sidebar.subheader("▶️ 稼働モード")
current_operate_mode = os.getenv("MODE", "realtime")
mode_options = ["realtime", "backtest"]
mode_index = mode_options.index(current_operate_mode) if current_operate_mode in mode_options else 0
selected_operate_mode = st.sidebar.radio("モード選択", options=mode_options, index=mode_index, format_func=lambda x: "リアルタイム" if x == "realtime" else "バックテスト (過去データ検証)")

if selected_operate_mode != current_operate_mode:
    update_env("MODE", selected_operate_mode)
    current_operate_mode = selected_operate_mode
    
backtest_start_str = os.getenv("BACKTEST_START", "2024-02-10T09:00:00Z")

if current_operate_mode == "backtest":
    st.sidebar.markdown("**バックテスト設定**")
    try:
        from datetime import datetime, timezone
        default_dt = datetime.strptime(backtest_start_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
    except:
        default_dt = pd.Timestamp.now() - pd.Timedelta(days=5)
        
    start_date = st.sidebar.date_input("開始日", value=default_dt.date())
    start_time = st.sidebar.time_input("開始時間", value=default_dt.time())
    
    selected_start_dtstr = f"{start_date}T{start_time.strftime('%H:%M:%S')}Z"
    
    if selected_start_dtstr != backtest_start_str:
        update_env("BACKTEST_START", selected_start_dtstr)
        
    backtest_end_str = os.getenv("BACKTEST_END", "")
    try:
        from datetime import datetime, timezone
        default_end_dt = datetime.strptime(backtest_end_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
    except:
        default_end_dt = pd.Timestamp.now()
        
    end_date = st.sidebar.date_input("終了日", value=default_end_dt.date())
    end_time = st.sidebar.time_input("終了時間", value=default_end_dt.time())
    
    selected_end_dtstr = f"{end_date}T{end_time.strftime('%H:%M:%S')}Z"
    if selected_end_dtstr != backtest_end_str:
        update_env("BACKTEST_END", selected_end_dtstr)

st.sidebar.divider()
# Trading Parameters
st.sidebar.subheader("取引パラメータ")
current_symbol = os.getenv("SYMBOL", "USD_JPY")
current_timeframe = os.getenv("TIMEFRAME", "M1")
current_size = os.getenv("POSITION_SIZE", "10000")

symbol = st.sidebar.text_input("通貨ペア", value=current_symbol)
timeframe = st.sidebar.selectbox("時間足", ["S5", "S10", "S30", "M1", "M5", "M15", "M30", "H1", "H4", "D"], index=["S5", "S10", "S30", "M1", "M5", "M15", "M30", "H1", "H4", "D"].index(current_timeframe) if current_timeframe in ["S5", "S10", "S30", "M1", "M5", "M15", "M30", "H1", "H4", "D"] else 3)
position_size = st.sidebar.number_input("ポジションサイズ (通貨量)", value=int(current_size), step=1000)

if st.sidebar.button("💾 設定を保存"):
    update_env("SYMBOL", symbol)
    update_env("TIMEFRAME", timeframe)
    update_env("POSITION_SIZE", position_size)
    st.sidebar.success("設定を保存しました。")

# Bot Control
st.sidebar.divider()
st.sidebar.subheader("▶️ Bot 制御")

bot_running = is_bot_running()

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Bot起動 (Start)", disabled=bot_running, use_container_width=True):
        update_env("TRADE_ENV", selected_env) # Ensure latest env is set before start
        # Reset state to starting
        with open(STATE_FILE, "w") as f:
            json.dump({"status": "starting..."}, f)
            
        # Spawn the process detached
        import platform
        if platform.system() == "Windows":
            # Setting PYTHONUTF8=1 to fix Windows encoding issues
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            subprocess.Popen(
                ["python", "trading_bot.py"], 
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                env=env
            )
        else:
            subprocess.Popen(["python", "trading_bot.py"])
            
        st.success("Botを起動しました！")
        time.sleep(2)
        st.rerun()

with col2:
    if st.button("Bot停止 (Stop)", disabled=not bot_running, use_container_width=True):
        # We can stop it by simply changing the TRADE_ENV to something else temporarily, 
        # or writing "stop" to a control file. Let's write 'stop' to bot_state.
        with open(STATE_FILE, "w") as f:
            json.dump({"status": "stopped"}, f)
        st.success("停止シグナルを送信しました。")
        time.sleep(1)
        st.rerun()

st.sidebar.info("注意: Botは別ウィンドウ（裏側）で動作しています。この画面を閉じてもBotは停止しません。")

# ----- MAIN DASHBOARD -----
state = load_bot_state()

# Auto-Refresh Toggle
# Default to true if bot is running, or if we are in backtest mode so it can auto-reveal the result
auto_refresh = st.checkbox("自動更新 (5秒ごと)", value=bot_running or current_operate_mode == "backtest")

# Check for newly finished backtests to trigger immediate redraw if not yet seen
if 'last_seen_update' not in st.session_state:
    st.session_state.last_seen_update = None

current_update = state.get("last_update") if state else None
if current_update and current_update != st.session_state.last_seen_update:
    st.session_state.last_seen_update = current_update
    # If the state just changed to stopped with metrics, force a rapid rerun to show it
    if state.get("mode") == "backtest" and state.get("status") == "stopped" and "backtest_metrics" in state:
        time.sleep(0.5)
        st.rerun()

# Status Banner
if bot_running and state:
    st.success(f"🟢 BOT稼働中 | 対象口座: **{'デモ' if state.get('env', 'unknown') == 'practice' else '本番'}({state.get('env', 'unknown').upper()})**")
else:
    st.warning("🔴 BOT停止中")

if state and "error" in state.get("status"):
    st.error(f"Botでエラーが発生しました: {state.get('message', 'Unknown Error')}")

# Metrics display
col1, col2, col3, col4 = st.columns(4)
with col1:
    env_label = "デモ (Practice)" if (state.get("env", current_env) if state else current_env) == "practice" else "本番 (Live)"
    mode_label = (" バックテスト" if state and state.get("mode") == "backtest" else "")
    st.metric(label="現在の環境", value=env_label + mode_label)
with col2:
    st.metric(label="口座残高", value=f"¥ {float(state.get('balance', 0)):,.0f}" if state and state.get('balance') else "N/A")
with col3:
    st.metric(label="現在価格", value=state.get("latest_price", "N/A") if state and state.get('latest_price') else "N/A")
with col4:
    date_val = state.get("latest_time", "N/A") if state and state.get("latest_time") else "N/A"
    if date_val != "N/A":
        # clean up the date display slightly
        date_val = str(date_val).split(".")[0]
    st.metric(label="現在の日時" if state and state.get("mode") == "backtest" else "現在のRSI", value=date_val if state and state.get("mode") == "backtest" else f"{state.get('rsi', 0):.2f}")

if state and state.get("mode") == "backtest" and state.get("status") == "stopped" and "backtest_metrics" in state:
    metrics = state["backtest_metrics"]
    st.markdown("### 📊 バックテスト結果 (Backtest Summary)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("総取引回数 (Total Trades)", metrics.get("total_trades", 0))
    m2.metric("勝ちトレード (Wins)", metrics.get("wins", 0))
    m3.metric("勝率 (Win Rate)", f"{metrics.get('win_rate', 0):.2f}%")
    
    pnl = float(metrics.get("net_pnl", 0))
    m4.metric("純利益 (Net PnL)", f"¥ {pnl:,.0f}", delta=f"¥ {pnl:,.0f}")

st.divider()

# Chart and Positions
col_chart, col_data = st.columns([2, 1])

with col_chart:
    st.subheader("価格推移 ＆ インジケーター")
    if os.path.exists(HISTORICAL_DATA):
        try:
            df = pd.read_csv(HISTORICAL_DATA)
            
            fig = go.Figure()

            # Candlesticks
            fig.add_trace(go.Candlestick(x=df['time'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='価格 (Price)'
            ))

            # SMAs
            if 'SMA_short' in df.columns:
                fig.add_trace(go.Scatter(x=df['time'], y=df['SMA_short'], line=dict(color='orange', width=1.5), name='SMA (短期)'))
            if 'SMA_long' in df.columns:
                fig.add_trace(go.Scatter(x=df['time'], y=df['SMA_long'], line=dict(color='blue', width=1.5), name='SMA (長期)'))

            fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"チャートの描画中にエラーが発生しました: {e}")
    else:
        st.info("まだチャートデータがありません。Botを起動してデータを収集してください。")

with col_data:
    st.subheader("保有ポジション")
    if state and "open_positions" in state and len(state["open_positions"]) > 0:
        for pos in state["open_positions"]:
            with st.container(border=True):
                st.markdown(f"**{pos.get('instrument')}**")
                
                long_units = int(float(pos.get('long', {}).get('units', 0)))
                short_units = int(float(pos.get('short', {}).get('units', 0)))
                
                if long_units > 0:
                    st.success(f"買い (LONG): {long_units} 通貨")
                    st.write(f"平均取得単価: {pos.get('long', {}).get('averagePrice', 'N/A')}")
                elif short_units < 0:
                    st.error(f"売り (SHORT): {abs(short_units)} 通貨")
                    st.write(f"平均取得単価: {pos.get('short', {}).get('averagePrice', 'N/A')}")
                    
                st.write(f"未確定損益 (PL): {pos.get('unrealizedPL', 'N/A')}")
    else:
        st.info("現在保有しているポジションはありません。")

# Process auto-refresh
if auto_refresh:
    # If a backtest just finished (status is stopped and we have metrics), 
    # and we haven't 'seen' it yet, we don't need to sleep 5 seconds, but standard is 5s
    time.sleep(5)
    st.rerun()
