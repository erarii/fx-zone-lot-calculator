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
# USD/JPY 自動取得
# -------------------------
def fetch_usdjpy():
    try:
        url = "https://cdn.moneyconvert.net/api/latest.json"
        response = requests.get(url, timeout=5)
        data = response.json()
        usd_jpy = data["rates"].get("JPY")
        if usd_jpy is None:
            return None
        return float(usd_jpy)
    except:
        return None

# -------------------------
# 計算ロジック
# -------------------------
def calc_positions(pair, direction, division, weights, avg_price, max_loss, stop, upper, lower, usd_jpy_rate=1.0):
    division = int(division)
    weights = [float(w) for w in weights]

    if len(weights) != division:
        raise ValueError(f"ウェイトの数({len(weights)})と分割数({division})が一致していません。")

    unit = LOT_INFO["GOLD"] if pair=="GOLD" else LOT_INFO["FX"]

    # 分割価格（上限-下限を均等分割）
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

    # 損失計算（常に正の値になるように）
    loss_per_unit = []
    for p in prices:
        if direction=="buy":
            diff = stop - p
        else:
            diff = p - stop
        diff = abs(diff)  # 符号無視して絶対値
        # USD建て・GOLDはUSDJPYを掛けて円換算
        if pair=="GOLD" or (not pair.endswith("JPY") and pair!="GOLD"):
            diff *= usd_jpy_rate
        loss_per_unit.append(diff)

    # total_loss
    total_loss = sum([w*unit*l for w,l in zip(weights, loss_per_unit)])

    # 最大損失制限
    if total_loss > max_loss and total_loss > 0:
        factor = max_loss / total_loss
        weights = [w*factor for w in weights]
        total_loss = max_loss

    # 平均建値計算（加重平均）
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
st.title("分割エントリー計算アプリ（ゾーン + 建値平均 + 成行対応）")

# モード選択
mode = st.radio("モード選択", ["事前ゾーン型", "成行起点型"])

# 通貨ペア選択
pair = st.selectbox("通貨ペア/GOLD", CURRENCY_PAIRS)
direction = st.radio("方向", ["buy", "sell"])
decimals = get_decimal(pair)
fmt = f"%.{decimals}f"

# ゾーン上限下限
upper_default = 150.0 if "JPY" in pair else 1.0
lower_default = 149.5 if "JPY" in pair else 0.995
upper = st.number_input("ゾーン上限", value=upper_default, format=fmt)
lower = st.number_input("ゾーン下限", value=lower_default, format=fmt)

# 分割・ウェイト・平均建値・ストップ・最大損失
division = st.number_input("分割数", min_value=1, max_value=5, value=3, step=1)
weights_input = st.text_input("ウェイト（カンマ区切り）例：2,2,4", value="2,2,4")
weights = [w.strip() for w in weights_input.split(",")]
avg_price = st.number_input("目標平均建値", value=upper_default, format=fmt)
stop = st.number_input("ストップ価格", value=lower_default, format=fmt)
max_loss = st.number_input("最大損失（円）", value=10000.0)

# 成行モードの市場価格
market_price = None
if mode=="成行起点型":
    market_price = st.number_input("成行価格", value=upper_default, format=fmt)
    if direction=="buy":
        upper = market_price
    else:
        lower = market_price

# 計算ボタン
if st.button("計算"):
    usd_jpy_rate = 1.0
    if pair=="GOLD" or (not pair.endswith("JPY") and pair!="GOLD"):
        usd_jpy_rate = fetch_usdjpy()
        if usd_jpy_rate is None:
            st.warning("USD/JPY レート取得失敗。手動入力してください。")
            usd_jpy_rate = st.number_input("USD/JPY換算レート", value=150.0)
        else:
            st.write(f"最新 USD/JPY: {usd_jpy_rate:.3f}（自動取得）")

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
