import pandas as pd

df = pd.read_excel("vouchers.xlsx")
print("Detected Columns:", [c.strip().lower() for c in df.columns])

# Find any matching link column
col = None
for c in df.columns:
    if c.strip().lower() in ["claim_link", "link", "url", "voucher_link"]:
        col = c
        break

print(f"Matched Link Column: {col}")

if col:
    non_empty = df[col].dropna()
    http_links = non_empty[non_empty.astype(str).str.strip().str.startswith("http")]
    print(f"Total rows in Excel: {len(df)}")
    print(f"Non-empty values in '{col}': {len(non_empty)}")
    print(f"Values starting with 'http': {len(http_links)}")