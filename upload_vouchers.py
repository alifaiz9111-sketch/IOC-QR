import pandas as pd
from datetime import timedelta

# Exact record from your database query
record = {'customer_name': 'Ajay Garg', 'phone_number': '8233926165', 'created_at': '2026-11-01T12:44:57+00:00'}
df = pd.DataFrame([record])

# New conversion logic
ts = pd.to_datetime(df["created_at"], utc=True) + timedelta(hours=5, minutes=30)
df["Scan_Date"] = ts.dt.strftime("%d-%m-%Y")
df["Scan_Time"] = ts.dt.strftime("%I:%M:%S %p")

print(df[["Scan_Date", "Scan_Time", "customer_name", "phone_number"]])