# calc_positions関数の損失計算部分を修正
def calc_positions(pair, direction, division, weights, avg_price, max_loss, stop, upper, lower, usd_jpy_rate=1.0):
    division = int(division)
    weights = [float(w) for w in weights]
    unit = LOT_INFO["GOLD"] if pair=="GOLD" else LOT_INFO["FX"]

    # 分割価格計算
    margin = 0.01 if pair=="GOLD" or "JPY" in pair else 0.0001
    effective_upper = upper - margin if direction=="buy" else upper + margin
    effective_lower = lower + margin if direction=="buy" else lower - margin
    prices = [effective_upper - i*(effective_upper-effective_lower)/(division-1) for i in range(division)]

    # 建値平均補正
    total_weighted_price = sum([w*p for w,p in zip(weights, prices)])
    total_weight = sum(weights)
    current_avg = total_weighted_price / total_weight
    scale = avg_price / current_avg if current_avg != 0 else 1
    weights = [w*scale for w in weights]

    # 損失計算
    loss_per_unit = []
    for p in prices:
        if direction=="buy":
            diff = stop - p  # ストップ下
        else:
            diff = p - stop  # ストップ上
        diff = max(diff, 0)  # 負なら0
        loss_per_unit.append(diff)

    # USD建てペア/GOLDはUSDJPY換算
    if pair=="GOLD" or (not pair.endswith("JPY") and pair!="GOLD"):
        total_loss = sum([w*unit*l*usd_jpy_rate for w,l in zip(weights, loss_per_unit)])
    else:
        total_loss = sum([w*unit*l for w,l in zip(weights, loss_per_unit)])

    # 最大損失制限
    if total_loss > max_loss and total_loss > 0:
        factor = max_loss / total_loss
        weights = [w*factor for w in weights]
        total_loss = max_loss

    avg_calc = sum([w*p for w,p in zip(weights, prices)]) / sum(weights)
    return {
        "prices": prices,
        "weights": weights,
        "avg_price": avg_calc,
        "total_loss": total_loss
    }
