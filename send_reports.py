import argparse
import io
import os
import smtplib
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd
from supabase import create_client

# Environment Secrets from GitHub Actions
SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://atpvqeibzuzhhuowzbtk.supabase.co"
)
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SMTP_SENDER_EMAIL = os.environ.get("SMTP_SENDER_EMAIL", "")
SMTP_SENDER_PASSWORD = os.environ.get("SMTP_SENDER_PASSWORD", "")

# Strict recipient list: sends only to these 2 designated email addresses
RECIPIENT_EMAILS = ["alifaiz9111@gmail.com", "mehedihassan@indianoil.in"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def generate_and_dispatch(mode: str):
  now = datetime.now()
  days = 1 if mode == "daily" else 7
  cutoff_iso = (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")

  print(f"📊 Pulling {mode} records (since {cutoff_iso})...")

  # Fetch data from Supabase
  entries_res = (
      supabase.table("campaign_entries")
      .select("*")
      .gte("created_at", cutoff_iso)
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

  # Aggregate performance
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
            Winners=(
                "outcome",
                lambda x: (x.astype(str).str.lower() == "won").sum(),
            ),
            Unique_Customers=("phone_number", "nunique"),
        )
        .reset_index()
        .sort_values(by="Total_Scans", ascending=False)
    )
  else:
    ro_summary = pd.DataFrame(
        {"Status": [f"No scans recorded in past {days} day(s)"]}
    )

  vault_summary = (
      df_v.groupby(["denomination", "status"]).size().unstack(fill_value=0)
      if not df_v.empty
      else pd.DataFrame()
  )

  # Build Excel file
  buffer = io.BytesIO()
  with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    ro_summary.to_excel(
        writer,
        sheet_name="Daily_Summary" if mode == "daily" else "Weekly_Performance",
        index=False,
    )
    vault_summary.to_excel(writer, sheet_name="Vault_Inventory")
    if not df_e.empty:
      audit_cols = [
          c
          for c in [
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
          ]
          if c in df_e.columns
      ]
      df_e[audit_cols].to_excel(
          writer, sheet_name="Audit_Transactions", index=False
      )

  buffer.seek(0)
  date_str = now.strftime("%d-%b-%Y")
  scan_count = len(df_e)
  total_sales = (
      float(df_e["amount"].sum())
      if not df_e.empty and "amount" in df_e.columns
      else 0.0
  )

  # Email message
  msg = MIMEMultipart()
  msg["From"] = SMTP_SENDER_EMAIL
  msg["To"] = ", ".join(RECIPIENT_EMAILS)
  msg["Subject"] = (
      f"IOCL Kolkata DO - {mode.capitalize()} Campaign MIS Report ({date_str})"
  )

  body = f"""Dear Sir,

Please find attached the official {mode.capitalize()} Campaign MIS Report for the QR Sales Promotion Campaign (MS/XP95/XP100) under Kolkata Divisional Office.

Period Summary ({'Past 24 Hours' if mode == 'daily' else 'Past 7 Days'}):
- Total Scans: {scan_count:,}
- Total Fuel Sales Value Recorded: ₹{total_sales:,.2f}

Detailed outlet-wise breakups, voucher vault statuses, and complete transaction audits are included in the attached spreadsheet.

Warm regards,
Adnet Campaign Operations Team
"""
  msg.attach(MIMEText(body, "plain"))

  part = MIMEBase("application", "octet-stream")
  part.set_payload(buffer.getvalue())
  encoders.encode_base64(part)
  part.add_header(
      "Content-Disposition",
      f"attachment; filename=IOCL_{mode.capitalize()}_MIS_{date_str}.xlsx",
  )
  msg.attach(part)

  print(f"🚀 Dispatching to {RECIPIENT_EMAILS}...")
  with smtplib.SMTP("smtp.gmail.com", 587) as server:
    server.starttls()
    server.login(SMTP_SENDER_EMAIL, SMTP_SENDER_PASSWORD)
    server.sendmail(SMTP_SENDER_EMAIL, RECIPIENT_EMAILS, msg.as_string())
  print(f"✅ {mode.capitalize()} report dispatched successfully!")


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--mode", choices=["daily", "weekly"], default="weekly")
  args = parser.parse_args()
  generate_and_dispatch(args.mode)