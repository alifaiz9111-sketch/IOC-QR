import os
import io
import argparse
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import pandas as pd
from supabase import create_client

# ---------------- CONFIGURATION ----------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://atpvqeibzuzhhuowzbtk.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SMTP_SENDER_EMAIL = os.environ.get("SMTP_SENDER_EMAIL", "")
SMTP_SENDER_PASSWORD = os.environ.get("SMTP_SENDER_PASSWORD", "")

RECIPIENT_ENV = os.environ.get("RECIPIENT_EMAILS", "alifaiz9111@gmail.com, mehedihassan@indianoil.in")
RECIPIENT_EMAILS = [email.strip() for email in RECIPIENT_ENV.split(",") if email.strip()]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_and_dispatch(mode: str):
    now = datetime.now()
    days = 1 if mode == "daily" else 7
    cutoff_iso = (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")

    print(f"📊 Pulling {mode} data (cutoff: {cutoff_iso})...")

    # 1. Fetch data from Supabase
    entries_res = supabase.table("campaign_entries").select("*").gte("created_at", cutoff_iso).execute()
    outlets_res = supabase.table("retail_outlets").select("ro_code, ro_name, district, sales_area").execute()
    vouchers_res = supabase.table("voucher_vault").select("ro_code, denomination, status").execute()

    df_e = pd.DataFrame(entries_res.data or [])
    df_o = pd.DataFrame(outlets_res.data or [])
    df_v = pd.DataFrame(vouchers_res.data or [])

    # 2. Process Performance & Aggregations
    if not df_e.empty and not df_o.empty:
        df_e["ro_code"] = df_e["ro_code"].astype(str)
        df_o["ro_code"] = df_o["ro_code"].astype(str)
        df_e = df_e.merge(df_o, on="ro_code", how="left")

        # Convert timestamp to IST
        df_e["created_at_ist"] = pd.to_datetime(df_e["created_at"], errors="coerce", utc=True).dt.tz_convert("Asia/Kolkata")
        df_e["Scan_Date"] = df_e["created_at_ist"].dt.strftime("%d-%m-%Y")
        df_e["Scan_Time"] = df_e["created_at_ist"].dt.strftime("%I:%M:%S %p")

        ro_summary = df_e.groupby(["ro_code", "ro_name", "district"]).agg(
            Total_Scans=("bill_number", "count"),
            Total_Sales_Value=("amount", "sum"),
            Winners=("outcome", lambda x: (x.astype(str).str.lower() == "won").sum()),
            Unique_Customers=("phone_number", "nunique")
        ).reset_index().sort_values(by="Total_Scans", ascending=False)
    else:
        ro_summary = pd.DataFrame({"Status": [f"No transactions recorded in the past {days} day(s)"]})

    # 3. Voucher Vault Summary
    if not df_v.empty:
        vault_summary = df_v.groupby(["denomination", "status"]).size().unstack(fill_value=0).reset_index()
    else:
        vault_summary = pd.DataFrame({"Status": ["Voucher vault data unavailable"]})

    # 4. Generate Multi-Tab Excel Spreadsheet
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        sheet_label = "Daily_RO_Summary" if mode == "daily" else "Weekly_RO_Performance"
        ro_summary.to_excel(writer, sheet_name=sheet_label, index=False)
        vault_summary.to_excel(writer, sheet_name="Vault_Inventory", index=False)
        
        if not df_e.empty:
            export_cols = [c for c in ["Scan_Date", "Scan_Time", "ro_code", "ro_name", "district", "customer_name", "phone_number", "bill_number", "fuel_grade", "amount", "outcome"] if c in df_e.columns]
            df_e[export_cols].to_excel(writer, sheet_name="Audit_Transactions", index=False)

    excel_buffer.seek(0)

    # 5. Build Email Content
    date_str = now.strftime("%d-%b-%Y")
    scan_count = len(df_e)
    total_sales = float(df_e["amount"].sum()) if not df_e.empty and "amount" in df_e.columns else 0.0
    report_title = f"IOCL Kolkata DO - {'Daily' if mode == 'daily' else 'Weekly'} Campaign MIS Report ({date_str})"

    msg = MIMEMultipart()
    msg["From"] = SMTP_SENDER_EMAIL
    msg["To"] = ", ".join(RECIPIENT_EMAILS)
    msg["Subject"] = report_title

    body = f"""Dear Sir,

Please find attached the official {'Daily' if mode == 'daily' else 'Weekly'} Campaign MIS Report for the QR Sales Promotion Campaign (MS/XP95/XP100) under Kolkata Divisional Office.

Period Summary ({'Past 24 Hours' if mode == 'daily' else 'Past 7 Days'}):
- Report Generated: {date_str}
- Total Scans/Entries: {scan_count:,}
- Total Fuel Sales Recorded: ₹{total_sales:,.2f}

Detailed outlet-wise breakups, voucher vault statuses, and complete transaction audits are included in the attached spreadsheet.

Warm regards,
Adnet Campaign Operations Team
IndianOil Kolkata Divisional Office Promotion
"""
    msg.attach(MIMEText(body, "plain"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(excel_buffer.getvalue())
    encoders.encode_base64(part)
    filename = f"IOCL_{mode.capitalize()}_MIS_{date_str}.xlsx"
    part.add_header("Content-Disposition", f"attachment; filename={filename}")
    msg.attach(part)

    # 6. Dispatch via SMTP
    print(f"🚀 Dispatching email to: {', '.join(RECIPIENT_EMAILS)}...")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SMTP_SENDER_EMAIL, SMTP_SENDER_PASSWORD)
        server.sendmail(SMTP_SENDER_EMAIL, RECIPIENT_EMAILS, msg.as_string())
    print(f"✅ Successfully delivered {mode} report!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    args = parser.parse_args()
    generate_and_dispatch(args.mode)