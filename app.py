# app.py
import streamlit as st
import requests

# -------------------------
# 設定
# -------------------------
CURRENCY_PAIRS = [
    "USDJPY","EURJPY","GBPJPY","AUDJPY","NZDJPY","CADJPY","CHFJPY",
    "EURUSD","GBPUSD","AUDUSD","NZDUSD","USDCAD","USDCHF",
    "GOLD"
]

LOT_INFO = {"FX": 10000, "GOLD": 1}
DECIMALS = {"JPY": 3, "USD": 5, "GOLD": 2}

def get_decimal(pair):
    if pair == "GOLD":
        return DECIMALS["GOLD"]
    elif "JPY" in pair:
        return DECIMALS["JPY"]
    else:
        return DECIMALS["USD"]

# -------------------------
# 正しい FX レート取得（クロス円は自前計算）
# -------------------------
def get_fx_rate(pair):
    if pair == "GOLD":
        return 1900.0  # 必要なら後でAPI化

    base = pair[:3]
    quote = pair[3:]

    # USD が絡むペアは API から直接取得
    if base == "USD" or quote == "USD":
        url = f"https://api.exchangerate.host/latest?base={base}&symbols={quote}"
        r = requests.get(url).json()
        if "rates" in r and quote in r["rates"]:
            return float(r["rates"][quote])
        else:
            return None  # 後で fallback

    # USD が絡まないペア（クロス円含む）は自前計算
    # base/quote = (base/USD) / (quote/USD)

    # base/USD
    url1 = f"https://api.exchangerate.host/latest?base={base}&symbols=USD"
    r1 = requests.get(url1).json()
    if "rates" not in r1 or "USD" not in r1["rates"]:
        return None
    base_usd = float(r1["rates"]["USD"])

    # quote/USD
    url2 = f"https://api.exchangerate.host/latest?base={quote}&symbols=USD"
    r2 = requests.get(url2).json()
    if "rates" not in r2 or "USD" not in r2["rates"]:
        return None
    quote_usd = float(r2["rates"]["USD"])

    # base/quote = (base/USD) / (quote/USD)
    return base_usd / quote_usd

# -------------------------
# 分割エントリー計算
# -------------------------
def calc_positions(pair, direction, division, weights, avg_price, max_loss, stop, upper, lower, usd_jpy_rate):
    division = int(division)
    weights = [float(w) for w in weights]

    if len(weights) != division:
        raise ValueError(f"ウェイト数({len(weights)})と分割数({division})不一致")

    unit = LOT_INFO["GOLD"] if pair == "GOLD" else LOT_INFO["FX"]

    if division == 1:
        prices = [avg_price]
    else:
        prices = [upper - i * (upper - lower) / (division - 1) for i in range(division)]

    total_weighted_price = sum([w * p for w, p in zip(weights, prices)])
    total_weight = sum(weights)
    current_avg = total_weighted_price / total_weight if total_weight != 0 else avg_price
    scale = avg_price / current_avg if current_avg != 0 else 1
    weights = [w * scale for w in weights]

    loss_per_unit = []
    for p in prices:
        diff = abs((stop - p) if direction == "buy" else (p - stop))
        if pair == "GOLD" or not pair.endswith("JPY"):
            diff *= usd_jpy_rate
        loss_per_unit.append(diff)

    total_loss = sum([w * unit * l for w, l in zip(weights, loss_per_unit)])

    if total_loss > max_loss and total_loss > 0:
        factor = max_loss / total_loss
        weights = [w * factor for w in weights]
        total_loss = max_loss

    avg_calc = sum([w * p for w, p in zip(weights, prices)]) / sum(weights)

    return {"prices": prices, "weights": weights, "avg_price": avg_calc, "total_loss": total_loss}

# -------------------------
# Streamlit UI
# -------------------------
st.title("分割エントリー計算アプリ（正しい FX レート版）")

mode = st.radio("モード選択", ["事前ゾーン型", "成行起点型"])
pair = st.selectbox("通貨ペア/GOLD", CURRENCY_PAIRS)
direction = st.radio("方向", ["buy", "sell"])

decimals = get_decimal(pair)
fmt = f"%.{decimals}f"

# -------------------------
# レート取得（絶対に None にならないように fallback）
# -------------------------
current_price = get_fx_rate(pair)
if current_price is None:
    st.error(f"{pair} のレート取得に失敗しました。")
    st.stop()

usd_jpy_rate = get_fx_rate("USDJPY")
if usd_jpy_rate is None:
    st.error("USDJPY のレート取得に失敗しました。")
    st.stop()

# -------------------------
# UI 初期値制御
# -------------------------
if mode == "事前ゾーン型":
    upper_default = current_price
    lower_default = current_price * 0.995
else:
    upper_default = current_price if direction == "buy" else current_price * 1.005
    lower_default = current_price if direction == "sell" else current_price * 0.995

upper = st.number_input("ゾーン上限", value=upper_default, format=fmt)
lower = st.number_input("ゾーン下限", value=lower_default, format=fmt)

avg_price = st.number_input("目標平均建値", value=current_price, format=fmt)
stop = st.number_input("ストップ価格", value=current_price * 0.99, format=fmt)

division = st.number_input("分割数", min_value=1, max_value=5, value=3, step=1)
weights_input = st.text_input("ウェイト（カンマ区切り）例：2,2,4", "2,2,4")
weights = [w.strip() for w in weights_input.split(",")]

max_loss = st.number_input("最大損失（円）", value=10000.0)

if mode == "成行起点型":
    market_price = st.number_input("成行価格", value=current_price, format=fmt)
    if direction == "buy":
        upper = market_price
    else:
        lower = market_price

# -------------------------
# 計算
# -------------------------
if st.button("計算"):
    st.write(f"USD/JPY 最新レート: {usd_jpy_rate:.3f}")
    try:
        result = calc_positions(
            pair, direction, division, [float(w) for w in weights],
            avg_price, max_loss, stop, upper, lower, usd_jpy_rate
        )

        st.subheader("計算結果")
        for i, (p, w) in enumerate(zip(result["prices"], result["weights"])):
            st.write(f"ポジション{i+1}: レート {p:.{decimals}f}, ロット {w:.4f}")

        st.write(f"計算平均建値: {result['avg_price']:.{decimals}f}")
        st.write(f"最大損失（円換算）: {result['total_loss']:.2f}")

    except Exception as e:
        st.error(f"計算中エラー: {e}")