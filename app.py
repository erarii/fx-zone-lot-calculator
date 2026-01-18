import streamlit as st
from dataclasses import dataclass
from typing import List

# ------------------------
# 定数（GMOデフォルト）
# ------------------------
FX_LOT_UNITS = 10_000      # 1 lot = 10,000通貨
XAU_LOT_OZ = 1             # 1 lot = 1 oz
PIP_JPY = 0.01
PIP_OTHER = 0.0001

# ------------------------
# ユーティリティ
# ------------------------
def is_jpy_quote(symbol: str) -> bool:
    return symbol.endswith("JPY")

def is_xau(symbol: str) -> bool:
    return symbol.upper() in ["XAUUSD", "GOLD"]

def pip_size(symbol: str) -> float:
    if is_xau(symbol):
        return 0.01  # XAUの最小変動（簡易）
    return PIP_JPY if is_jpy_quote(symbol) else PIP_OTHER

def loss_per_lot_jpy(symbol: str, entry: float, sl: float, usdjpy: float) -> float:
    """1 lotあたりのSL到達損失（円）"""
    diff = abs(entry - sl)
    if is_xau(symbol):
        # USD建て → JPY換算
        return diff * XAU_LOT_OZ * usdjpy
    if is_jpy_quote(symbol):
        # JPY建て
        return diff * FX_LOT_UNITS
    # 非JPY建て（例：EURUSD）
    # 1 pip = 10 USD / 1 lot(100k) → 今回は 10k なので 1 USD/pip
    # diff を価格差で受け、USD損益にしてJPY換算
    # 価格差 ÷ pip × USD/pip
    usd_per_pip = 1.0
    pips = diff / pip_size(symbol)
    usd_loss = pips * usd_per_pip
    return usd_loss * usdjpy

@dataclass
class Entry:
    price: float
    lot: float
    loss_jpy: float

def build_entries(
    symbol: str,
    market_price: float,
    zone_low: float,
    zone_high: float,
    sl: float,
    max_loss_jpy: float,
    splits: int,
    weights: List[int],
    usdjpy: float,
    initial_ratio_cap: float = 0.3
) -> List[Entry]:
    """
    C方式：
    - 初動：成行（market_price）
    - 残り：ゾーンを等分
    - lotは重み配分、総損失がmax_loss_jpyに収まるよう逆算
    """
    assert splits == len(weights)
    # 価格配列
    prices = [market_price]
    if splits > 1:
        step = (zone_high - zone_low) / (splits - 1)
        for i in range(1, splits):
            prices.append(zone_low + step * (i - 1))

    # 1 lotあたり損失（各価格）
    per_lot_losses = [
        loss_per_lot_jpy(symbol, p, sl, usdjpy) for p in prices
    ]

    # 重みで配分（初動は上限30%）
    total_w = sum(weights)
    raw_lots = []
    for i, w in enumerate(weights):
        share = w / total_w
        if i == 0:
            share = min(share, initial_ratio_cap)
        raw_lots.append(share)

    # 正規化
    s = sum(raw_lots)
    raw_lots = [r / s for r in raw_lots]

    # 総lotを逆算
    loss_per_unit = sum(r * l for r, l in zip(raw_lots, per_lot_losses))
    total_lot = max_loss_jpy / loss_per_unit

    entries = []
    for p, r, lpl in zip(prices, raw_lots, per_lot_losses):
        lot = total_lot * r
        entries.append(Entry(price=p, lot=lot, loss_jpy=lot * lpl))
    return entries

# ------------------------
# UI
# ------------------------
st.title("ゾーン分割エントリー計算（GMOデフォルト）")

symbol = st.selectbox(
    "銘柄",
    ["USDJPY", "EURUSD", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY", "XAUUSD"]
)

market_price = st.number_input("初動（成行）価格", value=150.00 if symbol=="USDJPY" else 1.1000)
zone_low = st.number_input("ゾーン下限", value=149.50)
zone_high = st.number_input("ゾーン上限", value=150.20)
sl = st.number_input("ストップロス", value=149.00)

max_loss = st.number_input("許容最大損失（円）", value=50_000, step=1_000)
splits = st.number_input("分割数", min_value=1, max_value=6, value=3)
weights_str = st.text_input("分割比率（例：3,1,2）", value="3,1,2")

usdjpy = st.number_input("USDJPY（円換算用・ダミー）", value=150.0)

if st.button("計算"):
    weights = [int(x.strip()) for x in weights_str.split(",")]
    entries = build_entries(
        symbol=symbol,
        market_price=market_price,
        zone_low=zone_low,
        zone_high=zone_high,
        sl=sl,
        max_loss_jpy=max_loss,
        splits=splits,
        weights=weights,
        usdjpy=usdjpy
    )

    total_loss = sum(e.loss_jpy for e in entries)
    avg_price = sum(e.price * e.lot for e in entries) / sum(e.lot for e in entries)

    st.subheader("結果")
    st.write(f"平均建値：{avg_price:.5f}")
    st.write(f"最大想定損失：{total_loss:,.0f} 円")

    st.table([
        {"価格": round(e.price, 5), "Lot": round(e.lot, 3), "想定損失（円）": round(e.loss_jpy, 0)}
        for e in entries
    ])
