import os
import io
import smtplib
import traceback
from datetime import datetime, timedelta, date, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import pandas as pd
from supabase import create_client

# Indian Standard Time (UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

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
    Sends the MIS report for window:
    (selected_date - 1 day at 5:30 PM IST) to (selected_date at 5:30 PM IST).
    Guarantees no blank date/time cells and sorts chronologically ascending.
    """
    try:
        # 1. Determine target date
        if selected_date is None:
            target_d = datetime.now(IST).date()
        elif isinstance(selected_date, str):
            target_d = datetime.strptime(selected_date, "%Y-%m-%d").date()
        else:
            target_d = selected_date

        # Window: Yesterday 5:30 PM IST to Selected Date 5:30 PM IST
        end_dt_ist = datetime(target_d.year, target_d.month, target_d.day, 17, 30, 0, tzinfo=IST)
        start_dt_ist = end_dt_ist - timedelta(days=1)

        start_utc_iso = start_dt_ist.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        end_utc_iso = end_dt_ist.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        date_display_str = target_d.strftime("%d-%b-%Y")
        print(f"[{report_type} MIS] Querying window: {start_utc_iso}Z to {end_utc_iso}Z...")

        # 2. Query Supabase
        entries_res = (
            supabase.table("campaign_entries")
            .select("*")
            .gte("created_at", start_utc_iso)
            .lte("created_at", end_utc_iso)
            .execute()
        )
        outlets_res = (
            supabase.table("retail_outlets")
            .select("ro_code, ro_name, district")
            .execute()
        )

        raw_entries = entries_res.data or []
        raw_outlets = outlets_res.data or []
        print(f"[{report_type} MIS] Retrieved {len(raw_entries)} entries and {len(raw_outlets)} outlets.")

        df_e = pd.DataFrame(raw_entries)
        df_o = pd.DataFrame(raw_outlets)

        if not df_e.empty:
            # 3. Robust Datetime Parsing with Fallbacks
            # Convert raw created_at to UTC timestamp
            df_e["utc_dt"] = pd.to_datetime(df_e.get("created_at"), errors="coerce", utc=True)
            
            # Fallback for any missing/malformed row to the target day in UTC
            default_utc = datetime(target_d.year, target_d.month, target_d.day, 12, 0, 0, tzinfo=timezone.utc)
            df_e["utc_dt"] = df_e["utc_dt"].fillna(default_utc)

            # Sort strictly ascending (oldest yesterday -> newest today)
            df_e = df_e.sort_values(by="utc_dt", ascending=True).reset_index(drop=True)

            # Convert to IST (+5:30)
            df_e["ist_dt"] = df_e["utc_dt"] + timedelta(hours=5, minutes=30)

            # Format strings
            df_e["Scan_Date"] = df_e["ist_dt"].dt.strftime("%d-%m-%Y")
            df_e["Scan_Time"] = df_e["ist_dt"].dt.strftime("%I:%M:%S %p")

            # Final safety check: Replace any remaining nulls or empty strings
            df_e["Scan_Date"] = df_e["Scan_Date"].fillna(target_d.strftime("%d-%m-%Y"))
            df_e["Scan_Time"] = df_e["Scan_Time"].fillna("12:00:00 PM")
            df_e.loc[df_e["Scan_Date"].astype(str).str.strip().isin(["", "nan", "NaT", "None"]), "Scan_Date"] = target_d.strftime("%d-%m-%Y")
            df_e.loc[df_e["Scan_Time"].astype(str).str.strip().isin(["", "nan", "NaT", "None"]), "Scan_Time"] = "12:00:00 PM"

            # 4. Merge Outlet Details
            if not df_o.empty:
                df_e["ro_code"] = df_e["ro_code"].astype(str).str.strip()
                df_o["ro_code"] = df_o["ro_code"].astype(str).str.strip()
                df_o = df_o.drop_duplicates(subset=["ro_code"])
                df_e = df_e.merge(df_o, on="ro_code", how="left")

            # Fill missing names/districts if any
            df_e["ro_name"] = df_e["ro_name"].fillna("IndianOil Outlet")
            df_e["district"] = df_e["district"].fillna("WEST BENGAL")

            # 5. Summary Sheet (Unique_Customers excluded)
            ro_summary = (
                df_e.groupby(["ro_code", "ro_name", "district"], as_index=False)
                .agg(
                    Total_Scans=("bill_number", "count"),
                    Total_Sales_Value=("amount", "sum"),
                    Winners=("outcome", lambda x: (x.astype(str).str.lower() == "won").sum()),
                )
                .sort_values(by="Total_Scans", ascending=False)
            )
        else:
            ro_summary = pd.DataFrame({
                "Status": [f"No scans recorded between {start_dt_ist.strftime('%d-%b-%Y %I:%M %p')} and {end_dt_ist.strftime('%d-%b-%Y %I:%M %p')} IST"]
            })

        # 6. Build Clean Excel in Memory
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            # Sheet 1: Summary
            ro_summary.to_excel(writer, sheet_name=f"{report_type}_Summary", index=False)
            
            # Sheet 2: Audit Transactions (outcome excluded, sorted ascending, no Vault_Inventory sheet)
            if not df_e.empty:
                candidate_cols = [
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
                ]
                final_cols = [col for col in candidate_cols if col in df_e.columns]
                df_e[final_cols].to_excel(writer, sheet_name="Audit_Transactions", index=False)

        buffer.seek(0)

        # 7. Recipients and Dispatch
        if recipient_email:
            targets = [e.strip() for e in str(recipient_email).split(",") if e.strip()]
        else:
            targets = DEFAULT_RECIPIENT_EMAILS

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

        print(f"[{report_type} MIS] Connecting to SMTP server...")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SMTP_SENDER_EMAIL, SMTP_SENDER_PASSWORD)
            server.sendmail(SMTP_SENDER_EMAIL, targets, msg.as_string())

        success_msg = f"Successfully dispatched {report_type} report for {date_display_str} to {', '.join(targets)}!"
        print(f"[{report_type} MIS] ✅ {success_msg}")
        return True, success_msg

    except Exception as e:
        err_details = traceback.format_exc()
        print(f"[{report_type} MIS ERROR]\n{err_details}")
        return False, f"Failed to send email: {str(e)}"


if __name__ == "__main__":
    success, msg = send_campaign_report(report_type="Daily")
    print("Execution Result:", msg)