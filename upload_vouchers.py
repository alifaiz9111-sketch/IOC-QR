from collections import Counter
import pandas as pd
from supabase import create_client

# ----------------- SUPABASE CONFIGURATION -----------------
SUPABASE_URL = "https://atpvqeibzuzhhuowzbtk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF0cHZxZWlienV6aGh1b3d6YnRrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEzNjc4NjEsImV4cCI6MjEwNjk0Mzg2MX0.yrw0p1S7moCcUoEMdvDSnmhlWPP076CNF57_QqeEIos"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------- READ EXCEL FILE -----------------
EXCEL_FILE = "vouchers.xlsx"
df = pd.read_excel(EXCEL_FILE)

# Normalize column names (strip whitespace and convert to lowercase)
df.columns = df.columns.str.strip().str.lower()

records = []
for idx, row in df.iterrows():
    # 1. Read claim link (accepts 'claim_link', 'link', or 'url')
    link = str(row.get("claim_link") or row.get("link") or row.get("url") or "").strip()
    if not link or link.lower() == "nan" or not link.startswith("http"):
        continue

    # 2. Read RO Code safely (ensures empty cells become true SQL NULL)
    raw_ro = row.get("ro_code")
    ro_str = str(raw_ro).strip() if pd.notna(raw_ro) and raw_ro is not None else ""
    ro_code_val = ro_str if ro_str and ro_str.lower() not in ("nan", "none", "") else None

    # 3. Read Denomination (defaults to 10 if missing/blank)
    raw_denom = row.get("denomination", 10)
    try:
        denom_val = int(float(raw_denom))
    except (ValueError, TypeError):
        denom_val = 10

    records.append({
        "ro_code": ro_code_val,
        "denomination": denom_val,
        "claim_link": link,
        "status": "Available"
    })

# ----------------- BATCH UPLOAD TO DATABASE -----------------
BATCH_SIZE = 50
if records:
    print(f"\n🚀 Found {len(records)} valid vouchers in {EXCEL_FILE}.")
    print(f"Uploading to Supabase in batches of {BATCH_SIZE}...")

    total_uploaded = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        response = supabase.table("voucher_vault").insert(batch).execute()
        total_uploaded += len(response.data)
        print(f"  -> Uploaded {total_uploaded}/{len(records)} vouchers...")

    # Count breakdown by denomination
    counts = Counter(r["denomination"] for r in records)
    print("\n" + "=" * 38)
    print("         UPLOAD SUMMARY TABLE         ")
    print("=" * 38)
    for denom in sorted(counts.keys()):
        print(f"   ₹{denom:<4} Vouchers : {counts[denom]:>6} uploaded")
    print("-" * 38)
    print(f"   TOTAL UPLOADED : {total_uploaded:>6} vouchers")
    print("=" * 38 + "\n")
else:
    print("\n❌ No valid vouchers with HTTP/HTTPS links found in the Excel file.")