import os
import re
import time
import random
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st
from supabase import create_client, Client
from PIL import Image

# ==============================================================================
# DISPLAY MODE TOGGLE
# True  = Executive Mega Lucky Draw Winner Showcase
# False = Original Customer QR Receipt Scan & Instant Voucher App (preserved)
# ==============================================================================
SHOW_MEGA_WINNER_DASHBOARD = True

BASE_DIR = Path(__file__).resolve().parent
LOCAL_LOGO_PATH = str(BASE_DIR / "Indian_Oil_Logo.png")
EXCEL_FILE_PATH = str(BASE_DIR / "19+1.xlsx")
PROD_FALLBACK_URL = "https://images.seeklogo.com/logo-png/28/1/indian-oil-logo-png_seeklogo-284720.png"

logo_img = LOCAL_LOGO_PATH if os.path.exists(LOCAL_LOGO_PATH) else None
st.set_page_config(
    page_title="IndianOil Mega Lucky Draw | Winners",
    page_icon=logo_img,
    layout="wide" if SHOW_MEGA_WINNER_DASHBOARD else "centered"
)

# Embedded verified 20 winners (used automatically if 19+1.xlsx or openpyxl is unavailable)
EMBEDDED_WINNERS = [
    {"rank": 1, "name": "Akshat Bhardwaj", "phone": "89XXXX9956", "ro_code": "138854", "ro_name": "TRINATH SERVICE STATION", "sales_area": "Barasat RSA", "bill_no": "587940"},
    {"rank": 2, "name": "Rio das", "phone": "62XXXX4145", "ro_code": "196643", "ro_name": "PAUL CHOWDHURY ENTERP", "sales_area": "Barasat RSA", "bill_no": "207725"},
    {"rank": 3, "name": "Ruma Barat", "phone": "97XXXX7829", "ro_code": "164774", "ro_name": "MADHABI SERVICE STN", "sales_area": "Garia RSA", "bill_no": "534165"},
    {"rank": 4, "name": "Anupam Mukhopadhyay", "phone": "89XXXX8987", "ro_code": "190654", "ro_name": "PRASADPUR SERVICE STATION", "sales_area": "Garia RSA", "bill_no": "340068"},
    {"rank": 5, "name": "Amitava Pal", "phone": "81XXXX4776", "ro_code": "338777", "ro_name": "SOUTHERN FUEL SERVICE", "sales_area": "Garia RSA", "bill_no": "222530"},
    {"rank": 6, "name": "Hirak Mukherjee", "phone": "70XXXX2240", "ro_code": "191100", "ro_name": "MANMATHA SERVICE CENTRE", "sales_area": "Kalyani RSA", "bill_no": "55566"},
    {"rank": 7, "name": "Khyati Chopra", "phone": "84XXXX4168", "ro_code": "138056", "ro_name": "LAUHATI SERVICE STN", "sales_area": "Kolkata New Town RSA", "bill_no": "206886"},
    {"rank": 8, "name": "Uma mondal", "phone": "90XXXX5784", "ro_code": "331989", "ro_name": "AGNIV SERVICE STATION", "sales_area": "Kolkata New Town RSA", "bill_no": "688346"},
    {"rank": 9, "name": "TAPAN KUMAR SARKAR", "phone": "98XXXX7296", "ro_code": "138621", "ro_name": "DELUXE SERVICE STN", "sales_area": "Kolkata South RSA", "bill_no": "407120"},
    {"rank": 10, "name": "Jadunathchauhan", "phone": "94XXXX9286", "ro_code": "138709", "ro_name": "LUXMI NARAYAN SER. STN", "sales_area": "Kolkata South RSA", "bill_no": "109073"},
    {"rank": 11, "name": "Mukesh Desai", "phone": "84XXXX2272", "ro_code": "190519", "ro_name": "JEET SERVICE STATION", "sales_area": "Kolkata South RSA", "bill_no": "295240"},
    {"rank": 12, "name": "Tushar Pujara", "phone": "91XXXX7213", "ro_code": "190523", "ro_name": "OM AUTO SERVICE CORPORATION", "sales_area": "Kolkata South RSA", "bill_no": "994231"},
    {"rank": 13, "name": "Saptarshi Dasgupta", "phone": "89XXXX2597", "ro_code": "137977", "ro_name": "B C DUTTA & BROTHERS", "sales_area": "Kolkata-North RSA", "bill_no": "808822"},
    {"rank": 14, "name": "Pooja Verma", "phone": "96XXXX8345", "ro_code": "138661", "ro_name": "HIRJEE AUTO CENTRE", "sales_area": "Kolkata-North RSA", "bill_no": "489947"},
    {"rank": 15, "name": "Monali Paswan", "phone": "98XXXX0269", "ro_code": "189016", "ro_name": "HAPPY SERVICE STATION", "sales_area": "Kolkata-North RSA", "bill_no": "962116"},
    {"rank": 16, "name": "Myra Kotecha", "phone": "97XXXX1600", "ro_code": "191111", "ro_name": "THE JANATA S/STATION", "sales_area": "Kolkata-North RSA", "bill_no": "506656"},
    {"rank": 17, "name": "Madhurima Midya", "phone": "96XXXX8692", "ro_code": "151172", "ro_name": "MA DURGA FUEL STN", "sales_area": "Krishnanagar RSA", "bill_no": "138810"},
    {"rank": 18, "name": "Priyanka Dutta", "phone": "94XXXX6972", "ro_code": "240739", "ro_name": "G.Q.MONDAL SERVICE STATION", "sales_area": "24 Parganas(S) RSA", "bill_no": "546568"},
    {"rank": 19, "name": "Kakoli De-Sarkar", "phone": "94XXXX1919", "ro_code": "385566", "ro_name": "ADHOC MATRI MONDIR FUEL STATION", "sales_area": "Kolkata New Town RSA", "bill_no": "169743"},
    {"rank": 20, "name": "Yuvaan Bhojani", "phone": "97XXXX3991", "ro_code": "392418", "ro_name": "ADHOC MAA SIDDHESHWARI FUEL STATION", "sales_area": "Kalyani RSA", "bill_no": "783884"},
]

# ==============================================================================
# MODE 1: EXECUTIVE MEGA LUCKY DRAW WINNER DASHBOARD
# ==============================================================================
if SHOW_MEGA_WINNER_DASHBOARD:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 960px;
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }
        div.stButton > button {
            background-color: #f37022 !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 6px !important;
            font-weight: 700 !important;
            font-size: 15px !important;
            padding: 12px 24px !important;
            letter-spacing: 0.4px !important;
            box-shadow: 0 4px 12px rgba(243, 112, 34, 0.25) !important;
            transition: all 0.25s ease !important;
        }
        div.stButton > button:hover {
            background-color: #d85c14 !important;
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(243, 112, 34, 0.35) !important;
        }
        @keyframes fadeSlideUp {
            0% {
                opacity: 0;
                transform: translateY(16px);
            }
            100% {
                opacity: 1;
                transform: translateY(0);
            }
        }
        @keyframes grandRevealScale {
            0% {
                opacity: 0;
                transform: scale(0.94);
            }
            100% {
                opacity: 1;
                transform: scale(1);
            }
        }
        .exec-header-box {
            background: linear-gradient(135deg, #02164f 0%, #0a2a7a 100%);
            border-bottom: 4px solid #f37022;
            border-radius: 10px;
            padding: 22px 28px;
            color: #ffffff;
            margin-bottom: 24px;
            box-shadow: 0 6px 18px rgba(2, 22, 79, 0.14);
        }
        .winner-row-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-left: 5px solid #02164f;
            border-radius: 8px;
            padding: 14px 20px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
            animation: fadeSlideUp 0.45s ease-out both;
        }
        .winner-row-card:hover {
            border-left-color: #f37022;
            background: #fffdf9;
        }
        .rank-badge {
            background-color: #02164f;
            color: #ffffff;
            font-weight: 700;
            font-size: 13px;
            padding: 6px 12px;
            border-radius: 6px;
            min-width: 78px;
            text-align: center;
            margin-right: 16px;
        }
        .rank-badge-top3 {
            background-color: #f37022;
        }
        .iphone-grand-card {
            background: linear-gradient(135deg, #fffdf9 0%, #fff7ed 100%);
            border: 2px solid #f37022;
            border-top: 6px solid #02164f;
            border-radius: 12px;
            padding: 30px 28px;
            margin-top: 22px;
            box-shadow: 0 12px 30px rgba(243, 112, 34, 0.18);
            animation: grandRevealScale 0.65s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .iphone-pill {
            display: inline-block;
            background-color: #02164f;
            color: #ffffff;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            padding: 6px 14px;
            border-radius: 4px;
            margin-bottom: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    @st.cache_data(ttl=60)
    def load_winners_data(filepath: str):
        records = None
        target_path = filepath if os.path.exists(filepath) else "19+1.xlsx"
        if os.path.exists(target_path):
            try:
                df = pd.read_excel(target_path, dtype=str)
                df.columns = [str(c).strip() for c in df.columns]

                def find_col(candidates):
                    for cand in candidates:
                        for col in df.columns:
                            if cand.lower() in col.lower():
                                return col
                    return None

                col_rank = find_col(["rank", "position", "prize_no", "sl", "serial"])
                col_name = find_col(["customer_name", "winner_name", "winner", "name"])
                col_phone = find_col(["phone", "mobile", "contact"])
                col_ro_code = find_col(["ro_code", "ro code", "outlet_code"])
                col_ro_name = find_col(["ro_name", "ro name", "outlet_name", "station"])
                col_area = find_col(["sales_area", "sales area", "rsa", "area", "district"])
                col_bill = find_col(["bill", "receipt", "invoice"])

                parsed = []
                for idx, row in df.iterrows():
                    raw_rank = None
                    if col_rank and pd.notna(row[col_rank]):
                        digits = re.findall(r"\d+", str(row[col_rank]))
                        if digits:
                            raw_rank = int(digits[0])
                    if raw_rank is None:
                        raw_rank = idx + 1

                    raw_phone = str(row[col_phone]).strip() if col_phone and pd.notna(row[col_phone]) else ""
                    masked_phone = (
                        f"{raw_phone[:2]}XXXX{raw_phone[-4:]}"
                        if len(raw_phone) == 10 and raw_phone.isdigit()
                        else raw_phone
                    )

                    parsed.append({
                        "rank": raw_rank,
                        "name": str(row[col_name]).strip() if col_name and pd.notna(row[col_name]) else "Verified Participant",
                        "phone": masked_phone,
                        "ro_code": str(row[col_ro_code]).strip() if col_ro_code and pd.notna(row[col_ro_code]) else "",
                        "ro_name": str(row[col_ro_name]).strip() if col_ro_name and pd.notna(row[col_ro_name]) else "",
                        "sales_area": str(row[col_area]).strip() if col_area and pd.notna(row[col_area]) else "",
                        "bill_no": str(row[col_bill]).strip() if col_bill and pd.notna(row[col_bill]) else ""
                    })
                if parsed:
                    records = parsed
            except Exception:
                records = None

        if not records:
            records = EMBEDDED_WINNERS

        res_df = pd.DataFrame(records)
        grand_winner_df = res_df[res_df["rank"] == 1]
        if grand_winner_df.empty:
            grand_winner = res_df.iloc[0].to_dict()
            runners_up = res_df.iloc[1:20].sort_values(by="rank", ascending=False).to_dict("records")
        else:
            grand_winner = grand_winner_df.iloc[0].to_dict()
            runners_up = (
                res_df[res_df["rank"] != 1]
                .sort_values(by="rank", ascending=False)
                .head(19)
                .to_dict("records")
            )

        return runners_up, grand_winner

    if "reveal_list_done" not in st.session_state:
        st.session_state.reveal_list_done = False
    if "reveal_iphone_done" not in st.session_state:
        st.session_state.reveal_iphone_done = False

    # Header Section
    h_col1, h_col2 = st.columns([1, 5])
    with h_col1:
        if os.path.exists(LOCAL_LOGO_PATH):
            st.image(LOCAL_LOGO_PATH, width=105)
        else:
            st.image(PROD_FALLBACK_URL, width=105)
    with h_col2:
        st.markdown(
            """
            <div class="exec-header-box">
                <div style="font-size: 12px; letter-spacing: 1.2px; text-transform: uppercase; color: #fdba74; font-weight: 700;">
                    IndianOil Kolkata Divisional Office
                </div>
                <h2 style="margin: 4px 0 6px 0; color: #ffffff; font-size: 26px;">
                    Mega Lucky Draw — Official Winners Announcement
                </h2>
                <div style="font-size: 13px; color: #e2e8f0;">
                    20 Verified Winners Selected Across Retail Outlets (19 Smartphone Winners + 1 Grand iPhone Winner)
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    runners_up_list, grand_iphone_winner = load_winners_data(EXCEL_FILE_PATH)

    # STAGE 1: Reveal 20th to 2nd Winners
    if not st.session_state.reveal_list_done:
        st.markdown(
            """
            <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 10px; padding: 36px 24px; text-align: center; margin: 16px 0;">
                <h3 style="color: #02164f; margin-top: 0;">Ready for Official Winner Declaration</h3>
                <p style="color: #475569; font-size: 14px; max-width: 560px; margin: 0 auto 22px auto;">
                    Click below to unveil the 19 Mega Draw Winners starting from Position #20 down to Position #2.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        c1, c2, c3 = st.columns([1.2, 2, 1.2])
        with c2:
            if st.button("REVEAL WINNERS (20th TO 2nd POSITION)", use_container_width=True, key="btn_reveal_20_to_2"):
                progress_bar = st.progress(0, text="Verifying audit records and preparing winner list...")
                for pct in range(0, 101, 20):
                    time.sleep(0.14)
                    progress_bar.progress(pct, text=f"Loading verified winners... {pct}%")
                progress_bar.empty()
                st.session_state.reveal_list_done = True
                st.rerun()

    # Display 20th -> 2nd Winners List
    if st.session_state.reveal_list_done:
        st.markdown(
            """
            <div style="display: flex; justify-content: space-between; align-items: center; margin: 10px 0 14px 0;">
                <h3 style="color: #02164f; margin: 0; font-size: 20px;">Winners List (Position #20 to #2)</h3>
                <span style="font-size: 12px; color: #64748b; font-weight: 600;">Ordered from #20 (Top) to #2 (Bottom)</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        for i, w in enumerate(runners_up_list):
            delay_sec = round(i * 0.04, 2)
            badge_extra_cls = "rank-badge-top3" if w["rank"] in (2, 3) else ""
            ro_detail = f"{w['ro_name']} ({w['ro_code']})" if w["ro_code"] else w["ro_name"]
            area_detail = f" | {w['sales_area']}" if w["sales_area"] else ""
            bill_detail = f" | Bill: {w['bill_no']}" if w["bill_no"] else ""

            st.markdown(
                f"""
                <div class="winner-row-card" style="animation-delay: {delay_sec}s;">
                    <div style="display: flex; align-items: center;">
                        <div class="rank-badge {badge_extra_cls}">Rank #{w['rank']}</div>
                        <div>
                            <div style="font-size: 16px; font-weight: 700; color: #0f172a;">{w['name']}</div>
                            <div style="font-size: 12px; color: #475569; margin-top: 2px;">
                                <b>Outlet:</b> {ro_detail}{area_detail}
                            </div>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 13px; font-weight: 700; color: #02164f;">{w['phone']}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Verified Entry{bill_detail}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown("<hr style='border: 0; border-top: 1px solid #cbd5e1; margin: 28px 0;'>", unsafe_allow_html=True)

        # STAGE 2: Button right after the list to reveal Grand iPhone Winner
        if not st.session_state.reveal_iphone_done:
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 14px;">
                    <div style="font-size: 13px; font-weight: 700; color: #02164f; letter-spacing: 0.6px; text-transform: uppercase;">
                        Grand Finale — First Prize Announcement
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            g1, g2, g3 = st.columns([1.1, 2.2, 1.1])
            with g2:
                if st.button("REVEAL GRAND IPHONE WINNER (1st PRIZE)", use_container_width=True, key="btn_reveal_iphone"):
                    with st.spinner("Unlocking Grand Prize Winner..."):
                        time.sleep(1.1)
                    st.session_state.reveal_iphone_done = True
                    st.rerun()
        else:
            gw = grand_iphone_winner
            gw_ro = f"{gw['ro_name']} ({gw['ro_code']})" if gw["ro_code"] else gw["ro_name"]
            gw_area = gw["sales_area"] if gw["sales_area"] else "Kolkata Divisional Office"
            gw_bill = gw["bill_no"] if gw["bill_no"] else "Verified"

            st.markdown(
                f"""
                <div class="iphone-grand-card">
                    <div style="text-align: center;">
                        <span class="iphone-pill">Grand Prize Winner — Position #1</span>
                        <div style="font-size: 14px; font-weight: 700; color: #f37022; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 6px;">
                            Apple iPhone 17 Pro Max Winner
                        </div>
                        <h1 style="margin: 0 0 8px 0; color: #02164f; font-size: 32px; font-weight: 800;">
                            {gw['name']}
                        </h1>
                        <div style="font-size: 16px; font-weight: 700; color: #334155; margin-bottom: 18px;">
                            Mobile: {gw['phone']} &nbsp;|&nbsp; Invoice No: {gw_bill}
                        </div>
                    </div>
                    <div style="background: #ffffff; border: 1px solid #fed7aa; border-radius: 8px; padding: 14px 20px; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                        <div>
                            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Retail Outlet</div>
                            <div style="font-size: 14px; color: #0f172a; font-weight: 700;">{gw_ro}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700;">Sales Area</div>
                            <div style="font-size: 14px; color: #02164f; font-weight: 700;">{gw_area}</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.write("")
            r1, r2, r3 = st.columns([2, 1, 2])
            with r2:
                if st.button("Reset Reveal", use_container_width=True, key="btn_reset_reveal"):
                    st.session_state.reveal_list_done = False
                    st.session_state.reveal_iphone_done = False
                    st.rerun()

    st.stop()


# ==============================================================================
# MODE 2: ORIGINAL CUSTOMER QR RECEIPT SCAN APP (PRESERVED & HIDDEN)
# ==============================================================================

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

ro_code = st.query_params.get("ro", None)

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

def get_station_details(code: str):
    res = db.table("retail_outlets").select("ro_code, ro_name, district, address, is_active, check_5580").eq("ro_code", str(code).strip()).execute()
    return res.data[0] if res.data else None

station = get_station_details(ro_code)
if not station:
    st.error(f"⚠️ Retail Outlet Code **{ro_code}** not recognized.")
    st.stop()

if not station.get("is_active", True):
    st.markdown(
        f"""
        <div style="
            background-color: #fff1f2;
            border: 3px solid #f37022;
            border-left: 7px solid #f37022;
            border-radius: 10px;
            padding: 22px;
            margin: 20px 0;
            color: #02164f;
            font-family: inherit;
            line-height: 1.6;
            box-shadow: 0 4px 12px rgba(225, 29, 72, 0.08);
        ">
            <div style="text-align: center;">
                <h3 style="margin: 0 0 10px 0; color: #02164f; font-size: 19px;">
                    Thank you for being a part of this campaign. <br> The campaign has ended, and we appreciate your participation.
                </h3>
            </div>
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

if st.session_state.get("pending_dialog") == "WINNER":
    v_data = st.session_state.get("winning_voucher_data", {})
    st.session_state.pending_dialog = None
    show_winner_dialog(
        voucher_id=v_data.get("id"),
        claim_link=v_data.get("claim_link", ""),
        denomination=v_data.get("denomination", 40)
    )

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

        dup_bill = db.table("campaign_entries").select("id").eq("ro_code", ro_code).eq("bill_number", normalized_bill).execute()
        if dup_bill.data:
            st.error("⚠️ This invoice number has already been entered at this outlet.")
            st.stop()

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

        today_ro_scans = db.table("campaign_entries").select("id", count="exact")\
            .eq("ro_code", ro_code)\
            .gte("created_at", today_iso_start)\
            .execute()

        current_scan_number = (today_ro_scans.count or 0) + 1
        is_cadence_winner = (current_scan_number % 10 == 0)

        CAMPAIGN_RULE_START_DATE = date(2026, 11, 10)
        is_rule_active = (date.today() >= CAMPAIGN_RULE_START_DATE)

        current_check_val = station.get("check_5580") or 0
        is_category_a = (current_check_val >= 5580)

        assigned_voucher = None
        is_winner = False

        if is_cadence_winner and not is_category_a:
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
                DAILY_PATTERN = [10, 10, 20, 10, 10, 10, 40, 10, 10, 10, 20, 10, 10]
                winner_index = claimed_today % len(DAILY_PATTERN)
                target_denomination = DAILY_PATTERN[winner_index]

                v_res = db.table("voucher_vault").select("id, denomination, claim_link")\
                    .eq("ro_code", ro_code)\
                    .eq("denomination", target_denomination)\
                    .ilike("status", "available")\
                    .order("uploaded_at", desc=False)\
                    .order("id", desc=False)\
                    .limit(1)\
                    .execute()

                if not v_res.data:
                    v_res = db.table("voucher_vault").select("id, denomination, claim_link")\
                        .is_("ro_code", "null")\
                        .eq("denomination", target_denomination)\
                        .ilike("status", "available")\
                        .order("uploaded_at", desc=False)\
                        .order("id", desc=False)\
                        .limit(1)\
                        .execute()

                if not v_res.data:
                    v_res = db.table("voucher_vault").select("id, denomination, claim_link")\
                        .ilike("status", "available")\
                        .order("uploaded_at", desc=False)\
                        .order("id", desc=False)\
                        .limit(1)\
                        .execute()

                if v_res.data:
                    assigned_voucher = v_res.data[0]
                    won_denom = assigned_voucher.get("denomination", target_denomination)
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

                    if is_rule_active:
                        new_check_val = current_check_val + won_denom
                        db.table("retail_outlets").update({
                            "check_5580": new_check_val
                        }).eq("ro_code", ro_code).execute()

                    st.session_state.pending_dialog = "WINNER"
                    st.session_state.winning_voucher_data = {
                        "id": assigned_voucher["id"],
                        "claim_link": assigned_voucher["claim_link"],
                        "denomination": won_denom
                    }

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