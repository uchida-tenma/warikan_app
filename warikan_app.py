import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ==============================
# Google Sheets 認証
# ==============================
scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scope
)
client = gspread.authorize(creds)

# あなたが作ったスプレッドシート名に置き換える
SHEET_NAME = "旅行割り勘データ"
worksheet = client.open(SHEET_NAME).sheet1

# ==============================
# Streamlit UI
# ==============================
st.title("旅行用 簡易割り勘アプリ（Google Sheets連携版）")

# --- メンバー人数を指定 ---
num_members = st.number_input("人数を入力してください", min_value=2, max_value=20, value=4, step=1)

# --- メンバー名と支払額入力 ---
st.subheader("メンバー名と支払金額")
members = []
payments = []
for i in range(num_members):
    col1, col2 = st.columns([2, 1])
    with col1:
        name = st.text_input(f"メンバー {i+1} の名前", value=f"メンバー{i+1}", key=f"name{i}")
    with col2:
        payment = st.number_input(f"{name} が支払った金額 (円)", min_value=0, step=500, key=f"pay{i}")
    members.append(name)
    payments.append(payment)

# ==============================
# Google Sheets 保存
# ==============================
if st.button("この支払をGoogle Sheetsに追加"):
    worksheet.append_row([
        ", ".join(members), 
        ", ".join(map(str, payments))
    ])
    st.success("Google Sheetsに保存しました！")

# ==============================
# Google Sheets 読み込み
# ==============================
st.subheader("これまでに保存されたデータ（Google Sheetsから読み込み）")
rows = worksheet.get_all_records()
if rows:
    st.dataframe(rows)
else:
    st.info("まだデータがありません。")

# ==============================
# 割り勘計算
# ==============================
st.subheader("割り勘結果")

total = sum(payments)
per_person = total / num_members if num_members > 0 else 0
st.write(f"💰 総額: {total} 円")
st.write(f"🙋 一人あたり: {per_person:.0f} 円")

balances = {m: p - per_person for m, p in zip(members, payments)}
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

st.subheader("清算結果")
if transactions:
    for t in transactions:
        st.write("✅ " + t)
else:
    st.write("精算は必要ありません！")
