import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from decimal import Decimal

# ==============================
# Google Sheets 認証
# ==============================
scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scope
)
client = gspread.authorize(creds)

SHEET_NAME = "旅行割り勘データ"  # あなたのシート名
spreadsheet = client.open(SHEET_NAME)

# メンバーシートを準備
try:
    member_sheet = spreadsheet.worksheet("members")
except gspread.exceptions.WorksheetNotFound:
    member_sheet = spreadsheet.add_worksheet(title="members", rows="50", cols="10")

# 費目シートを準備
try:
    expense_sheet = spreadsheet.worksheet("expenses")
except gspread.exceptions.WorksheetNotFound:
    expense_sheet = spreadsheet.add_worksheet(title="expenses", rows="200", cols="10")
    expense_sheet.append_row(["amount", "category", "payer", "participants", "exemptions", "desc"])


# ==============================
# メンバー管理
# ==============================
def save_members(members):
    member_sheet.clear()
    member_sheet.append_row(members)

def load_members():
    rows = member_sheet.get_all_values()
    if rows:
        return rows[0]
    return []


# ==============================
# UI
# ==============================
st.title("旅行用 割り勘アプリ（品目免除＋メンバー保存対応）")

# メンバー設定
st.subheader("メンバー設定")
members = load_members()
if not members:
    num_members = st.number_input("人数を入力してください", min_value=2, max_value=20, value=4, step=1)
    members = [st.text_input(f"メンバー {i+1} の名前", value=f"メンバー{i+1}", key=f"name{i}") for i in range(num_members)]
    if st.button("このメンバーで保存"):
        save_members(members)
        st.success("メンバーを保存しました。再読み込みすると反映されます。")
else:
    st.write("登録済みメンバー:", ", ".join(members))
    if st.button("メンバーをリセット"):
        member_sheet.clear()
        st.experimental_rerun()

categories = ["食事", "宿", "交通(高速/ガソリン)", "観光", "その他"]

# ==============================
# 費目の追加フォーム
# ==============================
st.subheader("費目を追加")
with st.form("add_expense", clear_on_submit=True):
    amount = st.number_input("金額 (円)", min_value=0, step=500)
    category = st.selectbox("費目カテゴリ", categories)
    payer = st.selectbox("支払者", members) if members else ""
    participants = st.multiselect("参加者", members, default=members)
    exemptions = st.multiselect("免除者（この費目は負担しない人）", members, default=[])

    desc = st.text_input("メモ（任意）")
    submitted = st.form_submit_button("追加")

    if submitted and amount > 0 and payer and participants:
        expense_sheet.append_row([
            str(amount), category, payer,
            ",".join(participants),
            ",".join(exemptions),
            desc
        ])
        st.success("Google Sheetsに保存しました！")

# ==============================
# 保存済みデータの表示と削除
# ==============================
st.subheader("登録済みの費目")
rows = expense_sheet.get_all_records()

if rows:
    for i, row in enumerate(rows, start=2):  # データは2行目以降
        st.write(row)
        if st.button(f"この行を削除 (行 {i})", key=f"del{i}"):
            expense_sheet.delete_rows(i)
            st.success(f"行 {i} を削除しました！")
            st.experimental_rerun()
else:
    st.info("まだデータがありません。")

# ==============================
# 割り勘計算
# ==============================
st.subheader("割り勘結果")

if members:
    paid = {m: 0 for m in members}   # 各人の支払総額
    owed = {m: 0 for m in members}   # 各人の負担総額

    for row in rows:
        amount = int(row["amount"])
        payer = row["payer"]
        participants = row["participants"].split(",") if row["participants"] else []
        exemptions = row["exemptions"].split(",") if row["exemptions"] else []

        # ウェイト計算：参加者=1, 免除者=0
        weights = {m: Decimal(0) for m in members}
        for m in participants:
            if m in weights and m not in exemptions:
                weights[m] = Decimal(1)

        total_w = sum(weights.values())
        if total_w > 0:
            shares = {m: (amount * weights[m] / total_w) for m in weights}
        else:
            shares = {m: 0 for m in weights}

        for m, s in shares.items():
            if m in owed:
                owed[m] += int(s)
        if payer in paid:
            paid[payer] += amount

    balances = {m: paid[m] - owed[m] for m in members}
    creditors = {m: bal for m, bal in balances.items() if bal > 0}
    debtors = {m: -bal for m, bal in balances.items() if bal < 0}

    transactions = []
    for debtor, d_amount in debtors.items():
        for creditor, c_amount in list(creditors.items()):
            if d_amount == 0:
                break
            pay = min(d_amount, c_amount)
            transactions.append(f"{debtor} → {creditor}: {int(pay)} 円")
            d_amount -= pay
            creditors[creditor] -= pay
            if creditors[creditor] == 0:
                del creditors[creditor]

    # 結果表示
    st.markdown("### 各人の内訳")
    st.table([{
        "メンバー": m,
        "支払合計(円)": paid[m],
        "負担合計(円)": owed[m],
        "差額(円)": balances[m]
    } for m in members])

    st.markdown("### 清算結果")
    if transactions:
        for t in transactions:
            st.write("✅ " + t)
    else:
        st.write("精算は必要ありません！")
