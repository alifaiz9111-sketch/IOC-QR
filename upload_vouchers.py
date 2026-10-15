import pandas as pd
import toml
from supabase import create_client

# 1. Load Supabase credentials from your secrets file
secrets = toml.load(".streamlit/secrets.toml")
SUPABASE_URL = secrets["SUPABASE_URL"]
SUPABASE_KEY = secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Read the Excel file
EXCEL_FILE = "vouchers.xlsx"
df = pd.read_excel(EXCEL_FILE)

# Clean column headers
df.columns = df.columns.str.strip().str.lower()

records = []
for _, row in df.iterrows():
    link = str(row.get("claim_link", "")).strip()
    if not link or link.lower() == "nan":
        continue

    # RO code (optional: None if left blank for global pool)
    ro = str(row.get("ro_code", "")).strip()
    ro_code_val = ro if ro and ro.lower() != "nan" else None

    # Denomination (default 40 if missing)
    denom = row.get("denomination", 40)
    try:
        denom = int(denom)
    except (ValueError, TypeError):
        denom = 40

    records.append({
        "ro_code": ro_code_val,
        "voucher_code": "Amazon Voucher",
        "denomination": denom,
        "claim_link": link,
        "status": "Available"
    })

# 3. Bulk insert into Supabase voucher_vault
if records:
    print(f"Uploading {len(records)} vouchers to Supabase...")
    response = supabase.table("voucher_vault").insert(records).execute()
    print(f"Successfully uploaded {len(response.data)} vouchers!")
else:
    print("No valid vouchers found in the Excel file.")