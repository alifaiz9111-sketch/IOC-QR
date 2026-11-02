from supabase import create_client

SUPABASE_URL = "https://atpvqeibzuzhhuowzbtk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF0cHZxZWlienV6aGh1b3d6YnRrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEzNjc4NjEsImV4cCI6MjEwNjk0Mzg2MX0.yrw0p1S7moCcUoEMdvDSnmhlWPP076CNF57_QqeEIos"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)
res = sb.table("campaign_entries").select("id, customer_name, phone_number, created_at").eq("phone_number", "8233926165").execute()
print(res.data)