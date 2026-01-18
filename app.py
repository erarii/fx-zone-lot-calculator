# app.py
import streamlit as st
import requests

# -------------------------
# 設定
# -------------------------
CURRENCY_PAIRS = [
    "USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY",
    "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF",
    "GOLD"
]

LOT_INFO = {
    "FX": 10000,    # 1lot=1万通貨
    "GOLD": 1       # 1lot=1oz
}

DECIMALS = {
    "JPY": 3,
    "USD": 5,
    "GOLD": 2
}

def get_decimal(pair):
    if pair=="GOLD":
        return DECIMALS["GOLD"]
    elif "JPY" in pair:
        return DECIMALS["JPY"]
    else:
        return DECIMALS["USD"]

# -------------------------
# 最新レート取得（USD基準）
# -------------------------
def fetch_rates():
    try:
        url = "https://cdn.moneyconvert.net/api/latest.json"
        response = requests.get(url, timeout=5)
        data = response.json().get("rates", {})
        usd_jpy = float(data.get("JPY", 150.0))
        return data, usd_jpy
    except:
        return {}, 150.0

# -------------------------
# ペアレート取得（円建て初期値用）
# -------------------------
def get_pair_rate(pair, rates, usd_jpy):
    if pair=="GOLD":
        return 1900.0  # USD建て
    elif pair=="USDJPY":
        return usd_jpy
    elif pair.endswith("JPY"):
        base = pair[:3]
        if base=="USD":
            return usd_jpy
        elif base in rates:
            # XXXJPY = USDJPY / (1 USD = XXX)
            return usd_jpy / float(rates[base])
        else:
            return usd_jpy
    else:  # ドル建てFX
        base = pair[:3]
        quote = pair[3:]
        if base=="USD" and quote in rates:
            # USD/XXX → USDJPY ÷ rate
            return usd_jpy / float(rates[quote])
        elif quote=="USD" and base in rates:
            # XXX/USD → USDJPY × rate
            return usd_jpy * float(rates[base])
        else:
            return usd_jpy

# -------------------------
# 分割エントリー計算
# -------------------------
def calc_positions(pair, direction, division, weights, avg_price, max_loss, stop, upper, lower, usd_jpy_rate):
    division = int(division)
    weights = [float(w) for w in weights]

    if len(weights) != division:
        raise ValueError(f"ウェイトの数({len(weights)})と分割数({division})が一致していません。")

    unit = LOT_INFO["GOLD"] if pair=="GOLD" else LOT_INFO["FX"]

    # 分割価格
    if division==1:
        prices = [avg_price]
    else:
        prices = [upper - i*(upper-lower)/(division-1) for i in range(division)]

    # 建値平均補正
    total_weighted_price = sum([w*p for w,p in zip(weights, prices)])
    total_weight = sum(weights)
    current_avg = total_weighted_price / total_weight if total_weight != 0 else avg_price
    scale = avg_price / current_avg if current_avg != 0 else 1
    weights = [w*scale for w in weights]

    # 損失計算
    loss_per_unit = []
    for p in prices:
        if direction=="buy":
            diff = stop - p
        else:
            diff = p - stop
        diff = abs(diff)
        # 円換算
        if pair=="GOLD" or (not pair.endswith("JPY") and pair!="GOLD"):
            diff *= usd_jpy_rate
        loss_per_unit.append(diff)

    total_loss = sum([w*unit*l for w,l in zip(weights, loss_per_unit)])

    # 最大損失制限
    if total_loss > max_loss and total_loss > 0:
        factor = max_loss / total_loss
        weights = [w*factor for w in weights]
        total_loss = max_loss

    # 平均建値
    avg_calc = sum([w*p for w,p in zip(weights, prices)]) / sum(weights)

    return {
        "prices": prices,
        "weights": weights,
        "avg_price": avg_calc,
        "total_loss": total_loss
    }

# -------------------------
# Streamlit UI
# -------------------------
st.title("分割エントリー計算アプリ（正確円建て対応）")

mode = st.radio("モード選択", ["事前ゾーン型", "成行起点型"])
pair = st.selectbox("通貨ペア/GOLD", CURRENCY_PAIRS)
direction = st.radio("方向", ["buy", "sell"])
decimals = get_decimal(pair)
fmt = f"%.{decimals}f"

# -------------------------
# 最新レート取得
# -------------------------
rates_data, usd_jpy_rate = fetch_rates()
current_price = get_pair_rate(pair, rates_data, usd_jpy_rate)

# ゾーン上限下限・平均建値・ストップ
upper = st.number_input("ゾーン上限", value=current_price, format=fmt)
lower = st.number_input("ゾーン下限", value=current_price*0.995, format=fmt)
avg_price = st.number_input("目標平均建値", value=current_price, format=fmt)
stop = st.number_input("ストップ価格", value=current_price*0.99, format=fmt)

# 分割・ウェイト・最大損失
division = st.number_input("分割数", min_value=1, max_value=5, value=3, step=1)
weights_input = st.text_input("ウェイト（カンマ区切り）例：2,2,4", value="2,2,4")
weights = [w.strip() for w in weights_input.split(",")]
max_loss = st.number_input("最大損失（円）", value=10000.0)

# 成行モードの市場価格
market_price = None
if mode=="成行起点型":
    market_price = st.number_input("成行価格", value=current_price, format=fmt)
    if direction=="buy":
        upper = market_price
    else:
        lower = market_price

# 計算ボタン
if st.button("計算"):
    st.write(f"USD/JPY 最新レート: {usd_jpy_rate:.3f}")
    try:
        result = calc_positions(
            pair=pair,
            direction=direction,
            division=division,
            weights=[float(w) for w in weights],
            avg_price=avg_price,
            max_loss=max_loss,
            stop=stop,
            upper=upper,
            lower=lower,
            usd_jpy_rate=usd_jpy_rate
        )

        st.subheader("計算結果")
        for i,(p,w) in enumerate(zip(result["prices"], result["weights"])):
            st.write(f"ポジション{i+1}: レート {p:.{decimals}f}, ロット {w:.4f}")

        st.write(f"計算平均建値: {result['avg_price']:.{decimals}f}")
        st.write(f"最大損失（円換算）: {result['total_loss']:.2f}")

    except Exception as e:
        st.error(f"計算中にエラーが発生しました: {e}")
