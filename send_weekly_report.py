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