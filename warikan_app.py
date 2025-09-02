import streamlit as st
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List

st.set_page_config(page_title="旅行用 簡易割り勘アプリ", page_icon="🧮", layout="wide")
st.title("旅行用 簡易割り勘アプリ（費目＆免除対応）")

# ----------------------------
# ユーティリティ
# ----------------------------
def split_amount_exact(amount_yen: int, weights: Dict[str, Decimal]) -> Dict[str, int]:
    """
    金額を重みで按分し、各人の金額を円単位で割り当てる。
    合計が必ず amount_yen に一致するように、端数は小数部の大きい順に配分。
    """
    if amount_yen <= 0 or not weights:
        return {k: 0 for k in weights.keys()}

    total_w = sum(weights.values())
    if total_w == 0:
        # すべてウェイト0ならだれにも配分しない
        return {k: 0 for k in weights.keys()}

    # 生配分（小数）
    raw = {m: (Decimal(amount_yen) * w / total_w) for m, w in weights.items()}
    # 四捨五入で一旦丸め
    rounded = {m: int(x.quantize(Decimal("1"), rounding=ROUND_HALF_UP)) for m, x in raw.items()}

    diff = amount_yen - sum(rounded.values())
    if diff == 0:
        return rounded

    # 小数部の大きい順に端数を配る（diff > 0 なら +1、diff < 0 なら -1 で調整）
    # 小数部（raw - floor(raw)）を計算
    fracs = sorted(
        [(m, raw[m] - Decimal(int(raw[m]))) for m in raw.keys()],
        key=lambda x: x[1],
        reverse=(diff > 0),
    )
    idx = 0
    while diff != 0 and len(fracs) > 0:
        m = fracs[idx % len(fracs)][0]
        if diff > 0:
            rounded[m] += 1
            diff -= 1
        else:
            # 減らす時は、減らしすぎないようにチェック
            if rounded[m] > 0:
                rounded[m] -= 1
                diff += 1
        idx += 1

    return rounded


def greedy_settlement(balances_yen: Dict[str, int]) -> List[str]:
    """
    残高（+は受取、-は支払）から、誰が誰にいくら払うかを貪欲に生成。
    """
    creditors = [(m, amt) for m, amt in balances_yen.items() if amt > 0]
    debtors = [(m, -amt) for m, amt in balances_yen.items() if amt < 0]

    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    i = j = 0
    results = []
    while i < len(debtors) and j < len(creditors):
        d_name, d_amt = debtors[i]
        c_name, c_amt = creditors[j]
        pay = min(d_amt, c_amt)
        if pay > 0:
            results.append(f"{d_name} → {c_name}: {pay} 円")
        d_amt -= pay
        c_amt -= pay
        debtors[i] = (d_name, d_amt)
        creditors[j] = (c_name, c_amt)
        if d_amt == 0:
            i += 1
        if c_amt == 0:
            j += 1
    return results


# ----------------------------
# メンバー設定
# ----------------------------
with st.sidebar:
    st.header("設定")
    num_members = st.number_input("人数", min_value=2, max_value=30, value=8, step=1)
    members = []
    for i in range(num_members):
        name = st.text_input(f"メンバー{i+1}の名前", value=f"メンバー{i+1}", key=f"name{i}")
        members.append(name)

    st.markdown("---")
    st.subheader("役割 / 免除ルール")
    # 費目の一覧（カンマ区切りで拡張可能）
    categories_default = "食事, 宿, 交通(高速/ガソリン), 観光, その他"
    cats_text = st.text_input("費目（カンマ区切りで編集可）", value=categories_default)
    categories = [c.strip() for c in cats_text.split(",") if c.strip()]

    drivers = st.multiselect("運転者（複数可）", options=members, default=[])
    exempt_driver_highway = st.checkbox("運転者は『交通(高速/ガソリン)』の負担を免除（=0円）", value=True)

    with st.expander("追加の手動調整（円）"):
        st.caption("＋は負担減（割引）、−は負担増（上乗せ）として最終負担に反映されます。")
        manual_adjust = {m: st.number_input(f"{m}", value=0, step=100, key=f"adj_{m}") for m in members}

# ----------------------------
# 費目の登録フォーム
# ----------------------------
if "expenses" not in st.session_state:
    st.session_state.expenses = []

st.subheader("費目の登録")
with st.form("add_expense", clear_on_submit=True):
    c1, c2, c3 = st.columns([1.1, 1.1, 1.2])
    with c1:
        amount = st.number_input("金額 (円)", min_value=0, step=1000)
        category = st.selectbox("費目", options=categories, index=min(len(categories)-1, categories.index("その他") if "その他" in categories else 0))
    with c2:
        payer = st.selectbox("支払者", options=members)
        desc = st.text_input("メモ / 内容（任意）", value="")
    with c3:
        participants = st.multiselect("この費目を負担する参加者", options=members, default=members)

    submitted = st.form_submit_button("追加")
    if submitted and amount > 0 and payer and len(participants) > 0:
        st.session_state.expenses.append({
            "amount": int(amount),
            "category": category,
            "payer": payer,
            "participants": participants,
            "desc": desc
        })
        st.success("費目を追加しました！")
    elif submitted:
        st.warning("金額・支払者・参加者を確認してください。")

# クリアボタン
col_a, col_b = st.columns([1, 3])
with col_a:
    if st.button("全費目をクリア", type="secondary"):
        st.session_state.expenses = []
        st.info("費目を全て削除しました。")

# ----------------------------
# 登録済み費目の表示
# ----------------------------
st.subheader("登録済みの費目")
if len(st.session_state.expenses) == 0:
    st.write("まだ費目がありません。上のフォームから追加してください。")
else:
    st.dataframe(
        [{
            "金額": e["amount"],
            "費目": e["category"],
            "支払者": e["payer"],
            "参加者": " / ".join(e["participants"]),
            "内容": e["desc"]
        } for e in st.session_state.expenses],
        use_container_width=True
    )

# ----------------------------
# 集計・精算
# ----------------------------
st.subheader("集計と清算")

paid = {m: 0 for m in members}   # 各人の支払総額
owed = {m: 0 for m in members}   # 各人の負担総額

# 各費目の配分
for e in st.session_state.expenses:
    amt = e["amount"]
    cat = e["category"]
    payer = e["payer"]
    participants = e["participants"]

    # ウェイト初期化（参加者=1、非参加者=0）
    weights = {m: Decimal(0) for m in members}
    for m in participants:
        weights[m] = Decimal(1)

    # 運転者免除ルール：交通(高速/ガソリン) のとき、運転者のウェイトを0
    if exempt_driver_highway and "交通" in cat:
        for drv in drivers:
            if drv in weights:
                weights[drv] = Decimal(0)

    # 実配分（端数調整込みで合計=amtに一致）
    shares = split_amount_exact(int(amt), weights)

    # 負担と支払を計上
    for m, s in shares.items():
        owed[m] += s
    paid[payer] += int(amt)

# 手動調整を適用（＋で負担減、−で負担増）
for m in members:
    owed[m] = max(0, owed[m] - int(manual_adjust[m]))

# 残高（＋は受取、−は支払）
balances = {m: paid[m] - owed[m] for m in members}

# 結果表示：各人の内訳
st.markdown("### 各人の内訳")
st.table([{
    "メンバー": m,
    "支払合計(円)": paid[m],
    "負担合計(円)": owed[m],
    "差額(円)": balances[m]
} for m in members])

# 精算取引
transactions = greedy_settlement(balances)
st.markdown("### 清算結果（誰が誰にいくら払うか）")
if transactions:
    for t in transactions:
        st.write("✅ " + t)
else:
    st.write("精算は必要ありません！")

# ダウンロード（CSV）
import io, csv
buf = io.StringIO()
writer = csv.writer(buf)
writer.writerow(["From(支払う人)", "To(受け取る人)", "Amount(円)"])
for line in transactions:
    # "A → B: 123 円" をパース
    try:
        left, yen = line.split(":")
        frm, to = [x.strip() for x in left.split("→")]
        amt = int(yen.strip().replace("円", "").strip())
        writer.writerow([frm, to, amt])
    except Exception:
        pass

st.download_button(
    "取引リストをCSVで保存",
    data=buf.getvalue().encode("utf-8-sig"),
    file_name="warikan_transactions.csv",
    mime="text/csv",
    disabled=(len(transactions) == 0)
)
