# app.py
import streamlit as st

# --- 設定 ---
CURRENCY_PAIRS = [
    "USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY",
    "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF",
    "GOLD"
]

LOT_INFO = {
    "FX": 10000,    # 1lot=1万通貨
    "GOLD": 1       # 1lot=1oz
}

# 通貨ペアごとの小数桁数
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

# --- 計算ロジック ---
def calc_positions(pair, direction, division, weights, avg_price, max_loss, stop, upper, lower):
    division = int(division)
    weights = [float(w) for w in weights]

    # FXかGOLDかで単位
    unit = LOT_INFO["GOLD"] if pair=="GOLD" else LOT_INFO["FX"]

    # --- 有効ゾーン設定（ストップ衝突回避） ---
    margin = 0.01 if "JPY" in pair else 0.0001
    effective_upper = upper - margin if direction=="buy" else upper + margin
    effective_lower = lower + margin if direction=="buy" else lower - margin

    # --- 分割価格計算 ---
    prices = [effective_upper - i*(effective_upper-effective_lower)/(division-1) for i in range(division)]

    # --- 建値平均に合わせてロットスケーリング ---
    total_weighted_price = sum([w*p for w,p in zip(weights, prices)])
    total_weight = sum(weights)
    current_avg = total_weighted_price / total_weight

    scale = avg_price / current_avg if current_avg != 0 else 1
    weights = [w*scale for w in weights]

    # --- 最大損失チェック ---
    if direction=="buy":
        loss_per_unit = [max(0, p - stop) for p in prices]
    else:
        loss_per_unit = [max(0, stop - p) for p in prices]

    total_loss = sum([w*unit*l for w,l in zip(weights, loss_per_unit)])

    if total_loss > max_loss:
        factor = max_loss / total_loss
        weights = [w*factor for w in weights]
        total_loss = max_loss

    # --- 平均建値再計算 ---
    avg_calc = sum([w*p for w,p in zip(weights, prices)]) / sum(weights)

    return {
        "prices": prices,
        "weights": weights,
        "avg_price": avg_calc,
        "total_loss": total_loss
    }

# --- Streamlit UI ---
st.title("分割エントリー計算アプリ（ゾーン + 建値平均 + 成行対応）")

mode = st.radio("モード選択", ["事前ゾーン型", "成行起点型"])
mode_key = "zone" if mode=="事前ゾーン型" else "market"

pair = st.selectbox("通貨ペア/GOLD", CURRENCY_PAIRS)
direction = st.radio("方向", ["buy", "sell"])

# 小数桁数取得
decimals = get_decimal(pair)
fmt = f"%.{decimals}f"

# --- ゾーン上限下限入力 ---
upper = st.number_input("ゾーン上限", value=150.0 if "JPY" in pair else 1.0, format=fmt)
lower = st.number_input("ゾーン下限", value=149.5 if "JPY" in pair else 0.995, format=fmt)

division = st.number_input("分割数", min_value=2, max_value=5, value=3, step=1)
weights_input = st.text_input("ウェイト（カンマ区切り）例：2,2,4", value="2,2,4")
weights = [float(w.strip()) for w in weights_input.split(",")]

avg_price = st.number_input("目標平均建値", value=150.0 if "JPY" in pair else 1.0, format=fmt)
stop = st.number_input("ストップ価格", value=149.5 if "JPY" in pair else 0.995, format=fmt)
max_loss = st.number_input("最大損失（円）", value=5000.0)

market_price = None
if mode_key=="market":
    market_price = st.number_input("成行価格", value=150.1 if "JPY" in pair else 1.001, format=fmt)
    # 成行が上限/下限に自動設定
    if direction=="buy":
        upper = market_price
    else:
        lower = market_price

if st.button("計算"):
    result = calc_positions(
        pair=pair, direction=direction, division=division, weights=weights,
        avg_price=avg_price, max_loss=max_loss, stop=stop, upper=upper, lower=lower
    )
    if result:
        st.subheader("計算結果")
        for i,(p,w) in enumerate(zip(result["prices"], result["weights"])):
            st.write(f"ポジション{i+1}: レート {p:.{decimals}f}, ロット {w:.4f}")
        st.write(f"計算平均建値: {result['avg_price']:.{decimals}f}")
        st.write(f"最大損失（円換算）: {result['total_loss']:.2f}")
