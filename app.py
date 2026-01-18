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

# --- ユーティリティ関数 ---
def calc_positions(mode, pair, division, weights, avg_price, max_loss, stop, market_price=None, direction="buy"):
    """
    計算ロジック
    - mode: 'zone' or 'market'
    - division: 分割数
    - weights: 入力ウェイトリスト
    - avg_price: 目標平均建値
    - max_loss: 最大損失（円）
    - stop: ストップ価格
    - market_price: 成行価格
    - direction: "buy" or "sell"
    """
    division = int(division)
    weights = [float(w) for w in weights]

    # FXかGOLDかで単位
    unit = LOT_INFO["GOLD"] if pair=="GOLD" else LOT_INFO["FX"]

    # --- 価格計算 ---
    if mode == "zone":
        # 等間隔で上限下限を仮定
        if direction=="buy":
            upper = avg_price + 0.5*(avg_price - stop)  # 推奨:下限ストップから平均を基準に上限仮定
            lower = stop
        else:
            lower = avg_price - 0.5*(stop - avg_price)
            upper = stop
        prices = [upper - i*(upper-lower)/(division-1) for i in range(division)]
    elif mode == "market":
        if not market_price:
            st.error("成行価格を入力してください")
            return
        # 成行がゾーン上限（買い）or下限（売り）
        if direction=="buy":
            upper = market_price
            lower = stop
            prices = [upper - i*(upper-lower)/(division-1) for i in range(division)]
        else:
            lower = market_price
            upper = stop
            prices = [lower + i*(upper-lower)/(division-1) for i in range(division)]
    else:
        st.error("modeエラー")
        return

    # --- ロット調整 ---
    # 建値平均に合わせてスケーリング
    total_weighted_price = sum([w*p for w,p in zip(weights, prices)])
    total_weight = sum(weights)
    current_avg = total_weighted_price / total_weight

    scale = 1
    if current_avg != avg_price:
        scale = 1  # 初期はスケール1、後で最大損失対応
        # ロットをスケーリング
        weights = [w * (avg_price / current_avg) for w in weights]

    # --- 最大損失チェック ---
    # 含み損計算
    if direction=="buy":
        loss_per_unit = [max(0, p - stop) for p in prices]
    else:
        loss_per_unit = [max(0, stop - p) for p in prices]

    total_loss = sum([w*u*l for w,u,l in zip(weights, [unit]*division, loss_per_unit)])
    # 最大損失超過時にスケール調整
    if total_loss > max_loss:
        factor = max_loss / total_loss
        weights = [w*factor for w in weights]
        total_loss = max_loss

    return {
        "prices": prices,
        "weights": weights,
        "avg_price": sum([w*p for w,p in zip(weights, prices)])/sum(weights),
        "total_loss": total_loss
    }

# --- Streamlit UI ---
st.title("分割エントリー計算アプリ（平均建値入力対応）")

mode = st.radio("モード選択", ["事前ゾーン型", "成行起点型"])
mode_key = "zone" if mode=="事前ゾーン型" else "market"

pair = st.selectbox("通貨ペア/GOLD", CURRENCY_PAIRS)
direction = st.radio("方向", ["buy", "sell"])

division = st.number_input("分割数", min_value=2, max_value=5, value=3, step=1)

weights_input = st.text_input("ウェイト（カンマ区切り）例：2,2,4", value="2,2,4")
weights = [float(w.strip()) for w in weights_input.split(",")]

avg_price = st.number_input("目標平均建値", value=150.0 if "JPY" in pair else 1.0)
stop = st.number_input("ストップ価格", value=149.5 if "JPY" in pair else 0.995)
max_loss = st.number_input("最大損失（円）", value=5000.0)

market_price = None
if mode_key=="market":
    market_price = st.number_input("成行価格", value=150.1 if "JPY" in pair else 1.001)

if st.button("計算"):
    result = calc_positions(
        mode=mode_key, pair=pair, division=division, weights=weights,
        avg_price=avg_price, max_loss=max_loss, stop=stop,
        market_price=market_price, direction=direction
    )
    if result:
        st.subheader("計算結果")
        for i,(p,w) in enumerate(zip(result["prices"], result["weights"])):
            st.write(f"ポジション{i+1}: レート {p:.4f}, ロット {w:.4f}")
        st.write(f"計算平均建値: {result['avg_price']:.4f}")
        st.write(f"最大損失（円換算）: {result['total_loss']:.2f}")
