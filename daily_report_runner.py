import os
import io
import smtplib
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import pandas as pd
from supabase import create_client

IST = pytz.timezone("Asia/Kolkata")

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

DEFAULT_RECIPIENT_EMAILS = [
    SIR_REPORT_EMAIL,
    "alifaiz9111@gmail.com",
    "adnetadvertising@gmail.com"
]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def send_campaign_report(selected_date=None, recipient_email=None, report_type="Daily"):
    """
    Sends the MIS report for a window:
    (selected_date - 1 day at 5:30 PM IST) to (selected_date at 5:30 PM IST).
    """
    try:
        # Determine target date
        if selected_date is None:
            target_d = datetime.now(IST).date()
        elif isinstance(selected_date, str):
            target_d = datetime.strptime(selected_date, "%Y-%m-%d").date()
        else:
            target_d = selected_date

        # Window: Yesterday 5:30 PM IST to Selected Date 5:30 PM IST
        end_dt_ist = IST.localize(datetime.combine(target_d, datetime.min.time())).replace(hour=17, minute=30, second=0)
        start_dt_ist = end_dt_ist - timedelta(days=1)

        start_utc_iso = start_dt_ist.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        end_utc_iso = end_dt_ist.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        date_display_str = target_d.strftime("%d-%b-%Y")

        # Fetch records
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
            ro_summary = pd.DataFrame({"Status": [f"No scans recorded between {start_dt_ist.strftime('%d-%b-%Y %I:%M %p')} and {end_dt_ist.strftime('%d-%b-%Y %I:%M %p')} IST"]})

        vault_summary = (
            df_v.groupby(["denomination", "status"]).size().unstack(fill_value=0)
            if not df_v.empty
            else pd.DataFrame()
        )

        # Build Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            ro_summary.to_excel(writer, sheet_name=f"{report_type}_Summary", index=False)
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

        # Recipient parsing
        if recipient_email:
            targets = [e.strip() for e in recipient_email.split(",") if e.strip()]
        else:
            targets = DEFAULT_RECIPIENT_EMAILS

        # Email Subject & Body exactly per specification
        email_subject = f"IOCL Kolkata DO - {report_type} Campaign MIS Report ({date_display_str})"
        email_body = f"""Dear Sir,

Please find attached the {report_type} Campaign MIS Report for the QR Sales Promotion Campaign (MS/XP95/XP100) under Kolkata Divisional Office.


Detailed outlet-wise breakups and audit transactions are included in the attached spreadsheet.

Warm regards,
Adnet Advertising Campaign Operations Team
"""

        msg = MIMEMultipart()
        msg["From"] = SMTP_SENDER_EMAIL
        msg["To"] = ", ".join(targets)
        msg["Subject"] = email_subject
        msg.attach(MIMEText(email_body, "plain"))

        part = MIMEBase("application", "octet-stream")
        part.set_payload(buffer.getvalue())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename=IOCL_{report_type}_MIS_{date_display_str}.xlsx",
        )
        msg.attach(part)

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SMTP_SENDER_EMAIL, SMTP_SENDER_PASSWORD)
            server.sendmail(SMTP_SENDER_EMAIL, targets, msg.as_string())

        return True, f"Successfully sent {report_type} report for {date_display_str} to {', '.join(targets)}!"

    except Exception as e:
        return False, f"Failed to send email: {str(e)}"


if __name__ == "__main__":
    # Standard automated run for today
    success, msg = send_campaign_report(report_type="Daily")
    print(msg)