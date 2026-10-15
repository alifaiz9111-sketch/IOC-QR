import pandas as pd
from supabase import create_client

# Supabase Credentials
SUPABASE_URL = "https://atpvqeibzuzhhuowzbtk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF0cHZxZWlienV6aGh1b3d6YnRrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEzNjc4NjEsImV4cCI6MjEwNjk0Mzg2MX0.yrw0p1S7moCcUoEMdvDSnmhlWPP076CNF57_QqeEIos"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Read the uploaded Excel file
EXCEL_FILE = "vouchers.xlsx"
df = pd.read_excel(EXCEL_FILE)

# Normalize column names
df.columns = df.columns.str.strip().str.lower()

records = []
for idx, row in df.iterrows():
    # Complete, unstripped link
    link = str(row.get("claim_link", "")).strip()
    if not link or link.lower() == "nan":
        continue

    # RO assignment (None if global fallback pool)
    ro = str(row.get("ro_code", "")).strip()
    ro_code_val = ro if ro and ro.lower() != "nan" else None

    # Face value
    denom = row.get("denomination", 40)
    try:
        denom = int(denom)
    except (ValueError, TypeError):
        denom = 40

    records.append({
        "ro_code": ro_code_val,
        "denomination": denom,
        "claim_link": link,
        "status": "Available"
    })

# Bulk insert
if records:
    print(f"Uploading {len(records)} vouchers directly to Supabase...")
    response = supabase.table("voucher_vault").insert(records).execute()
    print(f"Successfully uploaded {len(response.data)} vouchers with complete URLs!")
else:
    print("No valid vouchers found in the Excel file.")