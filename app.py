import streamlit as st
import requests
import yfinance as yf
import pandas as pd

# -------------------------
# 1. 価格取得ロジック（強化版）
# -------------------------
def fetch_gold_price():
    """GOLD価格を複数のソースから試行"""
    # 手法A: Yahoo Finance (金先物 GC=F)
    try:
        gold = yf.Ticker("GC=F")
        data = gold.history(period="2d", interval="1d")
        if not data.empty:
            return float(data["Close"].iloc[-1]), "Yahoo(GC=F)"
    except:
        pass

    # 手法B: 直接APIリクエスト（ライブラリのバグ回避）
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=5).json()
        price = r['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price), "Direct API"
    except:
        pass

    # 手法C: fallback (2026年想定価格)
    return 5100.0, "Default(Fallback)"

def fetch_fx_rates():
    """為替レート取得"""
    try:
        r = requests.get("https://cdn.moneyconvert.net/api/latest.json", timeout=5).json()
        rates = r.get("rates", {})
        usd_jpy = float(rates.get("JPY", 150.0))
        return rates, usd_jpy
    except:
        return {}, 150.0

# -------------------------
# 2. セッション状態の管理
# -------------------------
if 'initialized' not in st.session_state:
    with st.spinner('最新相場データを取得中...'):
        fx_rates, usd_jpy, gold_price = fetch_fx_rates()
        gold_val, source = fetch_gold_price()
        
        st.session_state.fx_rates = fx_rates
        st.session_state.usd_jpy = usd_jpy
        st.session_state.gold_price = gold_val
        st.session_state.gold_source = source
        st.session_state.initialized = True

# -------------------------
# 3. 計算ロジック
# -------------------------
def get_pair_rate(pair):
    rates = st.session_state.fx_rates
    uj = st.session_state.usd_jpy
    gp = st.session_state.gold_price
    
    if pair == "GOLD": return gp
    if pair == "USDJPY": return uj
    
    base, quote = pair[:3], pair[3:]
    v_base = float(rates.get(base, 0))
    if base == "USD": return float(rates.get(quote, 1.0))
    if quote == "USD": return 1.0 / v_base if v_base != 0 else 1.0
    if quote == "JPY": return (1.0 / v_base) * uj if v_base != 0 else uj
    return 1.0

def calc_positions(pair, direction, division, weights, avg_price, max_loss, stop, upper, lower):
    unit = 1 if pair == "GOLD" else 10000
    prices = [upper - i * (upper - lower) / (division - 1) for i in range(division)] if division > 1 else [upper]
    
    # 1枚あたりの損失額計算
    loss_per_unit = []
    uj = st.session_state.usd_jpy
    for p in prices:
        diff = abs(p - stop)
        # クロス円以外（GOLD含む）はドル建てなので円換算が必要
        if pair == "GOLD" or not pair.endswith("JPY"):
            diff *= uj
        loss_per_unit.append(diff)
    
    # ロット調整
    total_raw_loss = sum(w * unit * l for w, l in zip(weights, loss_per_unit))
    factor = max_loss / total_raw_loss if total_raw_loss > 0 else 0
    adj_weights = [w * factor for w in weights]
    
    actual_avg = sum(w * p for w, p in zip(adj_weights, prices)) / sum(adj_weights) if sum(adj_weights) > 0 else upper
    
    return {"prices": prices, "weights": adj_weights, "avg": actual_avg, "total_loss": max_loss}

# -------------------------
# 4. UI 
# -------------------------
st.title("📈 分割エントリー計算機")

# サイドバー：デバッグ情報
with st.sidebar:
    st.header("取得レート情報")
    st.write(f"USDJPY: {st.session_state.usd_jpy:.2f}")
    st.write(f"GOLD: {st.session_state.gold_price:.2f}")
    st.caption(f"GOLD取得元: {st.session_state.gold_source}")
    if st.button("レートを再更新"):
        del st.session_state.initialized
        st.rerun()

# 入力セクション
col_a, col_b = st.columns(2)
with col_a:
    pair = st.selectbox("銘柄選択", ["GOLD", "USDJPY", "EURUSD", "GBPJPY"])
    direction = st.radio("売買", ["buy", "sell"], horizontal=True)
with col_b:
    current_rate = get_pair_rate(pair)
    st.metric("現在レート", f"{current_rate:.2f}")

# 入力フォーム
with st.form("main_form"):
    c1, c2 = st.columns(2)
    with c1:
        upper = st.number_input("ゾーン上限", value=current_rate)
        lower = st.number_input("ゾーン下限", value=current_rate * 0.99)
    with c2:
        stop = st.number_input("ストップ価格", value=current_rate * 0.98)
        max_loss = st.number_input("最大損失(円)", value=10000)

    div = st.number_input("分割数", 1, 10, 3)
    w_input = st.text_input("比率（カンマ区切り）", "1,2,3")
    
    submit = st.form_submit_button("計算する")

if submit:
    try:
        w_list = [float(x) for x in w_input.split(",")]
        if len(w_list) != div:
            st.error("分割数と比率の数が一致しません")
        else:
            res = calc_positions(pair, direction, div, w_list, 0, max_loss, stop, upper, lower)
            
            st.divider()
            st.subheader("📊 計算結果")
            for i, (p, w) in enumerate(zip(res["prices"], res["weights"])):
                st.write(f"ポジション {i+1}: 価格 **{p:.2f}** / ロット **{w:.3f}**")
            
            st.info(f"期待平均建値: {res['avg']:.2f} | 許容損失: {max_loss:,}円")
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")