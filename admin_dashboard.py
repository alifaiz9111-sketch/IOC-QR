import io
import os
import re
import time
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import streamlit as st
from supabase import create_client, Client
import pandas as pd

from PIL import Image

# Load logo for browser tab favicon
logo_img = "Indian_Oil_Logo.png" if os.path.exists("Indian_Oil_Logo.png") else "⛽"

st.set_page_config(page_title="IOCL Portal", page_icon=logo_img, layout="wide")

# IndianOil Theme CSS Injection (#f37022)
st.markdown(
    """
    <style>
    div.stButton > button:first-child,
    div.stDownloadButton > button:first-child {
        background-color: #f37022 !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    div.stButton > button:first-child:hover,
    div.stDownloadButton > button:first-child:hover {
        background-color: #d85c14 !important;
        color: white !important;
    }
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #f37022 !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover {
        background-color: #d85c14 !important;
        color: white !important;
    }
    div[data-testid="stMetricValue"] {
        color: #f37022 !important;
        font-weight: 700 !important;
    }
    div[data-testid="stMetric"] {
        background: transparent !important;
        border: none !important;
        border-left: 4px solid #f37022 !important;
        padding: 6px 14px !important;
        border-radius: 0px !important;
    }
    h2, h3, h4, h5, h6 {
        color: #1e293b;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #f37022 !important;
        border-bottom-color: #f37022 !important;
    }
    div[data-baseweb="checkbox"] input:checked + div {
        background-color: #f37022 !important;
        border-color: #f37022 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = init_supabase()

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Report")
    return output.getvalue()

def send_custom_report(recipient_email: str):
    today = datetime.now()
    seven_days_ago = (today - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00")

    entries_res = db.table("campaign_entries").select("*").gte("created_at", seven_days_ago).execute()
    outlets_res = db.table("retail_outlets").select("ro_code, ro_name, district, sales_area").execute()
    vouchers_res = db.table("voucher_vault").select("ro_code, denomination, status").execute()

    df_e = pd.DataFrame(entries_res.data or [])
    df_o = pd.DataFrame(outlets_res.data or [])
    df_v = pd.DataFrame(vouchers_res.data or [])

    if not df_e.empty and not df_o.empty:
        df_e = df_e.merge(df_o, on="ro_code", how="left")
        ro_summary = df_e.groupby(["ro_code", "ro_name", "district"]).agg(
            Total_Scans=("bill_number", "count"),
            Total_Sales_Value=("amount", "sum"),
            Vouchers_Won=("outcome", lambda x: (x.astype(str).str.lower() == "won").sum()),
            Unique_Customers=("phone_number", "nunique")
        ).reset_index().sort_values(by="Total_Scans", ascending=False)
    else:
        ro_summary = pd.DataFrame({"Status": ["No scans in the last 7 days"]})

    vault_summary = df_v.groupby(["ro_code", "status"]).size().unstack(fill_value=0).reset_index() if not df_v.empty else pd.DataFrame({"Status": ["No voucher data"]})

    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        ro_summary.to_excel(writer, sheet_name="RO_Weekly_Performance", index=False)
        vault_summary.to_excel(writer, sheet_name="Voucher_Inventory", index=False)
        if not df_e.empty:
            df_e.to_excel(writer, sheet_name="Transaction_Audit", index=False)
        else:
            pd.DataFrame({"Status": ["No transactions logged"]}).to_excel(writer, sheet_name="Transaction_Audit", index=False)

    excel_buffer.seek(0)
    date_str = today.strftime("%d-%b-%Y")
    scan_count = len(df_e)
    total_sales = float(df_e["amount"].sum()) if not df_e.empty and "amount" in df_e.columns else 0.0

    sender_email = st.secrets["SMTP_SENDER_EMAIL"]
    sender_password = st.secrets["SMTP_SENDER_PASSWORD"]

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = f"IOCL Kolkata DO - Weekly Campaign MIS Report ({date_str})"

    body = f"""Dear Sir,

Please find attached the Weekly Campaign MIS Report for the QR Sales Promotion Campaign (MS/XP95/XP100) under Kolkata Divisional Office.

Weekly Summary:
- Total Scans/Entries: {scan_count:,}
- Total Fuel Sales Value Recorded: ₹{total_sales:,.2f}

Detailed outlet-wise breakups, voucher vault statuses, and audit transactions are included in the attached spreadsheet.

Warm regards,
Adnet Advertising Campaign Operations Team
"""
    msg.attach(MIMEText(body, "plain"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(excel_buffer.getvalue())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename=IOCL_Weekly_MIS_{date_str}.xlsx")
    msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [recipient_email], msg.as_string())

for key, default in [
    ("authenticated", False),
    ("user_role", None),
    ("ro_code", None),
    ("ro_name", None),
    ("login_error", None)
]:
    if key not in st.session_state:
        st.session_state[key] = default

def login(username, password):
    dev_user = st.secrets.get("DEV_USER", "dev")
    dev_pass = st.secrets.get("DEV_PASSWORD", "devpassword")
    admin_user = st.secrets.get("ADMIN_USER", "admin")
    admin_pass = st.secrets.get("ADMIN_PASSWORD", "IOCL@Admin2026")

    # 1. Developer Login
    if username == dev_user and password == dev_pass:
        st.session_state.authenticated = True
        st.session_state.user_role = "dev"
        st.session_state.ro_code = None
        st.session_state.ro_name = "Developer Console"
        st.session_state.login_error = None
        st.rerun()

    # 2. Executive Admin Login
    if username == admin_user and password == admin_pass:
        st.session_state.authenticated = True
        st.session_state.user_role = "admin"
        st.session_state.ro_code = None
        st.session_state.ro_name = "Divisional Office"
        st.session_state.login_error = None
        st.rerun()

    # 3. Retail Outlet Dealer Login
    try:
        res = db.table("retail_outlets").select("ro_code, ro_name, password").eq("ro_code", username).execute()
        if res.data:
            ro_row = res.data[0]
            stored_password = ro_row.get("password") or ro_row["ro_code"]
            if password == stored_password:
                st.session_state.authenticated = True
                st.session_state.user_role = "ro"
                st.session_state.ro_code = row_val if (row_val := ro_row.get("ro_code")) else ro_row["ro_code"]
                st.session_state.ro_name = ro_row["ro_name"]
                st.session_state.login_error = None
                st.rerun()
    except Exception as e:
        st.session_state.login_error = f"Database error: {e}"
        return

    st.session_state.login_error = "Invalid Username or Password. Please try again."

def logout():
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.ro_code = None
    st.session_state.ro_name = None
    st.session_state.login_error = None
    st.cache_data.clear()
    st.rerun()

LOCAL_LOGO_PATH = "Indian_Oil_Logo.png"
PROD_FALLBACK_URL = "https://images.seeklogo.com/logo-png/19/1/indian-oil-logo-png_seeklogo-198933.png"

# ----------------- LOGIN SCREEN -----------------
if not st.session_state.authenticated:
    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        sub_c1, sub_c2, sub_c3 = st.columns([1, 1.2, 1])
        with sub_c2:
            if os.path.exists(LOCAL_LOGO_PATH):
                st.image(LOCAL_LOGO_PATH, use_container_width=True)
            else:
                st.image(PROD_FALLBACK_URL, use_container_width=True)

        st.markdown("<h3 style='text-align: center; margin-top: -35px; margin-left: 25px;'>IndianOil</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray; margin-bottom: 20px;'>Retail Campaign Management Portal</p>", unsafe_allow_html=True)

        if st.session_state.login_error:
            st.error(st.session_state.login_error)

        with st.form("login_form"):
            user_input = st.text_input("Login ID / RO Code", placeholder="e.g. dev, admin or 360126")
            pass_input = st.text_input("Password", type="password", placeholder="Enter your password")
            submit_btn = st.form_submit_button("Sign In", use_container_width=True)
            if submit_btn:
                login(user_input.strip(), pass_input.strip())

    st.stop()

# ==============================================================================
# EXECUTIVE ADMIN DASHBOARD ONLY (BRAND THEME + LEFT SIDEBAR + 19+1 WINNERS)
# ==============================================================================
if st.session_state.user_role == "admin":
    EMBEDDED_19_PLUS_1 = [
        {"rank": 1, "name": "Akshat Bhardwaj", "phone": "89XXXX9956", "ro_code": "138854", "ro_name": "TRINATH SERVICE STATION", "sales_area": "Barasat RSA", "bill_no": "587940", "prize": "Apple iPhone 17 Pro Max"},
        {"rank": 2, "name": "Rio das", "phone": "62XXXX4145", "ro_code": "196643", "ro_name": "PAUL CHOWDHURY ENTERP", "sales_area": "Barasat RSA", "bill_no": "207725", "prize": "vivo 5G Smartphone"},
        {"rank": 3, "name": "Ruma Barat", "phone": "97XXXX7829", "ro_code": "164774", "ro_name": "MADHABI SERVICE STN", "sales_area": "Garia RSA", "bill_no": "534165", "prize": "vivo 5G Smartphone"},
        {"rank": 4, "name": "Anupam Mukhopadhyay", "phone": "89XXXX8987", "ro_code": "190654", "ro_name": "PRASADPUR SERVICE STATION", "sales_area": "Garia RSA", "bill_no": "340068", "prize": "vivo 5G Smartphone"},
        {"rank": 5, "name": "Amitava Pal", "phone": "81XXXX4776", "ro_code": "338777", "ro_name": "SOUTHERN FUEL SERVICE", "sales_area": "Garia RSA", "bill_no": "222530", "prize": "vivo 5G Smartphone"},
        {"rank": 6, "name": "Hirak Mukherjee", "phone": "70XXXX2240", "ro_code": "191100", "ro_name": "MANMATHA SERVICE CENTRE", "sales_area": "Kalyani RSA", "bill_no": "55566", "prize": "vivo 5G Smartphone"},
        {"rank": 7, "name": "Khyati Chopra", "phone": "84XXXX4168", "ro_code": "138056", "ro_name": "LAUHATI SERVICE STN", "sales_area": "Kolkata New Town RSA", "bill_no": "206886", "prize": "vivo 5G Smartphone"},
        {"rank": 8, "name": "Uma mondal", "phone": "90XXXX5784", "ro_code": "331989", "ro_name": "AGNIV SERVICE STATION", "sales_area": "Kolkata New Town RSA", "bill_no": "688346", "prize": "vivo 5G Smartphone"},
        {"rank": 9, "name": "TAPAN KUMAR SARKAR", "phone": "98XXXX7296", "ro_code": "138621", "ro_name": "DELUXE SERVICE STN", "sales_area": "Kolkata South RSA", "bill_no": "407120", "prize": "vivo 5G Smartphone"},
        {"rank": 10, "name": "Jadunathchauhan", "phone": "94XXXX9286", "ro_code": "138709", "ro_name": "LUXMI NARAYAN SER. STN", "sales_area": "Kolkata South RSA", "bill_no": "109073", "prize": "vivo 5G Smartphone"},
        {"rank": 11, "name": "Mukesh Desai", "phone": "84XXXX2272", "ro_code": "190519", "ro_name": "JEET SERVICE STATION", "sales_area": "Kolkata South RSA", "bill_no": "295240", "prize": "vivo 5G Smartphone"},
        {"rank": 12, "name": "Tushar Pujara", "phone": "91XXXX7213", "ro_code": "190523", "ro_name": "OM AUTO SERVICE CORPORATION", "sales_area": "Kolkata South RSA", "bill_no": "994231", "prize": "vivo 5G Smartphone"},
        {"rank": 13, "name": "Saptarshi Dasgupta", "phone": "89XXXX2597", "ro_code": "137977", "ro_name": "B C DUTTA & BROTHERS", "sales_area": "Kolkata-North RSA", "bill_no": "808822", "prize": "vivo 5G Smartphone"},
        {"rank": 14, "name": "Pooja Verma", "phone": "96XXXX8345", "ro_code": "138661", "ro_name": "HIRJEE AUTO CENTRE", "sales_area": "Kolkata-North RSA", "bill_no": "489947", "prize": "vivo 5G Smartphone"},
        {"rank": 15, "name": "Monali Paswan", "phone": "98XXXX0269", "ro_code": "189016", "ro_name": "HAPPY SERVICE STATION", "sales_area": "Kolkata-North RSA", "bill_no": "962116", "prize": "vivo 5G Smartphone"},
        {"rank": 16, "name": "Myra Kotecha", "phone": "97XXXX1600", "ro_code": "191111", "ro_name": "THE JANATA S/STATION", "sales_area": "Kolkata-North RSA", "bill_no": "506656", "prize": "vivo 5G Smartphone"},
        {"rank": 17, "name": "Madhurima Midya", "phone": "96XXXX8692", "ro_code": "151172", "ro_name": "MA DURGA FUEL STN", "sales_area": "Krishnanagar RSA", "bill_no": "138810", "prize": "vivo 5G Smartphone"},
        {"rank": 18, "name": "Priyanka Dutta", "phone": "94XXXX6972", "ro_code": "240739", "ro_name": "G.Q.MONDAL SERVICE STATION", "sales_area": "24 Parganas(S) RSA", "bill_no": "546568", "prize": "vivo 5G Smartphone"},
        {"rank": 19, "name": "Kakoli De-Sarkar", "phone": "94XXXX1919", "ro_code": "385566", "ro_name": "ADHOC MATRI MONDIR FUEL STATION", "sales_area": "Kolkata New Town RSA", "bill_no": "169743", "prize": "vivo 5G Smartphone"},
        {"rank": 20, "name": "Yuvaan Bhojani", "phone": "97XXXX3991", "ro_code": "392418", "ro_name": "ADHOC MAA SIDDHESHWARI FUEL STATION", "sales_area": "Kalyani RSA", "bill_no": "783884", "prize": "vivo 5G Smartphone"},
    ]

    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1240px !important;
            padding-top: 1.4rem !important;
            padding-bottom: 3rem !important;
        }
        [data-testid="stSidebar"] {
            background-color: #fffdf9 !important;
            border-right: 1px solid #fde2cf !important;
        }
        div.stButton > button {
            background-color: #f37022 !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 6px !important;
            font-weight: 700 !important;
            font-size: 13px !important;
            padding: 9px 18px !important;
            transition: all 0.2s ease !important;
        }
        div.stButton > button:hover {
            background-color: #d85c14 !important;
            color: #ffffff !important;
            transform: translateY(-1px) !important;
        }
        .brand-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-left: 4px solid #f37022;
            border-radius: 10px;
            padding: 20px 22px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
            height: 100%;
        }
        .brand-card-title {
            font-size: 16px;
            font-weight: 700;
            color: #1e293b;
            margin: 0;
        }
        .brand-badge {
            display: inline-block;
            background: #fff7ed;
            border: 1px solid #fed7aa;
            color: #c2410c;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
        }
        .bar-chart-grid {
            display: grid;
            grid-template-columns: repeat(8, 1fr);
            gap: 12px;
            align-items: end;
            height: 210px;
            padding: 10px 4px 0 4px;
        }
        .bar-col-wrap {
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100%;
            justify-content: flex-end;
        }
        .bar-track {
            width: 24px;
            height: 160px;
            background: #fff7ed;
            border: 1px solid #ffedd5;
            border-radius: 6px;
            display: flex;
            align-items: flex-end;
            justify-content: center;
        }
        .bar-fill {
            width: 22px;
            background: linear-gradient(180deg, #f37022 0%, #d85c14 100%);
            border-radius: 5px;
            transition: height 0.5s ease;
        }
        .bar-val-tag {
            font-size: 12px;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 5px;
        }
        .bar-lbl {
            font-size: 11px;
            color: #475569;
            margin-top: 8px;
            text-align: center;
            font-weight: 600;
            white-space: nowrap;
        }
        .spotlight-box {
            background: #fffdf9;
            border: 1px solid #fde2cf;
            border-radius: 8px;
            padding: 12px 14px;
            margin-top: 12px;
        }
        @keyframes rowFadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .brand-table-wrap {
            width: 100%;
            overflow-x: auto;
            margin-top: 6px;
        }
        .brand-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            background: #ffffff;
        }
        .brand-table thead th {
            text-align: left;
            color: #1e293b;
            background: #fff7ed;
            font-weight: 700;
            font-size: 12px;
            padding: 11px 14px;
            border-bottom: 2px solid #f37022;
        }
        .brand-table tbody tr {
            border-bottom: 1px solid #e2e8f0;
            animation: rowFadeIn 0.35s ease both;
        }
        .brand-table tbody tr:hover {
            background: #fffdf9;
        }
        .brand-table tbody tr.grand-row {
            background: #fff7ed;
            border-top: 2px solid #f37022;
            border-bottom: 2px solid #f37022;
        }
        .brand-table td {
            padding: 12px 14px;
            color: #1e293b;
            vertical-align: middle;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Left Block: Sidebar with IndianOil Logo, Name, Logged-in User & Logout Button
    with st.sidebar:
        sb_c1, sb_c2, sb_c3 = st.columns([1, 2, 1])
        with sb_c2:
            if os.path.exists(LOCAL_LOGO_PATH):
                st.image(LOCAL_LOGO_PATH, use_container_width=True)
            else:
                st.image(PROD_FALLBACK_URL, use_container_width=True)
        st.markdown("<h4 style='text-align: center; margin-top: -20px; color: #1e293b;'>IndianOil</h4>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 13px; margin-bottom: 14px;'>Retail Campaign Management Portal</p>", unsafe_allow_html=True)
        st.divider()
        st.markdown(f"**Logged in:** {st.session_state.ro_name}")
        if st.button("Logout", use_container_width=True, key="admin_sidebar_logout"):
            st.session_state.admin_reveal_list_done = False
            st.session_state.admin_reveal_iphone_done = False
            logout()

    @st.cache_data(ttl=60)
    def load_admin_winners():
        base_dir = Path(__file__).resolve().parent
        excel_path = base_dir / "19+1.xlsx"
        target_path = str(excel_path) if excel_path.exists() else "19+1.xlsx"
        records = None

        if os.path.exists(target_path):
            try:
                df = pd.read_excel(target_path, dtype=str)
                df.columns = [str(c).strip() for c in df.columns]

                def find_col(candidates):
                    for cand in candidates:
                        for col in df.columns:
                            if cand.lower() in col.lower():
                                return col
                    return None

                col_rank = find_col(["rank", "position", "prize_no", "sl", "serial"])
                col_name = find_col(["customer_name", "winner_name", "winner", "name"])
                col_phone = find_col(["phone", "mobile", "contact"])
                col_ro_code = find_col(["ro_code", "ro code", "outlet_code"])
                col_ro_name = find_col(["ro_name", "ro name", "outlet_name", "station"])
                col_area = find_col(["sales_area", "sales area", "rsa", "area", "district"])
                col_bill = find_col(["bill", "receipt", "invoice"])
                col_prize = find_col(["prize", "reward", "gift", "item"])

                parsed = []
                for idx, row in df.iterrows():
                    raw_rank = None
                    if col_rank and pd.notna(row[col_rank]):
                        digits = re.findall(r"\d+", str(row[col_rank]))
                        if digits:
                            raw_rank = int(digits[0])
                    if raw_rank is None:
                        raw_rank = idx + 1

                    raw_phone = str(row[col_phone]).strip() if col_phone and pd.notna(row[col_phone]) else ""
                    masked_phone = (
                        f"{raw_phone[:2]}XXXX{raw_phone[-4:]}"
                        if len(raw_phone) == 10 and raw_phone.isdigit()
                        else raw_phone
                    )

                    default_prize = "Apple iPhone 17 Pro Max" if raw_rank == 1 else "vivo 5G Smartphone"
                    parsed.append({
                        "rank": raw_rank,
                        "name": str(row[col_name]).strip() if col_name and pd.notna(row[col_name]) else "Verified Participant",
                        "phone": masked_phone,
                        "ro_code": str(row[col_ro_code]).strip() if col_ro_code and pd.notna(row[col_ro_code]) else "",
                        "ro_name": str(row[col_ro_name]).strip() if col_ro_name and pd.notna(row[col_ro_name]) else "",
                        "sales_area": str(row[col_area]).strip() if col_area and pd.notna(row[col_area]) else "",
                        "bill_no": str(row[col_bill]).strip() if col_bill and pd.notna(row[col_bill]) else "",
                        "prize": str(row[col_prize]).strip() if col_prize and pd.notna(row[col_prize]) else default_prize
                    })
                if parsed:
                    records = parsed
            except Exception:
                records = None

        if not records:
            records = EMBEDDED_19_PLUS_1

        res_df = pd.DataFrame(records)
        grand_df = res_df[res_df["rank"] == 1]
        if grand_df.empty:
            grand_winner = res_df.iloc[0].to_dict()
            runners_up = res_df.iloc[1:20].sort_values(by="rank", ascending=False).to_dict("records")
        else:
            grand_winner = grand_df.iloc[0].to_dict()
            runners_up = (
                res_df[res_df["rank"] != 1]
                .sort_values(by="rank", ascending=False)
                .head(19)
                .to_dict("records")
            )
        return res_df, runners_up, grand_winner

    if "admin_reveal_list_done" not in st.session_state:
        st.session_state.admin_reveal_list_done = False
    if "admin_reveal_iphone_done" not in st.session_state:
        st.session_state.admin_reveal_iphone_done = False

    df_all_winners, runners_up_list, grand_iphone_winner = load_admin_winners()

    # Main Page Title
    st.title("Executive Dashboard — Mega Lucky Draw Winners")
    st.caption("Kolkata Divisional Office • 19 Smartphone Winners + 1 Grand iPhone Winner")
    st.divider()

    # Top Section: Sales_Area Graph (Left) + Grand Prize Card (Right)
    col_chart, col_right = st.columns([1.8, 1.1], gap="medium")

    with col_chart:
        area_counts = (
            df_all_winners.groupby("sales_area")
            .size()
            .reset_index(name="winners")
            .sort_values(by=["winners", "sales_area"], ascending=[False, True])
        )
        max_w = max(int(area_counts["winners"].max()), 1)

        short_labels = {
            "Kolkata South RSA": "Kol South",
            "Kolkata-North RSA": "Kol North",
            "Garia RSA": "Garia",
            "Kolkata New Town RSA": "New Town",
            "Barasat RSA": "Barasat",
            "Kalyani RSA": "Kalyani",
            "Krishnanagar RSA": "Krishnanagar",
            "24 Parganas(S) RSA": "24 Pgs (S)",
        }

        bars_html = ""
        for _, r in area_counts.iterrows():
            area_full = r["sales_area"]
            cnt = int(r["winners"])
            pct_h = int(round((cnt / max_w) * 140))
            lbl = short_labels.get(area_full, area_full.replace(" RSA", ""))
            bars_html += f"""
            <div class="bar-col-wrap" title="{area_full}: {cnt} Winners">
                <div class="bar-val-tag">{cnt}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="height: {pct_h}px;"></div>
                </div>
                <div class="bar-lbl">{lbl}</div>
            </div>
            """

        st.markdown(
            f"""
            <div class="brand-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div class="brand-card-title">Winners by Sales Area</div>
                    <span class="brand-badge">20 Winners Across 8 RSAs</span>
                </div>
                <div class="bar-chart-grid">
                    {bars_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col_right:
        if not st.session_state.admin_reveal_iphone_done:
            grand_status_txt = "Ready to Reveal" if st.session_state.admin_reveal_list_done else "Locked (Reveal #20-#2 First)"
            st.markdown(
                f"""
                <div class="brand-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div class="brand-card-title">1st Prize Grand Winner</div>
                        <span class="brand-badge">Rank #1</span>
                    </div>
                    <div style="font-size: 24px; font-weight: 800; color: #f37022; margin: 6px 0 10px 0;">
                        Apple iPhone 17 Pro Max
                    </div>
                    <div style="font-size: 13px; color: #475569; line-height: 1.5;">
                        Grand draw first prize winner across all verified campaign entries.
                    </div>
                    <div class="spotlight-box">
                        <div style="font-size: 11px; color: #64748b; font-weight: 600;">CURRENT STATUS</div>
                        <div style="font-size: 13px; font-weight: 700; color: #1e293b; margin-top: 2px;">
                            {grand_status_txt}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            gw = grand_iphone_winner
            st.markdown(
                f"""
                <div class="brand-card" style="background: #fffdf9; border-color: #f37022;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div class="brand-card-title" style="color: #f37022;">1st Prize Grand Winner</div>
                        <span class="brand-badge">Rank #1 Declared</span>
                    </div>
                    <div style="font-size: 24px; font-weight: 800; color: #1e293b; margin: 4px 0 4px 0;">
                        {gw['name']}
                    </div>
                    <div style="font-size: 13px; font-weight: 700; color: #f37022; margin-bottom: 8px;">
                        Apple iPhone 17 Pro Max
                    </div>
                    <div class="spotlight-box">
                        <div style="font-size: 12px; color: #1e293b; font-weight: 600;">
                            Mobile: {gw['phone']} | Bill: {gw['bill_no']}
                        </div>
                        <div style="font-size: 12px; color: #475569; margin-top: 4px;">
                            Outlet: {gw['ro_name']} ({gw['ro_code']})
                        </div>
                        <div style="font-size: 12px; color: #475569; margin-top: 2px;">
                            Sales Area: {gw['sales_area']}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.write("")

    # Bottom Section: Winners List (20th to 1st) + Reveal Buttons
    st.markdown(
        """
        <div class="brand-card" style="height: auto;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div class="brand-card-title">Winners List (Position #20 to #1)</div>
                <span class="brand-badge">Descending Sequence: #20 to #1</span>
            </div>
        """,
        unsafe_allow_html=True
    )

    if not st.session_state.admin_reveal_list_done:
        st.markdown(
            """
            <div style="background: #fffdf9; border: 1px dashed #f37022; border-radius: 8px; padding: 28px 20px; text-align: center; margin: 10px 0 18px 0;">
                <div style="font-size: 16px; font-weight: 700; color: #1e293b; margin-bottom: 6px;">
                    Ready to Reveal Winners (20th to 2nd Position)
                </div>
                <div style="font-size: 13px; color: #64748b; margin-bottom: 16px;">
                    Click below to display the 19 winners from Position #20 down to Position #2, followed by the 1st Prize iPhone winner.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        b_c1, b_c2, b_c3 = st.columns([1.2, 2, 1.2])
        with b_c2:
            if st.button("Reveal 20th to 2nd Position Winners", use_container_width=True, key="btn_admin_reveal_20_to_2"):
                prog = st.progress(0, text="Loading verified winners from 19+1.xlsx...")
                for pct in range(0, 101, 25):
                    time.sleep(0.11)
                    prog.progress(pct, text=f"Preparing winners list... {pct}%")
                prog.empty()
                st.session_state.admin_reveal_list_done = True
                st.rerun()
    else:
        f_col1, f_col2, f_col3 = st.columns([2.5, 1.5, 1.3])
        with f_col1:
            search_winner = st.text_input(
                "Search Winner",
                value="",
                placeholder="Search winner name, RO code, outlet, or bill...",
                label_visibility="collapsed",
                key="admin_winner_search"
            ).strip().lower()
        with f_col2:
            area_options = ["All Sales Areas"] + sorted(df_all_winners["sales_area"].unique().tolist())
            selected_area = st.selectbox(
                "Filter Sales Area",
                area_options,
                index=0,
                label_visibility="collapsed",
                key="admin_winner_area_filter"
            )
        with f_col3:
            if not st.session_state.admin_reveal_iphone_done:
                if st.button("Reveal 1st Prize (iPhone)", use_container_width=True, key="btn_admin_reveal_iphone_top"):
                    with st.spinner("Unlocking 1st Prize Grand Winner..."):
                        time.sleep(0.9)
                    st.session_state.admin_reveal_iphone_done = True
                    st.rerun()
            else:
                if st.button("Reset Reveal", use_container_width=True, key="btn_admin_reset_reveal"):
                    st.session_state.admin_reveal_list_done = False
                    st.session_state.admin_reveal_iphone_done = False
                    st.rerun()

        visible_winners = list(runners_up_list)  # Rank 20 down to 2
        if st.session_state.admin_reveal_iphone_done:
            visible_winners.append(grand_iphone_winner)  # Rank 1 at bottom

        filtered_winners = []
        for w in visible_winners:
            if selected_area != "All Sales Areas" and w["sales_area"] != selected_area:
                continue
            if search_winner:
                haystack = f"{w['rank']} {w['name']} {w['ro_code']} {w['ro_name']} {w['sales_area']} {w['bill_no']} {w['phone']}".lower()
                if search_winner not in haystack:
                    continue
            filtered_winners.append(w)

        rows_html = ""
        for idx, w in enumerate(filtered_winners):
            is_grand = (w["rank"] == 1)
            tr_cls = "grand-row" if is_grand else ""
            prize_label = w["prize"] if w.get("prize") else ("Apple iPhone 17 Pro Max" if is_grand else "vivo 5G Smartphone")

            rows_html += f"""
            <tr class="{tr_cls}" style="animation-delay: {round(idx * 0.025, 3)}s;">
                <td style="font-weight: 700; color: #f37022;">#{w['rank']}</td>
                <td style="font-weight: 700; color: #1e293b;">{w['name']}</td>
                <td style="color: #334155;">{w['ro_name']} <span style="color: #64748b;">({w['ro_code']})</span></td>
                <td style="color: #475569; font-weight: 600;">{w['sales_area']}</td>
                <td style="font-weight: 700; color: {'#f37022' if is_grand else '#1e293b'};">{prize_label}</td>
                <td style="color: #475569;">{w['phone']} | Bill: {w['bill_no']}</td>
            </tr>
            """

        if not rows_html:
            rows_html = """
            <tr>
                <td colspan="6" style="text-align: center; color: #64748b; padding: 20px;">
                    No winners match your current search or Sales Area filter.
                </td>
            </tr>
            """

        st.markdown(
            f"""
            <div class="brand-table-wrap">
                <table class="brand-table">
                    <thead>
                        <tr>
                            <th>Position</th>
                            <th>Winner Name</th>
                            <th>Retail Outlet</th>
                            <th>Sales Area</th>
                            <th>Prize</th>
                            <th>Mobile &amp; Bill No.</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
            """,
            unsafe_allow_html=True
        )

        if not st.session_state.admin_reveal_iphone_done:
            st.write("")
            g_c1, g_c2, g_c3 = st.columns([1.2, 2.2, 1.2])
            with g_c2:
                if st.button("Reveal Grand iPhone Winner (1st Prize)", use_container_width=True, key="btn_admin_reveal_iphone_bottom"):
                    with st.spinner("Unlocking Grand Prize Winner..."):
                        time.sleep(0.9)
                    st.session_state.admin_reveal_iphone_done = True
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()
# ----------------- LOGGED IN HEADER (DEV & RO UNCHANGED) -----------------
top_col1, top_col2 = st.columns([3, 1])
is_admin_or_dev = st.session_state.user_role in ["admin", "dev"]

if st.session_state.user_role == "dev":
    top_col1.title("🛠️ Developer Dashboard")
    top_col1.caption("System Diagnostics • Outlet Activation Control • Live Voucher Vault Tracking")
elif st.session_state.user_role == "admin":
    top_col1.title("⛽ Executive Dashboard")
    top_col1.caption("Divisional Office Master View • Cross-network monitoring & exports")
else:
    top_col1.title(f"⛽ RO Dashboard — {st.session_state.ro_name} ({st.session_state.ro_code})")

with top_col2:
    st.write(f"Logged in: **{st.session_state.ro_name}**")
    if st.button("🚪 Logout", use_container_width=True):
        logout()

if st.session_state.user_role == "ro":
    with st.expander("🔑 Change Outlet Password"):
        with st.form("change_password_form"):
            new_pass = st.text_input("New Password", type="password")
            confirm_pass = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Update Password"):
                if not new_pass or len(new_pass) < 4:
                    st.error("Password must be at least 4 characters long.")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match.")
                else:
                    db.table("retail_outlets").update({"password": new_pass}).eq("ro_code", st.session_state.ro_code).execute()
                    st.cache_data.clear()
                    st.success("Password updated successfully!")

st.divider()

# ----------------- DATA LOADER -----------------
@st.cache_data(ttl=15)
def load_data(role: str, ro_code: str = None):
    outlets_res = db.table("retail_outlets").select("ro_code, ro_name, district, is_active, check_5580").execute()
    
    all_entries = []
    page_size = 1000
    start = 0
    while True:
        query = db.table("campaign_entries").select("*").order("created_at", desc=True).range(start, start + page_size - 1)
        if role not in ["admin", "dev"] and ro_code:
            query = query.eq("ro_code", ro_code)
        
        batch = query.execute()
        if not batch.data:
            break
        all_entries.extend(batch.data)
        if len(batch.data) < page_size:
            break
        start += page_size

    all_vouchers = []
    v_start = 0
    v_page_size = 1000
    while True:
        v_query = db.table("voucher_vault").select("ro_code, denomination, status, claimed_by_phone").range(v_start, v_start + v_page_size - 1)
        if role not in ["admin", "dev"] and ro_code:
            v_query = v_query.eq("ro_code", ro_code)
        
        v_batch = v_query.execute()
        if not v_batch.data:
            break
        all_vouchers.extend(v_batch.data)
        if len(v_batch.data) < v_page_size:
            break
        v_start += v_page_size

    return all_entries, outlets_res.data, all_vouchers

entries, outlets, vouchers = load_data(st.session_state.user_role, st.session_state.ro_code)

df_entries = pd.DataFrame(entries) if entries else pd.DataFrame()
df_outlets = pd.DataFrame(outlets) if outlets else pd.DataFrame()
df_vouchers = pd.DataFrame(vouchers) if vouchers else pd.DataFrame()
if not df_vouchers.empty:
    df_vouchers["denomination"] = pd.to_numeric(df_vouchers["denomination"], errors="coerce").fillna(0)
    df_vouchers["status_clean"] = df_vouchers["status"].astype(str).str.strip().str.title()

if not df_entries.empty:
    df_entries["amount"] = pd.to_numeric(df_entries["amount"], errors="coerce").fillna(0.0)
    df_entries["created_at"] = pd.to_datetime(df_entries["created_at"], errors="coerce", utc=True).dt.tz_convert("Asia/Kolkata")
    df_entries["Date"] = df_entries["created_at"].dt.strftime("%d-%m-%Y")
    df_entries["Time"] = df_entries["created_at"].dt.strftime("%I:%M:%S %p")
    if not df_outlets.empty:
        df_entries = df_entries.merge(df_outlets[["ro_code", "ro_name", "district"]], on="ro_code", how="left")

# ----------------- DEVELOPER CONTROL PANEL -----------------
if st.session_state.user_role == "dev":
    with st.expander("⚙️ Developer Controls: RO Activation & Live Voucher Vault", expanded=True):
        dev_tab1, dev_tab2, dev_tab3 = st.tabs([
            "🚦 Turn ROs Active / Inactive", 
            "🎟️ Live Voucher Vault Inventory",
            "📨 Manual MIS Dispatcher"
        ])

        with dev_tab1:
            st.markdown("##### Outlet Campaign Status")
            st.caption("Toggle the checkbox to activate/deactivate an outlet.")
            if not df_outlets.empty:
                ro_display = df_outlets[["ro_code", "ro_name", "district", "check_5580", "is_active"]].copy()
                ro_display["check_5580"] = pd.to_numeric(ro_display["check_5580"], errors="coerce").fillna(0).astype(int)
                ro_display["is_active"] = ro_display["is_active"].fillna(True).astype(bool)

                edited_ro = st.data_editor(
                    ro_display,
                    column_config={
                        "ro_code": st.column_config.TextColumn("RO Code", disabled=True),
                        "ro_name": st.column_config.TextColumn("RO Name", disabled=True),
                        "district": st.column_config.TextColumn("District", disabled=True),
                        "check_5580": st.column_config.NumberColumn(
                            "Total Sum", 
                            help="Cumulative disbursed amount tracked against ₹5,580",
                            format="₹%d",
                            disabled=True
                        ),
                        "is_active": st.column_config.CheckboxColumn("Active in Campaign?", default=True)
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="ro_activation_editor"
                )

                if st.button("💾 Save RO Activation Changes", type="primary"):
                    try:
                        for _, row in edited_ro.iterrows():
                            db.table("retail_outlets").update({"is_active": bool(row["is_active"])}).eq("ro_code", row["ro_code"]).execute()
                        st.cache_data.clear()
                        st.success("Outlet statuses updated successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Update failed: {e}")

        with dev_tab2:
            st.markdown("##### Detailed Voucher Vault Breakdown (3-Stage Tracking)")
            if not df_vouchers.empty:
                v_avail = df_vouchers[df_vouchers["status"] == "Available"]
                v_won = df_vouchers[df_vouchers["status"] == "Won"]
                v_claimed = df_vouchers[df_vouchers["status"] == "Claimed"]

                vc1, vc2, vc3, vc4 = st.columns(4)
                vc1.metric("Total Vouchers Seeded", len(df_vouchers))
                vc2.metric("Available Pool", len(v_avail))
                vc3.metric("Won (Unclaimed)", len(v_won))
                vc4.metric("Claimed / Delivered", len(v_claimed))

                st.markdown("###### By Denomination")
                denom_summary = df_vouchers.groupby("denomination").agg(
                    Total=("status", "count"),
                    Available=("status", lambda x: (x == "Available").sum()),
                    Won=("status", lambda x: (x == "Won").sum()),
                    Claimed=("status", lambda x: (x == "Claimed").sum())
                ).reset_index()
                st.dataframe(denom_summary, use_container_width=True, hide_index=True)

                st.markdown("###### Customers Who Won but Haven't Claimed (For Manual Outreach)")
                unclaimed_winners = df_vouchers[df_vouchers["status"] == "Won"][["ro_code", "denomination", "claimed_by_phone"]].dropna()
                st.dataframe(unclaimed_winners, use_container_width=True, hide_index=True)

        with dev_tab3:
            st.markdown("##### 📨 Manual Campaign MIS Report Dispatcher")
            st.caption("Sends records from **Day Before 5:30 PM IST** to **Selected Date 5:30 PM IST**.")

            from datetime import date
            from daily_report_runner import send_campaign_report

            col_d1, col_d2 = st.columns([1, 2])
            with col_d1:
                manual_date = st.date_input(
                    "Select Date *",
                    value=date.today(),
                    key="dev_manual_report_date"
                )
            with col_d2:
                manual_recipient = st.text_input(
                    "Recipient Email Address *",
                    value="mehedihassan@indianoil.in",
                    placeholder="Enter email address (comma-separated for multiple)",
                    key="dev_manual_report_email"
                ).strip()

            if st.button("🚀 Send Daily MIS Report", type="primary", use_container_width=True, key="btn_send_dev_manual_report"):
                if not manual_recipient:
                    st.error("Please enter a valid recipient email address.")
                else:
                    with st.spinner(f"Compiling MIS report for {manual_date} and dispatching..."):
                        ok, msg = send_campaign_report(
                            selected_date=manual_date,
                            recipient_email=manual_recipient,
                            report_type="Daily"
                        )
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

    st.divider()

# ----------------- SIDEBAR CONTROLS & FILTERS -----------------
with st.sidebar:
    sb_c1, sb_c2, sb_c3 = st.columns([1, 2, 1])
    with sb_c2:
        if os.path.exists(LOCAL_LOGO_PATH):
            st.image(LOCAL_LOGO_PATH, use_container_width=True)
        else:
            st.image(PROD_FALLBACK_URL, use_container_width=True)
    st.markdown("<h4 style='text-align: center; margin-top: -25px;'>IndianOil</h4>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray; margin-bottom: 20px;'>Retail Campaign Management Portal</p>", unsafe_allow_html=True)

st.sidebar.header("🔍 Filters & Controls")

selected_dates = st.sidebar.date_input(
    "📅 Select Date or Date Range",
    value=(),
    help="Pick a single date, or select two dates to filter by a range. Leave blank to show All-Time data."
)

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

filtered_df = df_entries.copy()

if not filtered_df.empty and selected_dates:
    entry_dates = filtered_df["created_at"].dt.date
    if isinstance(selected_dates, tuple) or isinstance(selected_dates, list):
        if len(selected_dates) == 1:
            filtered_df = filtered_df[entry_dates == selected_dates[0]]
        elif len(selected_dates) == 2:
            start_date, end_date = selected_dates
            filtered_df = filtered_df[(entry_dates >= start_date) & (entry_dates <= end_date)]
    else:
        filtered_df = filtered_df[entry_dates == selected_dates]

search_query = st.sidebar.text_input("🔎 Search Bill / Customer / Phone", placeholder="Type keyword...").strip()

if not filtered_df.empty:
    if search_query:
        mask = (
            filtered_df["customer_name"].astype(str).str.contains(search_query, case=False, na=False) |
            filtered_df["phone_number"].astype(str).str.contains(search_query, case=False, na=False) |
            filtered_df["bill_number"].astype(str).str.contains(search_query, case=False, na=False)
        )
        filtered_df = filtered_df[mask]

    if is_admin_or_dev:
        if "district" in filtered_df.columns:
            districts = ["All Districts"] + sorted([str(d) for d in filtered_df["district"].dropna().unique().tolist()])
            selected_dist = st.sidebar.selectbox("Filter District", districts, index=0)
            if selected_dist != "All Districts":
                filtered_df = filtered_df[filtered_df["district"] == selected_dist]

        outlet_pairs = filtered_df[["ro_code", "ro_name"]].drop_duplicates().dropna()
        outlets_list = ["All Retail Outlets"] + sorted([f"{r.ro_code} - {r.ro_name}" for _, r in outlet_pairs.iterrows()])
        selected_ro = st.sidebar.selectbox("Filter Retail Outlet", outlets_list, index=0)
        if selected_ro != "All Retail Outlets":
            ro_code_val = selected_ro.split(" - ")[0]
            filtered_df = filtered_df[filtered_df["ro_code"] == ro_code_val]

    outcomes = ["All Outcomes"] + sorted([str(o) for o in filtered_df["outcome"].dropna().unique().tolist()])
    selected_outcome = st.sidebar.selectbox("Filter Outcome", outcomes, index=0)
    if selected_outcome != "All Outcomes":
        filtered_df = filtered_df[filtered_df["outcome"] == selected_outcome]

    fuel_grades = ["All Fuel Grades"] + sorted([str(f) for f in filtered_df["fuel_grade"].dropna().unique().tolist()])
    selected_fuel = st.sidebar.selectbox("Filter Fuel Grade", fuel_grades, index=0)
    if selected_fuel != "All Fuel Grades":
        filtered_df = filtered_df[filtered_df["fuel_grade"] == selected_fuel]

# ----------------- 1. KPI SUMMARY CARDS -----------------
col1, col2, col3, col4 = st.columns(4)

total_scans = len(filtered_df)
won_vouchers = len(df_vouchers[df_vouchers["status"].isin(["Won", "Claimed"])]) if not df_vouchers.empty else 0
total_sales_value = filtered_df["amount"].sum() if not filtered_df.empty else 0.0

col1.metric("Scans Recorded", f"{total_scans:,}")
col2.metric("Vouchers Won/Issued", f"{won_vouchers:,}")
col3.metric("Fuel Sales Recorded", f"₹{total_sales_value:,.2f}")

if is_admin_or_dev:
    active_outlets = filtered_df["ro_code"].nunique() if not filtered_df.empty else 0
    col4.metric("Active Outlets", f"{active_outlets} / 112")
else:
    available_vouchers = len(df_vouchers[df_vouchers["status"] == "Available"]) if not df_vouchers.empty else 0
    col4.metric("Vouchers Remaining", f"{available_vouchers}")

st.divider()

# ----------------- EMAIL DISPATCH SECTION (DEV ONLY) -----------------
if st.session_state.user_role == "dev":
    st.subheader("📧 Developer MIS Dispatcher")
    c_mail1, c_mail2 = st.columns([3, 1])

    with c_mail1:
        target_email = st.text_input(
            "Send Report To Any Email",
            value="",
            placeholder="e.g. client@example.com, official@indianoil.in",
            key="dev_custom_email_input"
        )

    with c_mail2:
        st.write("")
        st.write("")
        send_btn = st.button("🚀 Send MIS Report", use_container_width=True, key="dev_send_mis_btn")

    if send_btn:
        if not target_email or "@" not in target_email:
            st.error("Please enter a valid email address.")
        else:
            with st.spinner(f"Generating Excel report and sending to {target_email}..."):
                try:
                    send_custom_report(target_email.strip())
                    st.success(f"✅ Report successfully dispatched to {target_email}!")
                except Exception as e:
                    st.error(f"❌ Failed to send email: {e}")

    st.divider()

# ----------------- 2. LEADERBOARD & FUEL BREAKDOWN -----------------
left_col, right_col = st.columns([1, 1])

with left_col:
    st.subheader("🏆 Performance Summary")
    if not filtered_df.empty:
        if is_admin_or_dev:
            if "ro_name" not in filtered_df.columns:
                filtered_df["ro_name"] = filtered_df["ro_code"]

            outlet_agg = filtered_df.groupby(["ro_code", "ro_name"]).agg(
                Scans=("bill_number", "count"),
                Total_Sales=("amount", "sum"),
                Avg_Bill=("amount", "mean"),
                Winners=("outcome", lambda x: (x.astype(str).str.lower() == "won").sum())
            ).reset_index().sort_values(by="Scans", ascending=False)
            st.dataframe(outlet_agg, use_container_width=True, hide_index=True)
        else:
            outlet_summary = filtered_df.groupby("fuel_grade").agg(
                Transactions=("bill_number", "count"),
                Total_Revenue=("amount", "sum"),
                Average_Bill=("amount", "mean")
            ).reset_index()
            st.dataframe(outlet_summary, use_container_width=True, hide_index=True)
    else:
        st.info("No matching performance data.")

with right_col:
    st.subheader("⛽ Fuel Grade Breakdown")
    if not filtered_df.empty and "fuel_grade" in filtered_df.columns:
        fuel_agg = filtered_df.groupby("fuel_grade").agg(
            Count=("bill_number", "count"),
            Total_Value=("amount", "sum")
        ).reset_index().sort_values(by="Count", ascending=False)
        st.dataframe(fuel_agg, use_container_width=True, hide_index=True)
    else:
        st.info("No fuel transaction records available.")

    if st.session_state.user_role == "dev":
        st.write("")
        if not df_vouchers.empty:
            disbursed_df = df_vouchers[df_vouchers["status_clean"].isin(["Claimed", "Allocated", "Won"])]
            total_disbursed_amt = disbursed_df["denomination"].sum()
            total_disbursed_count = len(disbursed_df)
            
            claimed_df = df_vouchers[df_vouchers["status_clean"] == "Claimed"]
            allocated_df = df_vouchers[df_vouchers["status_clean"].isin(["Allocated", "Won"])]
            
            claimed_amt = claimed_df["denomination"].sum()
            allocated_amt = allocated_df["denomination"].sum()

            st.markdown("##### 💰 Voucher Value Disbursed (Allocated + Claimed)")
            kpi_c1, kpi_c2 = st.columns(2)
            kpi_c1.metric(
                label="Total Value Disbursed",
                value=f"₹{total_disbursed_amt:,.0f}",
                help=f"Claimed: ₹{claimed_amt:,.0f} | Allocated: ₹{allocated_amt:,.0f}"
            )
            kpi_c2.metric(
                label="Total Count",
                value=f"{total_disbursed_count:,} Vouchers",
                help=f"Claimed: {len(claimed_df)} | Allocated: {len(allocated_df)}"
            )
        else:
            st.metric("Total Value Disbursed", "₹0")

st.divider()

# ----------------- 3. TRANSACTION AUDIT FEED -----------------
st.subheader("📋 Transaction Audit Feed")

if not filtered_df.empty:
    ctrl_col1, ctrl_col2 = st.columns([3, 1])

    audit_sort_options = {
        "Timestamp (Newest First)": ("created_at", False),
        "Timestamp (Oldest First)": ("created_at", True),
        "Amount (Highest First)": ("amount", False),
        "Customer Name (A to Z)": ("customer_name", True)
    }

    chosen_sort = ctrl_col1.selectbox("Sort Transactions", list(audit_sort_options.keys()), index=0)
    if st.session_state.user_role == "dev":
        limit_options = ["25 Rows", "50 Rows", "100 Rows", "All Rows"]
    else:
        limit_options = ["25 Rows", "50 Rows", "100 Rows"]

    chosen_limit = ctrl_col2.selectbox("Display Limit", limit_options, index=0)

    sort_col, is_asc = audit_sort_options[chosen_sort]
    sorted_feed = filtered_df.sort_values(by=sort_col, ascending=is_asc)

    if st.session_state.user_role == "admin":
        display_cols = [
            "Date", "Time", "ro_code", "ro_name", 
            "customer_name", "phone_number", "bill_number", 
            "fuel_grade", "amount"
        ]
    else:
        display_cols = [
            "Date", "Time", "ro_code", "ro_name", 
            "customer_name", "phone_number", "bill_number", 
            "fuel_grade", "amount", "outcome", "claim_link"
        ]

    available_cols = [c for c in display_cols if c in sorted_feed.columns]

    num_rows = len(sorted_feed) if chosen_limit == "All Rows" else int(chosen_limit.replace(" Rows", ""))
    st.dataframe(sorted_feed.head(num_rows)[available_cols], use_container_width=True, hide_index=True)

    dl_c1, dl_c2 = st.columns(2)
    export_feed = sorted_feed[available_cols].copy()
    dl_c1.download_button(
        "📥 Download Audit (CSV)",
        data=export_feed.to_csv(index=False).encode("utf-8"),
        file_name=f"iocl_transactions_{st.session_state.ro_code or 'admin'}.csv",
        mime="text/csv",
        use_container_width=True
    )
    dl_c2.download_button(
        "📊 Download Audit (Excel)",
        data=to_excel_bytes(export_feed),
        file_name=f"iocl_transactions_{st.session_state.ro_code or 'admin'}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
else:
    st.info("No transaction entries found.")