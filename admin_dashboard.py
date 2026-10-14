import io
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import streamlit as st
from supabase import create_client, Client
import pandas as pd

st.set_page_config(page_title="IOCL Portal", page_icon="⛽", layout="wide")

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
            Vouchers_Won=("voucher_code", lambda x: x.notnull().sum()),
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

        st.markdown("<h4 style='text-align: center; margin-top: -10px;'>Indian Oil</h4>", unsafe_allow_html=True)
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

# ----------------- LOGGED IN HEADER -----------------
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
    outlets_res = db.table("retail_outlets").select("ro_code, ro_name, district, is_active").execute()
    if role in ["admin", "dev"]:
        entries_res = db.table("campaign_entries").select("*").order("created_at", desc=True).limit(5000).execute()
        vouchers_res = db.table("voucher_vault").select("ro_code, denomination, status, claimed_by_phone").execute()
    else:
        entries_res = db.table("campaign_entries").select("*").eq("ro_code", ro_code).order("created_at", desc=True).execute()
        vouchers_res = db.table("voucher_vault").select("ro_code, denomination, status, claimed_by_phone").eq("ro_code", ro_code).execute()

    return entries_res.data, outlets_res.data, vouchers_res.data

entries, outlets, vouchers = load_data(st.session_state.user_role, st.session_state.ro_code)

df_entries = pd.DataFrame(entries) if entries else pd.DataFrame()
df_outlets = pd.DataFrame(outlets) if outlets else pd.DataFrame()
df_vouchers = pd.DataFrame(vouchers) if vouchers else pd.DataFrame()

if not df_entries.empty:
    df_entries["amount"] = pd.to_numeric(df_entries["amount"], errors="coerce").fillna(0.0)
    df_entries["created_at"] = pd.to_datetime(df_entries["created_at"], errors="coerce")
    df_entries["Date"] = df_entries["created_at"].dt.strftime("%d-%m-%Y")
    df_entries["Time"] = df_entries["created_at"].dt.strftime("%I:%M:%S %p")
    if not df_outlets.empty:
        df_entries = df_entries.merge(df_outlets[["ro_code", "ro_name", "district"]], on="ro_code", how="left")

# ----------------- DEVELOPER CONTROL PANEL -----------------
if st.session_state.user_role == "dev":
    with st.expander("⚙️ Developer Controls: RO Activation & Live Voucher Vault", expanded=True):
        dev_tab1, dev_tab2 = st.tabs(["🚦 Turn ROs Active / Inactive", "🎟️ Live Voucher Vault Inventory"])

        with dev_tab1:
            st.markdown("##### Outlet Campaign Status")
            st.caption("Toggle the checkbox to activate/deactivate an outlet.")
            if not df_outlets.empty:
                ro_display = df_outlets[["ro_code", "ro_name", "district", "is_active"]].copy()
                ro_display["is_active"] = ro_display["is_active"].fillna(True).astype(bool)

                edited_ro = st.data_editor(
                    ro_display,
                    column_config={
                        "ro_code": st.column_config.TextColumn("RO Code", disabled=True),
                        "ro_name": st.column_config.TextColumn("RO Name", disabled=True),
                        "district": st.column_config.TextColumn("District", disabled=True),
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
if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

filtered_df = df_entries.copy()
search_query = st.sidebar.text_input("🔎 Search Bill / Customer / Phone", placeholder="Type keyword...").strip()

if not filtered_df.empty:
    if search_query:
        mask = (
            filtered_df["customer_name"].astype(str).str.contains(search_query, case=False, na=False) |
            filtered_df["phone_number"].astype(str).str.contains(search_query, case=False, na=False) |
            filtered_df["bill_number"].astype(str).str.contains(search_query, case=False, na=False) |
            filtered_df["voucher_code"].astype(str).str.contains(search_query, case=False, na=False)
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

# ----------------- EMAIL DISPATCH SECTION (ADMIN / DEV ONLY) -----------------
if is_admin_or_dev:
    with st.expander("📧 Email Weekly MIS Report to Officials / Clients", expanded=False):
        c_mail1, c_mail2 = st.columns([3, 1])
        with c_mail1:
            target_email = st.text_input(
                "Recipient Email Address",
                value=st.secrets.get("SIR_REPORT_EMAIL", "alifaiz9111@gmail.com"),
                placeholder="Enter email to receive the report"
            )
        with c_mail2:
            st.write("")
            st.write("")
            send_btn = st.button("🚀 Send Report Now", use_container_width=True)

        if send_btn:
            if not target_email or "@" not in target_email:
                st.error("Please enter a valid email address.")
            else:
                with st.spinner(f"Generating spreadsheet and sending to {target_email}..."):
                    try:
                        send_custom_report(target_email.strip())
                        st.success(f"✅ Weekly MIS report successfully emailed to {target_email}!")
                    except Exception as e:
                        st.error(f"❌ Failed to dispatch email: {e}")

    st.divider()

# ----------------- 2. LEADERBOARD & FUEL BREAKDOWN -----------------
left_col, right_col = st.columns([1, 1])

with left_col:
    st.subheader("🏆 Performance Summary")
    if not filtered_df.empty:
        if is_admin_or_dev:
            outlet_agg = filtered_df.groupby(["ro_code", "ro_name"]).agg(
                Scans=("bill_number", "count"),
                Total_Sales=("amount", "sum"),
                Avg_Bill=("amount", "mean"),
                Winners=("voucher_code", lambda x: x.notnull().sum())
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
    chosen_limit = ctrl_col2.selectbox("Display Limit", ["25 Rows", "50 Rows", "100 Rows", "All Rows"], index=0)

    sort_col, is_asc = audit_sort_options[chosen_sort]
    sorted_feed = filtered_df.sort_values(by=sort_col, ascending=is_asc)

    display_cols = [
        "Date", "Time", "ro_code", "ro_name", 
        "customer_name", "phone_number", "bill_number", 
        "fuel_grade", "amount", "outcome", "voucher_code"
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