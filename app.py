import streamlit as st
import requests
import yfinance as yf

# -------------------------
# 設定 & レート取得ロジック
# -------------------------
CURRENCY_PAIRS = ["GOLD", "USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "EURUSD", "GBPUSD"]
LOT_INFO = {"FX": 10000, "GOLD": 1}
DECIMALS = {"JPY": 3, "USD": 5, "GOLD": 2}

def get_decimal(pair):
    if pair == "GOLD": return DECIMALS["GOLD"]
    return DECIMALS["JPY"] if "JPY" in pair else DECIMALS["USD"]

def fetch_all_rates():
    """全レートをまとめて取得する関数"""
    # 1. USDJPY & FX Rates
    try:
        r = requests.get("https://cdn.moneyconvert.net/api/latest.json", timeout=5).json()
        fx_rates = r.get("rates", {})
        usd_jpy = float(fx_rates.get("JPY", 150.0))
    except:
        fx_rates, usd_jpy = {}, 150.0

    # 2. GOLD Price (Yahoo FinanceのGC=Fを優先)
    gold_price = 2000.0 # 究極のfallback
    try:
        gold_data = yf.Ticker("GC=F").history(period="1d")
        if not gold_data.empty:
            gold_price = float(gold_data["Close"].iloc[-1])
    except:
        pass # 失敗した場合は2000.0
        
    return fx_rates, usd_jpy, gold_price

# -------------------------
# セッション状態の初期化
# -------------------------
# 初回実行時、または「更新」ボタンが押された時だけAPIを叩く
if 'rates_initialized' not in st.session_state:
    fx, uj, gold = fetch_all_rates()
    st.session_state.fx_rates = fx
    st.session_state.usd_jpy = uj
    st.session_state.gold_price = gold
    st.session_state.rates_initialized = True

# -------------------------
# レート計算ロジック
# -------------------------
def get_pair_rate(pair):
    rates = st.session_state.fx_rates
    usd_jpy = st.session_state.usd_jpy
    gold_price = st.session_state.gold_price

    if pair == "GOLD": return gold_price
    
    base, quote = pair[:3], pair[3:]
    # ... (既存の計算ロジックはそのまま利用)
    v_base = float(rates.get(base, 0))
    if base == "USD": return float(rates.get(quote, 1.0))
    if quote == "USD": return 1.0 / v_base if v_base != 0 else 1.0
    if quote == "JPY": return (1.0 / v_base) * usd_jpy if v_base != 0 else usd_jpy
    return 1.0

# -------------------------
# UI部分
# -------------------------
st.title("FX/GOLD 分割エントリー計算機")

# サイドバーに現在の参照レートを表示
st.sidebar.markdown(f"**現在の取得レート**")
st.sidebar.write(f"USDJPY: {st.session_state.usd_jpy:.2f}")
st.sidebar.write(f"GOLD: {st.session_state.gold_price:.2f}")
if st.sidebar.button("レート再取得"):
    del st.session_state.rates_initialized
    st.rerun()

pair = st.selectbox("通貨ペア/GOLD", CURRENCY_PAIRS)
direction = st.radio("方向", ["buy", "sell"], horizontal=True)

# 選択された通貨の現在値を算出
current_price = get_pair_rate(pair)
decimals = get_decimal(pair)
fmt = f"%.{decimals}f"

# フォーム形式にして、入力のたびに再計算が走るのを防ぐ（任意）
with st.form("calc_form"):
    col1, col2 = st.columns(2)
    with col1:
        upper = st.number_input("ゾーン上限", value=current_price, format=fmt)
        lower = st.number_input("ゾーン下限", value=current_price * 0.995, format=fmt)
    with col2:
        avg_price = st.number_input("目標平均建値", value=current_price, format=fmt)
        stop = st.number_input("ストップ価格", value=current_price * 0.99, format=fmt)

    division = st.slider("分割数", 1, 5, 3)
    weights_input = st.text_input("ウェイト（カンマ区切り）", "2,2,4")
    max_loss = st.number_input("最大許容損失（円）", value=10000)
    
    submitted = st.form_submit_button("計算実行")

# ... (calc_positions関数と結果表示ロジックをここに継続)