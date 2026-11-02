import os
import io
import smtplib
from datetime import datetime, timedelta
import pytz
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import pandas as pd
from supabase import create_client

IST = pytz.timezone("Asia/Kolkata")

# Helper to fetch from environment variables first, fallback to Streamlit secrets
def get_config(key: str, default: str = ""):
    val = os.environ.get(key)
    if not val:
        try:
            import streamlit as st
            val = st.secrets.get(key, default)
        except Exception:
            val = default
    return val

SUPABASE_URL = get_config("SUPABASE_URL", "https://atpvqeibzuzhhuowzbtk.supabase.co")
SUPABASE_KEY = get_config(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF0cHZxZWlienV6aGh1b3d6YnRrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEzNjc4NjEsImV4cCI6MjEwNjk0Mzg2MX0.yrw0p1S7moCcUoEMdvDSnmhlWPP076CNF57_QqeEIos"
)
SMTP_SENDER_EMAIL = get_config("SMTP_SENDER_EMAIL", "alifaiz.adnetprint@gmail.com")
SMTP_SENDER_PASSWORD = get_config("SMTP_SENDER_PASSWORD", "wncganghkujowixi")
SIR_REPORT_EMAIL = get_config("SIR_REPORT_EMAIL", "mehedihassan@indianoil.in")

RECIPIENT_EMAILS = [
    SIR_REPORT_EMAIL,
    "alifaiz9111@gmail.com",
    "adnetadvertising@gmail.com"
]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def run_daily_report():
    # Anchor cutoff period: Yesterday 5:30 PM IST to Today 5:30 PM IST
    now_ist = datetime.now(IST)
    end_dt_ist = now_ist.replace(hour=17, minute=30, second=0, microsecond=0)
    start_dt_ist = end_dt_ist - timedelta(days=1)

    # Convert to UTC ISO format for Supabase querying
    start_utc_iso = start_dt_ist.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%S")
    end_utc_iso = end_dt_ist.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%S")

    start_str_display = start_dt_ist.strftime("%d-%b-%Y %I:%M %p")
    end_str_display = end_dt_ist.strftime("%d-%b-%Y %I:%M %p")
    date_str = end_dt_ist.strftime("%d-%b-%Y")

    print(f"📊 Pulling records from {start_str_display} to {end_str_display} (IST)...")

    # Fetch data from Supabase
    entries_res = (
        supabase.table("campaign_entries")
        .select("*")
        .gte("created_at", start_utc_iso)
        .lte("created_at", end_utc_iso)
        .execute()
    )
    outlets_res = (
        supabase.table("retail_outlets")
        .select("ro_code, ro_name, district, sales_area")
        .execute()
    )
    vouchers_res = (
        supabase.table("voucher_vault")
        .select("ro_code, denomination, status")
        .execute()
    )

    df_e = pd.DataFrame(entries_res.data or [])
    df_o = pd.DataFrame(outlets_res.data or [])
    df_v = pd.DataFrame(vouchers_res.data or [])

    # Process and aggregate data
    if not df_e.empty and not df_o.empty:
        df_e["ro_code"] = df_e["ro_code"].astype(str)
        df_o["ro_code"] = df_o["ro_code"].astype(str)
        df_e = df_e.merge(df_o, on="ro_code", how="left")

        df_e["created_at_ist"] = (
            pd.to_datetime(df_e["created_at"], errors="coerce", utc=True)
            .dt.tz_convert("Asia/Kolkata")
        )
        df_e["Scan_Date"] = df_e["created_at_ist"].dt.strftime("%d-%m-%Y")
        df_e["Scan_Time"] = df_e["created_at_ist"].dt.strftime("%I:%M:%S %p")

        ro_summary = (
            df_e.groupby(["ro_code", "ro_name", "district"])
            .agg(
                Total_Scans=("bill_number", "count"),
                Total_Sales_Value=("amount", "sum"),
                Winners=("outcome", lambda x: (x.astype(str).str.lower() == "won").sum()),
                Unique_Customers=("phone_number", "nunique"),
            )
            .reset_index()
            .sort_values(by="Total_Scans", ascending=False)
        )
    else:
        ro_summary = pd.DataFrame({"Status": [f"No scans recorded between {start_str_display} and {end_str_display}"]})

    vault_summary = (
        df_v.groupby(["denomination", "status"]).size().unstack(fill_value=0)
        if not df_v.empty
        else pd.DataFrame()
    )

    # Generate Excel in memory
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        ro_summary.to_excel(writer, sheet_name="Daily_Summary", index=False)
        vault_summary.to_excel(writer, sheet_name="Vault_Inventory")
        if not df_e.empty:
            audit_cols = [
                c for c in [
                    "Scan_Date",
                    "Scan_Time",
                    "ro_code",
                    "ro_name",
                    "district",
                    "customer_name",
                    "phone_number",
                    "bill_number",
                    "fuel_grade",
                    "amount",
                    "outcome",
                ] if c in df_e.columns
            ]
            df_e[audit_cols].to_excel(writer, sheet_name="Audit_Transactions", index=False)

    buffer.seek(0)
    scan_count = len(df_e)
    total_sales = float(df_e["amount"].sum()) if not df_e.empty and "amount" in df_e.columns else 0.0

    # Compose Email
    msg = MIMEMultipart()
    msg["From"] = SMTP_SENDER_EMAIL
    msg["To"] = ", ".join(RECIPIENT_EMAILS)
    msg["Subject"] = f"IOCL Kolkata DO - Daily Campaign MIS Report ({date_str})"

    body = f"""Dear Sir,

Please find attached the official Daily Campaign MIS Report for the QR Sales Promotion Campaign (MS/XP95/XP100) under Kolkata Divisional Office.

Reporting Window:
- From: {start_str_display} IST
- To:   {end_str_display} IST

Period Summary:
- Total Customer Scans: {scan_count:,}
- Total Fuel Sales Value Recorded: ₹{total_sales:,.2f}

Detailed outlet-wise breakups, voucher inventory statuses, and complete transaction audits are included in the attached spreadsheet.

Warm regards,
Adnet Campaign Operations Team
"""
    msg.attach(MIMEText(body, "plain"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(buffer.getvalue())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f"attachment; filename=IOCL_Daily_MIS_{date_str}.xlsx",
    )
    msg.attach(part)

    print(f"🚀 Dispatching to {RECIPIENT_EMAILS}...")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SMTP_SENDER_EMAIL, SMTP_SENDER_PASSWORD)
        server.sendmail(SMTP_SENDER_EMAIL, RECIPIENT_EMAILS, msg.as_string())
    print("✅ Daily report dispatched successfully!")


if __name__ == "__main__":
    run_daily_report()