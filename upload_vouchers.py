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
    # Accept 'claim_link', 'link', or 'url'
    link = str(row.get("claim_link") or row.get("link") or row.get("url") or "").strip()
    if not link or link.lower() == "nan" or not link.startswith("http"):
        continue

    # Station assignment (None if unassigned/global fallback pool)
    ro = str(row.get("ro_code", "")).strip()
    ro_code_val = ro if ro and ro.lower() != "nan" else None

    # Face value (default 10)
    denom = row.get("denomination", 10)
    try:
        denom = int(float(denom))
    except (ValueError, TypeError):
        denom = 10

    records.append({
        "ro_code": ro_code_val,
        "denomination": denom,
        "claim_link": link,
        "status": "Available"
    })

# Batch insert to prevent PostgREST payload limits
BATCH_SIZE = 50
if records:
    print(f"Uploading {len(records)} vouchers to Supabase in batches of {BATCH_SIZE}...")
    total_uploaded = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        response = supabase.table("voucher_vault").insert(batch).execute()
        total_uploaded += len(response.data)
        print(f"Uploaded {total_uploaded}/{len(records)} records...")
    print(f"✅ Successfully uploaded {total_uploaded} vouchers with complete URLs!")
else:
    print("❌ No valid voucher links found in the Excel file.")