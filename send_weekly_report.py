import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import io
import pandas as pd
from supabase import create_client

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

def fetch_all_vouchers():
    """Fetches all vouchers across all pages beyond Supabase's 1000 limit."""
    all_vouchers = []
    page_size = 1000
    start = 0
    while True:
        res = db.table("voucher_vault").select("ro_code, denomination, status").range(start, start + page_size - 1).execute()
        data = res.data or []
        all_vouchers.extend(data)
        if len(data) < page_size:
            break
        start += page_size
    return all_vouchers