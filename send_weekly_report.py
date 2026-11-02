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

# Helper to fetch from GitHub Actions environment first, fallback to Streamlit secrets
def get_config(key: str, default: str = ""):
    val = os.environ.get(key)
    if not val:
        try:
            import streamlit as st
            val = st.secrets.get(key, default)
        except Exception:
            val = default
    return val

SUPABASE_URL = get_config("SUPABASE_URL")
SUPABASE_KEY = get_config("SUPABASE_KEY")
SENDER_EMAIL = get_config("SMTP_SENDER_EMAIL")
SENDER_PASSWORD = get_config("SMTP_SENDER_PASSWORD")
SIR_REPORT_EMAIL = get_config("SIR_REPORT_EMAIL", "alifaiz9111@gmail.com")

RECIPIENT_EMAILS = [
    SIR_REPORT_EMAIL,
    "mehedihassan@indianoil.in",
    "adnetadvertising@gmail.com"
]

db = create_client(SUPABASE_URL, SUPABASE_KEY)


def send_weekly_report():
    # 7-day window anchored to 5:30 PM IST (From 7 days ago 5:30 PM IST to Today 5:30 PM IST)
    now_ist = datetime.now(IST)
    end_dt_ist = now_ist.replace(hour=17, minute=30, second=0, microsecond=0)
    start_dt_ist = end_dt_ist - timedelta(days=7)

    # Convert to UTC ISO format for Supabase queries
    start_utc_iso = start_dt_ist.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%S")
    end_utc_iso = end_dt_ist.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%S")

    start_str_display = start_dt_ist.strftime("%d-%b-%Y %I:%M %p")
    end_str_display = end_dt_ist.strftime("%d-%b-%Y %I:%M %p")
    date_display_str = end_dt_ist.strftime("%d-%b-%Y")

    print(f"📊 Pulling weekly records from {start_str_display} to {end_str_display} (IST)...")

    # Fetch records from Supabase
    entries_res = (
        db.table("campaign_entries")
        .select("*")
        .gte("created_at", start_utc_iso)
        .lte("created_at", end_utc_iso)
        .execute()
    )
    outlets_res = (
        db.table("retail_outlets")
        .select("ro_code, ro_name, district, sales_area")
        .execute()
    )
    vouchers_res = (
        db.table("voucher_vault")
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
        df_e["Scan_Time"] = df_e["created_at_ist"].dt.strftime("%I:%M:%S