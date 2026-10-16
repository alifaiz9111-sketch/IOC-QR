import pandas as pd
from collections import Counter
from supabase import create_client

# ----------------- SUPABASE CREDENTIALS -----------------
SUPABASE_URL = "https://atpvqeibzuzhhuowzbtk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF0cHZxZWlienV6aGh1b3d6YnRrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEzNjc4NjEsImV4cCI6MjEwNjk0Mzg2MX0.yrw0p1S7moCcUoEMdvDSnmhlWPP076CNF57_QqeEIos"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

EXCEL_FILE = "vouchers.xlsx"
df = pd.read_excel(EXCEL_FILE)
df.columns = df.columns.str.strip().str.lower()

# 1. Fetch already existing links in voucher_vault to prevent duplicate insertion
print("🔍 Checking existing links in database...")
existing_links = set()
try:
    page_size = 1000
    start = 0
    while True:
        res = supabase.table("voucher_vault").select("claim_link").range(start, start + page_size - 1).execute()
        if not res.data:
            break
        for item in res.data:
            if item.get("claim_link"):
                existing_links.add(item["claim_link"].strip())
        if len(res.data) < page_size:
            break
        start += page_size
    print(f"Found {len(existing_links)} existing links in Supabase.")
except Exception as e:
    print(f"Warning fetching existing links: {e}")

# 2. Parse, clean, and deduplicate Excel records
records = []
seen_in_file = set()

for idx, row in df.iterrows():
    link = str(row.get("claim_link") or row.get("link") or "").strip()
    if not link or link.lower() == "nan" or not link.startswith("http"):
        continue

    # Skip duplicates within the file or already in DB
    if link in seen_in_file or link in existing_links:
        continue
    seen_in_file.add(link)

    # Empty ro_code becomes SQL NULL (unassigned global pool)
    raw_ro = row.get("ro_code")
    ro_str = str(raw_ro).strip() if pd.notna(raw_ro) and raw_ro is not None else ""
    ro_code_val = ro_str if ro_str and ro_str.lower() not in ("nan", "none", "") else None

    # Denomination parsing
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

# 3. Batch Upload
BATCH_SIZE = 100
if records:
    print(f"\n🚀 Ready to upload {len(records)} fresh unique vouchers...")
    total_uploaded = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        response = supabase.table("voucher_vault").insert(batch).execute()
        total_uploaded += len(response.data)
        print(f"  -> Uploaded {total_uploaded}/{len(records)}...")

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
    print("\n✅ All links in this Excel file are already present in the database.")