import os
import re
import random
from datetime import date
import streamlit as st
from supabase import create_client, Client
from PIL import Image

# Mobile-first page layout
logo_img = "Indian_Oil_Logo.png" if os.path.exists("Indian_Oil_Logo.png") else "⛽"
st.set_page_config(page_title="IndianOil Rewards", page_icon=logo_img, layout="centered")

# Branding CSS (#f37022 Saffron Accent)
st.markdown(
    """
    <style>
    .block-container {
        max-width: 600px;
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    div.stButton > button:first-child,
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #f37022 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        padding: 10px 20px !important;
    }
    div.stButton > button:first-child:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        background-color: #d85c14 !important;
    }
    .ro-header-card {
        background: #fffdf9;
        border: 1px solid #fde2cf;
        border-left: 5px solid #f37022;
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 16px;
    }
    .welcome-banner {
        background-color: #fff7ed;
        border: 1px dashed #f37022;
        border-radius: 8px;
        padding: 12px 14px;
        font-size: 14px;
        color: #9a3412;
        margin-bottom: 20px;
        text-align: center;
    }
    .result-card-win {
        background-color: #ecfdf5;
        border: 2px solid #10b981;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        margin-top: 15px;
    }
    .result-card-loss {
        background-color: #f8fafc;
        border: 2px solid #cbd5e1;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        margin-top: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = init_supabase()

def mark_voucher_claimed(vault_id: int):
    if vault_id:
        try:
            db.table("voucher_vault").update({
                "status": "Claimed",
                "claimed_at": "now()"
            }).eq("id", vault_id).execute()
        except Exception:
            pass

# ----------------- CLAIM MODAL DIALOG -----------------
@st.dialog("🎉 Congratulations!")
def show_winner_dialog(voucher_id: int, claim_link: str, denomination: int):
    st.balloons()
    st.markdown(f"### You have won an Amazon Voucher worth ₹{denomination}!")
    
    st.markdown(
        f"""
        <div style="background: #ffffff; border: 1px dashed #10b981; border-radius: 8px; padding: 14px; margin: 12px 0; word-break: break-all; text-align: center;">
            <div style="font-size: 12px; color: #6b7280; margin-bottom: 6px;">YOUR AMAZON CLAIM LINK:</div>
            <a href="{claim_link}" target="_blank" style="font-size: 15px; font-weight: 700; color: #f37022; text-decoration: underline;">
                {claim_link}
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.write("Click below to open and claim your voucher directly on Amazon:")

    mark_voucher_claimed(voucher_id)

    st.link_button(
        "🎁 Open Amazon & Claim Voucher",
        url=claim_link,
        use_container_width=True
    )

LOCAL_LOGO_PATH = "Indian_Oil_Logo.png"
PROD_FALLBACK_URL = "https://images.seeklogo.com/logo-png/28/1/indian-oil-logo-png_seeklogo-284720.png"

ro_code = st.query_params.get("ro", None)

# Logo Display
c1, c2, c3 = st.columns([1, 1.2, 1])
with c2:
    st.markdown("<br><br>", unsafe_allow_html=True)
    if os.path.exists(LOCAL_LOGO_PATH):
        st.image(LOCAL_LOGO_PATH, use_container_width=True)
    elif os.path.exists("Indian_Oil_Logo.png"):
        st.image("Indian_Oil_Logo.png", use_container_width=True)
    else:
        st.image(PROD_FALLBACK_URL, use_container_width=True)
    st.markdown("<h2 style='text-align: center; margin-top: -45px; margin-left: 25px;'>IndianOil</h2>", unsafe_allow_html=True)

if not ro_code:
    st.error("⚠️ Invalid station link. Please scan the official QR code at the IndianOil fuel dispenser.")
    st.stop()


# Real-time check directly from Supabase (no cache, 0-second delay)
def get_station_details(code: str):
    res = db.table("retail_outlets").select("ro_code, ro_name, district, address, is_active").eq("ro_code", str(code).strip()).execute()
    return res.data[0] if res.data else None

station = get_station_details(ro_code)
if not station:
    st.error(f"⚠️ Retail Outlet Code **{ro_code}** not recognized.")
    st.stop()

# Real-time ban enforcement
if not station.get("is_active", True):
    st.markdown(
        f"""
        <div style="
            background-color: #fff1f2;
            border: 2px solid #f43f5e;
            border-left: 6px solid #e11d48;
            border-radius: 10px;
            padding: 22px;
            margin: 20px 0;
            color: #881337;
            font-family: inherit;
            line-height: 1.6;
            box-shadow: 0 4px 12px rgba(225, 29, 72, 0.08);
        ">
            <h3 style="margin: 0 0 10px 0; color: #be123c; font-size: 19px;">
                🚫 Station Access Restricted
            </h3>
            <p style="margin: 0 0 10px 0; font-size: 15px; color: #4c0519; font-weight: 500;">
                Because of spamming, this Petrol Pump (<b>RO Code: {ro_code}</b>) is currently banned from participating in this campaign.
            </p>
            <p style="margin: 0; font-size: 13px; color: #9f1239;">
                Entries and rewards submission for this outlet have been locked by Kolkata Divisional Office.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.stop()

ro_name = station.get("ro_name", "IndianOil Outlet")
ro_address = station.get("address") or f"{station.get('district', '')}, India"

st.markdown(
    f"""
    <div class="ro-header-card">
        <h3 style="margin: 0; color: #1e293b; font-size: 20px;">⛽ {ro_name}</h3>
        <p style="margin: 3px 0 0 0; color: #64748b; font-size: 13px;">| <b>RO Code:</b> {ro_code} <br>| <b>Location:</b> {ro_address}</p>
    </div>
    <div class="welcome-banner">
        🎉 <b>Welcome to IndianOil {ro_name}!</b><br>
        Enter your receipt details below for a chance to win instant Amazon vouchers on your fill today.
    </div>
    """,
    unsafe_allow_html=True
)

if "form_submitted" not in st.session_state:
    st.session_state.form_submitted = False
if "submission_result" not in st.session_state:
    st.session_state.submission_result = None

# Trigger Modal Dialog if pending
if st.session_state.get("pending_dialog") == "WINNER":
    v_data = st.session_state.get("winning_voucher_data", {})
    st.session_state.pending_dialog = None
    show_winner_dialog(
        voucher_id=v_data.get("id"),
        claim_link=v_data.get("claim_link", ""),
        denomination=v_data.get("denomination", 40)
    )

# ----------------- 2. RESULT SCREENS (WIN & BETTER LUCK NEXT TIME) -----------------
if st.session_state.form_submitted:
    result = st.session_state.submission_result

    if result["outcome"] == "WON":
        claim_url = result.get("claim_link", "#")

        st.markdown(
            f"""
            <div class="result-card-win" style="text-align: left; line-height: 1.6;">
                <h3 style="color: #065f46; margin-top: 0;">Heartiest Congratulations, {result['name']}! 🌟</h3>
                <p style="font-size: 15px; color: #047857; margin-bottom: 12px;">
                    Thank you for fuelling at IndianOil <b>{ro_name}</b>. You have won an <b>Amazon Voucher worth Rs. {result['denomination']}!</b> 💳✨
                </p>
                <div style="background: #ffffff; border: 1px dashed #10b981; border-radius: 8px; padding: 14px; text-align: center; margin: 15px 0; word-break: break-all;">
                    <div style="font-size: 12px; color: #6b7280; margin-bottom: 6px;">YOUR AMAZON CLAIM LINK:</div>
                    <a href="{claim_url}" target="_blank" style="font-size: 15px; font-weight: 700; color: #f37022; text-decoration: underline;">
                        {claim_url}
                    </a>
                </div>
                <p style="font-size: 14px; color: #374151; margin-bottom: 4px;">
                    Keep fuelling, keep winning! 🚗💨
                </p>
                <p style="font-size: 13px; font-weight: 600; color: #f37022; margin-top: 0;">
                    — Team IndianOil
                </p>
                <hr style="border: 0; border-top: 1px solid #d1fae5; margin: 15px 0;">
                <p style="font-size: 12px; color: #047857; margin-bottom: 0;">
                    ✅ <i>Your entry has also been registered for the Apple iPhone 17 Pro Max & vivo 5G Lucky Draw!</i>
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.write("")
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            mark_voucher_claimed(result.get("vault_id"))
            st.link_button(
                "🛒 Open Amazon & Claim",
                url=claim_url,
                use_container_width=True
            )

        with c_btn2:
            if st.button("📋 Copy / Mark Received", use_container_width=True, key="btn_copy_received"):
                mark_voucher_claimed(result.get("vault_id"))
                st.session_state["voucher_copied"] = True

        if st.session_state.get("voucher_copied", False):
            st.success(f"✅ Voucher marked as Claimed! Link: {claim_url}")

    else:
        st.markdown(
            f"""
            <div class="result-card-loss" style="text-align: left; line-height: 1.6;">
                <h3 style="color: #475569; margin-top: 0;">Better Luck Next Time! ⛽</h3>
                <p style="font-size: 15px; color: #334155; margin-bottom: 12px;">
                    Thank you for fuelling with IndianOil, <b>{result['name']}</b> at <b>{ro_name}</b>.
                </p>
                <div style="background: #ffffff; border: 1px dashed #cbd5e1; border-radius: 8px; padding: 12px; margin: 12px 0;">
                    <p style="font-size: 13px; color: #065f46; font-weight: 600; margin: 0;">
                        🎉 Good news! Your receipt has been successfully entered into the <b>Mega Lucky Draw</b> for the Apple iPhone 17 Pro Max & vivo 5G Smartphones!
                    </p>
                </div>
                <p style="font-size: 14px; color: #374151; margin-bottom: 4px;">
                    Keep fuelling, keep winning! 🚗💨
                </p>
                <p style="font-size: 13px; font-weight: 600; color: #f37022; margin-top: 0;">
                    — Team IndianOil
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.write("")
    if st.button("Back to Home", use_container_width=True):
        st.session_state.form_submitted = False
        st.session_state.submission_result = None
        st.session_state.opened_amazon = False
        st.session_state.voucher_copied = False
        st.rerun()

    st.stop()

# ----------------- ENTRY FORM (TRANSACTION NO REMOVED) -----------------
with st.form("customer_scan_form", clear_on_submit=False):
    st.markdown("#### Enter Fueling Details")

    col_name, col_phone = st.columns(2)
    with col_name:
        customer_name = st.text_input("Customer Name *", placeholder="Enter your full name").strip()
    with col_phone:
        mobile_no = st.text_input("Mobile Number *", max_chars=10, placeholder="10-digit number").strip()

    receipt_no = st.text_input("Receipt / Invoice No. *", placeholder="e.g. 245003226J400675").strip()

    col_grade, col_amount = st.columns(2)
    with col_grade:
        fuel_grade = st.selectbox("Fuel Grade *", ["MS", "XP95", "XP100"])
    with col_amount:
        amount = st.number_input("Fuel Amount (₹) *", min_value=500.0, value=500.0, step=50.0, format="%.2f")

    submit_pressed = st.form_submit_button("Submit & Reveal Reward 🎁", use_container_width=True)

# ----------------- EXECUTION & BUSINESS RULES -----------------
if submit_pressed:
    errors = []
    if not customer_name or len(customer_name) < 2:
        errors.append("Please provide a valid Customer Name.")
    if not re.match(r"^[6-9]\d{9}$", mobile_no):
        errors.append("Please enter a valid 10-digit Indian mobile number.")
    if not receipt_no:
        errors.append("Receipt / Invoice number is required.")
    if amount < 500.0:
        errors.append("Minimum fueling amount to participate is ₹500.")

    if errors:
        for err in errors:
            st.error(f"❌ {err}")
    else:
        clean_bill = receipt_no.replace(" ", "").upper()
        normalized_bill = clean_bill[-6:] if len(clean_bill) >= 6 else clean_bill

        # 1. Unique receipt check per RO
        dup_bill = db.table("campaign_entries").select("id").eq("ro_code", ro_code).eq("bill_number", normalized_bill).execute()
        if dup_bill.data:
            st.error("⚠️ This invoice number has already been entered at this outlet.")
            st.stop()

        # 2. Check 1 scan per mobile number per day
        today_iso_start = f"{date.today().isoformat()}T00:00:00"
        daily_mobile_scan = db.table("campaign_entries").select("id")\
            .eq("phone_number", mobile_no)\
            .gte("created_at", today_iso_start)\
            .execute()

        if daily_mobile_scan.data:
            db.table("campaign_entries").insert({
                "ro_code": ro_code,
                "customer_name": customer_name,
                "phone_number": mobile_no,
                "bill_number": normalized_bill,
                "fuel_grade": fuel_grade,
                "amount": float(amount),
                "outcome": "Better Luck Next Time"
            }).execute()

            st.session_state.form_submitted = True
            st.session_state.submission_result = {
                "outcome": "LOST",
                "name": customer_name,
                "reason": "Daily limit reached (1 entry per day per mobile number)."
            }
            st.rerun()

        # 3. Winning Rule: 3rd, 13th, 23rd, 33rd... (Every 10 scans starting from scan 3)
        today_ro_scans = db.table("campaign_entries").select("id", count="exact")\
            .eq("ro_code", ro_code)\
            .gte("created_at", today_iso_start)\
            .execute()

        current_scan_number = (today_ro_scans.count or 0) + 1
        is_cadence_winner = (current_scan_number % 2 == 1)

        assigned_voucher = None
        is_winner = False

        if is_cadence_winner:
            # 4. Check available quota from ro_daily_quota (13 base + carry over)
            quota_res = db.table("ro_daily_quota").select("*")\
                .eq("ro_code", ro_code)\
                .eq("quota_date", str(date.today()))\
                .execute()

            has_quota = True
            claimed_today = 0

            if quota_res.data:
                q_row = quota_res.data[0]
                total_avail = q_row.get("total_available", 13)
                claimed_today = q_row.get("claimed_count", 0)
                if claimed_today >= total_avail:
                    has_quota = False

            if has_quota:
                # 5. Exact pattern: 10 of ₹10, 2 of ₹20, 1 of ₹40
                DAILY_PATTERN = [10, 10, 10, 20, 10, 10, 40, 10, 10, 20, 10, 10, 10]
                winner_index = claimed_today % len(DAILY_PATTERN)
                target_denomination = DAILY_PATTERN[winner_index]

                # Fetch available voucher with target denomination (station-specific first, then unassigned pool)
                v_res = db.table("voucher_vault").select("id, denomination, claim_link")\
                    .eq("ro_code", ro_code)\
                    .eq("denomination", target_denomination)\
                    .ilike("status", "available")\
                    .limit(1)\
                    .execute()

                if not v_res.data:
                    v_res = db.table("voucher_vault").select("id, denomination, claim_link")\
                        .is_("ro_code", "null")\
                        .eq("denomination", target_denomination)\
                        .ilike("status", "available")\
                        .limit(1)\
                        .execute()

                # Fallback to any available voucher if target denomination is temporarily out
                if not v_res.data:
                    v_res = db.table("voucher_vault").select("id, denomination, claim_link")\
                        .ilike("status", "available")\
                        .limit(1)\
                        .execute()

                if v_res.data:
                    assigned_voucher = v_res.data[0]
                    is_winner = True

                    db.table("voucher_vault").update({
                        "status": "Allocated",
                        "claimed_by_phone": mobile_no,
                        "ro_code": ro_code,
                        "allocated_at": "now()"
                    }).eq("id", assigned_voucher["id"]).execute()

                    if quota_res.data:
                        db.table("ro_daily_quota").update({
                            "claimed_count": claimed_today + 1
                        }).eq("id", q_row["id"]).execute()

                    st.session_state.pending_dialog = "WINNER"
                    st.session_state.winning_voucher_data = {
                        "id": assigned_voucher["id"],
                        "claim_link": assigned_voucher["claim_link"],
                        "denomination": assigned_voucher.get("denomination", target_denomination)
                    }

        # 6. Insert Entry
        final_outcome = "Won" if is_winner else "Better Luck Next Time"
        claim_url = assigned_voucher["claim_link"] if is_winner else None
        denom_val = assigned_voucher.get("denomination", 40) if is_winner else 40
        vault_id = assigned_voucher["id"] if is_winner else None

        db.table("campaign_entries").insert({
            "ro_code": ro_code,
            "customer_name": customer_name,
            "phone_number": mobile_no,
            "bill_number": normalized_bill,
            "fuel_grade": fuel_grade,
            "amount": float(amount),
            "outcome": final_outcome
        }).execute()

        st.session_state.form_submitted = True
        st.session_state.submission_result = {
            "outcome": "WON" if is_winner else "LOST",
            "name": customer_name,
            "phone": mobile_no,
            "claim_link": claim_url,
            "denomination": denom_val,
            "vault_id": vault_id
        }
        st.rerun()