import streamlit as st
import requests
import yfinance as yf

# -------------------------
# 1. 設定 & 取得ロジック
# -------------------------
# 主要通貨ペアを網羅
CURRENCY_PAIRS = [
    "GOLD", 
    "USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY",
    "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF",
    "EURAUD", "EURGBP", "EURCAD", "EURCHF", "GBPAUD", "GBPCAD", "AUDNZD"
]
DECIMALS = {"JPY": 3, "USD": 5, "GOLD": 2}

def get_decimal(pair):
    if pair == "GOLD": return DECIMALS["GOLD"]
    return DECIMALS["JPY"] if "JPY" in pair else DECIMALS["USD"]

def fetch_fx_rates():
    """為替レートを取得 (Base: USD)"""
    try:
        r = requests.get("https://cdn.moneyconvert.net/api/latest.json", timeout=5).json()
        rates = r.get("rates", {})
        usd_jpy = float(rates.get("JPY", 150.0))
        return rates, usd_jpy
    except:
        return {}, 150.0

def fetch_gold_price():
    """GOLD価格を複数のソースから試行"""
    try:
        gold = yf.Ticker("GC=F")
        data = gold.history(period="2d", interval="1d")
        if not data.empty:
            return float(data["Close"].iloc[-1]), "Yahoo(GC=F)"
    except:
        pass

    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5).json()
        price = r['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price), "Direct API"
    except:
        pass

    return 5100.0, "Default(Fallback)"

# -------------------------
# 2. セッション状態の管理
# -------------------------
if 'initialized' not in st.session_state:
    with st.spinner('最新データを取得中...'):
        fx_rates, usd_jpy = fetch_fx_rates()
        gold_val, source = fetch_gold_price()
        
        st.session_state.fx_rates = fx_rates
        st.session_state.usd_jpy = usd_jpy
        st.session_state.gold_price = gold_val
        st.session_state.gold_source = source
        st.session_state.initialized = True

# -------------------------
# 3. レート計算関数（全ペア対応）
# -------------------------
def get_pair_rate(pair):
    rates = st.session_state.fx_rates
    uj = st.session_state.usd_jpy
    gp = st.session_state.gold_price
    
    if pair == "GOLD": return gp
    if pair == "USDJPY": return uj
    
    base = pair[:3]   # 例: EUR
    quote = pair[3:]  # 例: AUD
    
    # 1. USDがベース (USDCAD, USDCHFなど)
    if base == "USD":
        return float(rates.get(quote, 1.0))
    
    # 2. USDがクオート (EURUSD, GBPUSDなど)
    if quote == "USD":
        v_base = float(rates.get(base, 0))
        return 1.0 / v_base if v_base != 0 else 1.0
    
    # 3. クロス円 (EURJPYなど)
    if quote == "JPY":
        v_base = float(rates.get(base, 0))
        return (1.0 / v_base * uj) if v_base != 0 else uj
        
    # 4. その他クロス通貨 (EURAUDなど)
    v_base = float(rates.get(base, 0))
    v_quote = float(rates.get(quote, 0))
    if v_base != 0 and v_quote != 0:
        # (1/EURUSD) / (1/AUDUSD) = AUDUSD / EURUSD = EURAUD
        return (1.0 / v_base) / (1.0 / v_quote)

    return 1.0

# -------------------------
# 4. ポジション計算（円建て換算強化）
# -------------------------
def calc_positions(pair, direction, division, weights, max_loss, stop, upper, lower):
    unit = 1 if pair == "GOLD" else 10000
    
    if division > 1:
        prices = [upper - i * (upper - lower) / (division - 1) for i in range(division)]
    else:
        prices = [upper]
    
    uj = st.session_state.usd_jpy
    rates = st.session_state.fx_rates
    loss_per_unit = []
    
    # クオート通貨（右側）を特定して円換算レートを出す
    quote_cur = "USD" if pair == "GOLD" else pair[3:]
    
    # 円換算レートの取得
    if quote_cur == "JPY":
        conversion_rate = 1.0
    elif quote_cur == "USD":
        conversion_rate = uj
    else:
        # 例: EURAUDなら AUDJPY のレートが必要
        # 簡易的に (1 / AUDUSD) * USDJPY で算出
        v_quote = float(rates.get(quote_cur, 0))
        conversion_rate = (1.0 / v_quote * uj) if v_quote != 0 else uj

    for p in prices:
        diff = abs(p - stop)
        loss_per_unit.append(diff * conversion_rate)
    
    total_raw_loss = sum(w * unit * l for w, l in zip(weights, loss_per_unit))
    factor = max_loss / total_raw_loss if total_raw_loss > 0 else 0
    adj_weights = [w * factor for w in weights]
    
    actual_avg = sum(w * p for w, p in zip(adj_weights, prices)) / sum(adj_weights) if sum(adj_weights) > 0 else upper
    
    return {"prices": prices, "weights": adj_weights, "avg": actual_avg, "total_loss": max_loss}

# -------------------------
# 5. UI 
# -------------------------
st.title("📈 多通貨対応 分割計算機")

with st.sidebar:
    st.header("取得レート情報")
    st.write(f"USDJPY: {st.session_state.usd_jpy:.2f}")
    st.write(f"GOLD: {st.session_state.gold_price:.2f}")
    if st.button("レートを再取得"):
        del st.session_state.initialized
        st.rerun()

col_a, col_b = st.columns(2)
with col_a:
    pair = st.selectbox("銘柄選択", CURRENCY_PAIRS)
    direction = st.radio("売買方向", ["buy", "sell"], horizontal=True)
with col_b:
    current_rate = get_pair_rate(pair)
    decimals = get_decimal(pair)
    st.metric(f"現在の{pair}", f"{current_rate:.{decimals}f}")

with st.form("main_form"):
    fmt = f"%.{decimals}f"
    c1, c2 = st.columns(2)
    with c1:
        upper = st.number_input("ゾーン上限", value=current_rate, format=fmt, step=0.001 if decimals > 2 else 0.1)
        lower = st.number_input("ゾーン下限", value=current_rate * 0.995, format=fmt, step=0.001 if decimals > 2 else 0.1)
    with c2:
        stop = st.number_input("ストップ価格", value=current_rate * 0.99, format=fmt, step=0.001 if decimals > 2 else 0.1)
        max_loss_input = st.number_input("最大許容損失(円)", value=10000, step=1000)

    div = st.number_input("分割数", 1, 10, 3)
    w_input = st.text_input("ウェイト比率（例: 1,2,4）", "1,1,1")
    
    submit = st.form_submit_button("計算を実行")

if submit:
    try:
        w_list = [float(x.strip()) for x in w_input.split(",")]
        if len(w_list) != div:
            st.error(f"分割数({div})と比率の数({len(w_list)})を合わせてください。")
        else:
            res = calc_positions(pair, direction, div, w_list, max_loss_input, stop, upper, lower)
            
            st.divider()
            st.subheader("📊 計算結果")
            for i, (p, w) in enumerate(zip(res["prices"], res["weights"])):
                st.write(f"{i+1}個目: 価格 **{p:.{decimals}f}** / ロット **{w:.4f}**")
            
            st.success(f"期待平均建値: {res['avg']:.{decimals}f} | 最大損失: {max_loss_input:,}円")
    except Exception as e:
        st.error(f"計算エラー: {e}")