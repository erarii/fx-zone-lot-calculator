import streamlit as st
from dataclasses import dataclass
from typing import List

# =========================
# データ構造
# =========================
@dataclass
class Entry:
    price: float
    weight: float
    lot: float = 0.0

# =========================
# JPY換算ロジック
# =========================
def pip_value_jpy(pair: str, usd_jpy: float, lot_size: int):
    if pair.endswith("JPY"):
        return 100 * lot_size / 10000
    elif pair == "GOLD":
        return usd_jpy
    else:
        return 100 * usd_jpy * lot_size / 10000

# =========================
# 平均建値計算
# =========================
def weighted_average(entries: List[Entry]):
    total_w = sum(e.weight for e in entries)
    return sum(e.price * e.weight for e in entries) / total_w

# =========================
# ロット自動計算
# =========================
def calculate_lots(entries, avg_target, stop_price, max_loss_jpy, pip_jpy):
    avg_price = weighted_average(entries)
    risk_per_lot = abs(avg_price - stop_price) * pip_jpy

    total_weight = sum(e.weight for e in entries)
    total_lot = max_loss_jpy / risk_per_lot

    for e in entries:
        e.lot = total_lot * (e.weight / total_weight)

    return entries, avg_price, total_lot

# =========================
# UI
# =========================
st.title("建値平均ベース ロット計算")

pair = st.selectbox(
    "通貨ペア",
    ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY",
     "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "GOLD"]
)

usd_jpy = st.number_input("USDJPY レート", value=150.0)

lot_type = st.selectbox("1lot単位", ["1万通貨（GMO）", "10万通貨"])
lot_size = 10000 if lot_type == "1万通貨（GMO）" else 100000

max_loss = st.number_input("許容最大損失（円）", value=10000)
stop_price = st.number_input("ストップロス価格")

st.subheader("エントリー設定")

prices = st.text_input("エントリー価格（カンマ区切り）", "100,95,90")
weights = st.text_input("ウェイト（カンマ区切り）", "2,2,4")

if st.button("計算"):
    price_list = list(map(float, prices.split(",")))
    weight_list = list(map(float, weights.split(",")))

    entries = [Entry(p, w) for p, w in zip(price_list, weight_list)]

    pip_jpy = pip_value_jpy(pair, usd_jpy, lot_size)

    entries, avg_price, total_lot = calculate_lots(
        entries, avg_target=None, stop_price=stop_price,
        max_loss_jpy=max_loss, pip_jpy=pip_jpy
    )

    st.markdown("### 結果")
    st.write(f"**平均建値**：{avg_price:.4f}")
    st.write(f"**総ロット**：{total_lot:.2f}")

    for i, e in enumerate(entries, 1):
        st.write(f"{i}. 価格 {e.price} / ロット {e.lot:.2f}")
