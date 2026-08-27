"""
Bandhan.com — SINGLE-PAGE prototype (Batch 2 of N)
====================================================
Everything in this ONE file. Navigation between views is done purely via
st.session_state — there is no pages/ folder and no st.switch_page(). Because
Streamlit never treats this as a "new page", the sidebar component is never
unmounted/remounted, which is what eliminates the old page-to-page flicker.

Pages ported so far (in the natural user-journey order):
  Batch 1: Home, Registration, Search Partner, My Matches
  Batch 2: Chat & Alerts, Family Meet Scheduler, VIP Membership, Report & Safety
  Batch 3: Wedding Services, Wedding Budget, Wedding Finance, Kundli Match
  Batch 4: Digital Invites, Wedding Countdown Tracker, Vendor Registration, Success Stories
  Batch 5: AI Compatibility Score, AI Icebreaker, Boost Visibility, Referral Program
  Batch 6: Blog & Tips, Daily Horoscope, Second Marriage Support, Post-Marriage Resources
  Batch 7: NRI Visa Assistant, Anniversary & Birthday Reminders, Collaborative Budget Split, Legal & Trust Center
  Batch 8 (FINAL): Company Dashboard, Vendor Booking Dashboard, Vendor Insights, WhatsApp Notifications
All 32 original pages are now ported — this file is a complete 1:1 replacement
for the old multi-page app, with zero page-to-page flicker.
"""

import streamlit as st
import base64
import datetime
import datetime as dt
import time
import io
import random
import urllib.parse
import requests
import pandas as pd
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageSequence

st.set_page_config(page_title="Bandhan | Premium Matrimony & Ecosystem", page_icon="\U0001F48D", layout="wide", initial_sidebar_state="expanded")


# =====================================================================
# BASIC HELPERS
# =====================================================================
def get_base64_image(file_paths):
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    for path in file_paths:
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception:
            continue
    return ""


def render_html(html_string, container=None):
    target = container if container is not None else st
    lines = html_string.split("\n")
    cleaned = "\n".join(line.lstrip() for line in lines)
    target.markdown(cleaned, unsafe_allow_html=True)


MAIN_LOGO_B64 = get_base64_image(["000001.png", "896327.jpg", "903963.png", "896430.png"])


# =====================================================================
# MONGODB — real, persistent storage. Gracefully falls back to
# session-only storage (old behavior) if MONGODB_URI isn't configured
# in Streamlit Secrets yet, so nothing breaks either way.
# =====================================================================
import pymongo
import bcrypt


@st.cache_resource(show_spinner=False)
def get_mongo_client():
    try:
        mongo_uri = st.secrets["MONGODB_URI"]
        client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client
    except Exception:
        return None


def get_db():
    client = get_mongo_client()
    if client is None:
        return None
    return client["bandhan_db"]


def db_is_connected():
    return get_db() is not None


def hash_password(plain_password):
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password, hashed_password):
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception:
        return False


def db_find_user(email):
    db = get_db()
    if db is None:
        return None
    return db.users.find_one({"email": email})


def db_create_user(email, password_hash, role, name):
    db = get_db()
    if db is None:
        return False
    if db.users.find_one({"email": email}):
        return False
    db.users.insert_one({
        "email": email,
        "password_hash": password_hash,
        "role": role,
        "name": name,
        "created_at": dt.datetime.utcnow(),
    })
    return True


def db_record_tnc_acceptance(email, gate_key):
    """Permanent, timestamped legal record that this user accepted the
    Terms & Conditions — this is the real proof-of-consent that session-only
    storage can't provide."""
    db = get_db()
    if db is None:
        return
    db.tnc_acceptances.insert_one({
        "email": email,
        "gate": gate_key,
        "accepted_at": dt.datetime.utcnow(),
    })


# =====================================================================
# DEMO "DATABASE" (session-only fallback — used automatically whenever
# MongoDB isn't configured, so the app keeps working either way)
# =====================================================================
def init_demo_store():
    if "all_users" not in st.session_state:
        st.session_state.all_users = {
            "boss@bandhan.com": {"password": "BossAdmin@2026", "role": "boss", "name": "Admin"},
        }
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_role" not in st.session_state:
        st.session_state.user_role = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None
    if "stay_logged_in" not in st.session_state:
        st.session_state.stay_logged_in = False
    if "current_view" not in st.session_state:
        st.session_state.current_view = "home"


def get_boss_credentials():
    try:
        return st.secrets["BOSS_EMAIL"], st.secrets["BOSS_PASSWORD"]
    except Exception:
        return "boss@bandhan.com", "BossAdmin@2026"


def go_to(view_name):
    """The core of the fix: switch pages WITHOUT Streamlit treating it as a
    real page navigation. Sidebar never remounts because of this."""
    st.session_state.current_view = view_name
    st.rerun()


# =====================================================================
# TERMS & CONDITIONS — full legal text + acceptance gate
# =====================================================================
FULL_TERMS_TEXT = """
**TERMS AND CONDITIONS**
Last Updated: August 2026
Operated By: Firstchoice Innovations (Nagpur, Maharashtra, India)

**1. INTRODUCTION & ACCEPTANCE OF TERMS**
Welcome to the Bandhan ("Bandhan.com") matrimony platform. This website and the accompanying mobile application are owned and operated by Firstchoice Innovations. By accessing, registering, or using our platform, you agree to be bound by these Terms and Conditions. If you do not agree with any part of these terms, you must strictly refrain from using our services.

**2. ELIGIBILITY & STRICT AGE FALSIFICATION CLAUSE**
Minimum Age: To register, a male user must be at least 21 years old, and a female user must be at least 18 years old, as per the laws of India.
Minor Fraud & Liability: If any minor creates an account by falsifying their date of birth or uploading forged government documents, the entire legal liability (including under the POCSO Act) shall fall upon the user and their parents/legal guardians. Firstchoice Innovations shall hold zero liability for such fraudulent misrepresentation.

**3. PAYMENT, SUBSCRIPTION & STRICT NO-REFUND POLICY**
Non-Refundable: All payments made for premium memberships, subscriptions, or in-app purchases are strictly non-refundable. Once a transaction is successful and the plan is activated, no refunds will be issued under any circumstances (including, but not limited to, non-usage of the app, finding a match, or account termination).
Pricing Modifications: The company reserves the right to alter, modify, or increase subscription fees at any time without prior notice.

**4. PROFILE CREATION, CONTENT & ACCOUNT TERMINATION**
Fake Profiles & Ban: Users must provide accurate and truthful information. If a user is found using fake photos, providing false information, or using the platform for malicious intents (spam, extortion), the account will be permanently banned and deleted without any prior notice or refund.
User Content Rights: By uploading photos or personal data, you grant Firstchoice Innovations the right to display this content on the platform. You are solely responsible for any copyright violations associated with the content you upload.

**5. COMPANY'S LIMITATIONS & DISCLAIMER OF WARRANTIES**
No Guarantee of Match: This platform acts purely as a digital bridge to connect individuals. Purchasing a premium plan does not guarantee a successful marriage, engagement, or meeting.
No Background Check Obligation: Firstchoice Innovations does not conduct criminal background checks, police verifications, or authenticate the financial, medical, or marital status of its users. Verification is the sole responsibility of the users and their families.
Off-Platform Meetings: The company holds no liability for any incidents, disputes, fraud, or emotional/physical harm resulting from off-platform communication (phone calls, WhatsApp) or physical meetings between users.

**6. FINANCIAL FRAUD SAFETY DISCLAIMER**
Firstchoice Innovations or its representatives will never call users asking for passwords, OTPs, or direct bank transfers. If a user voluntarily transfers money to another profile under any pretext, the company shall not be held liable for any financial loss or recovery.

**7. TECHNICAL LIMITATIONS, CYBER SECURITY & FORCE MAJEURE**
Limitation of Liability: The company is not liable for any service interruptions due to server downtime, internet issues, or app maintenance.
Data Breach Disclaimer: While we use top-tier security protocols, no digital platform is 100% secure. Firstchoice Innovations cannot be held legally liable for data leaks resulting from massive cyber-attacks or unauthorized hacking.
Force Majeure: The company is completely exempt from liability for service failures caused by events outside its control, including natural disasters, internet shutdowns, or sudden government restrictions.

**8. ANTI-SCRAPING & INTELLECTUAL PROPERTY PROTECTION**
All branding, including the "Bandhan" name, logo, and app design, is the intellectual property of Firstchoice Innovations.
Zero Scraping Policy: Users or third parties are strictly prohibited from using bots, spiders, or scripts to scrape user data (photos, numbers) or reverse-engineer the app. Violators will face immediate criminal prosecution and heavy financial penalties.

**9. COMMUNICATION & 'DO NOT DISTURB' (DND) OVERRIDE**
By registering on Bandhan, you provide explicit consent to receive promotional messages, match alerts, and calls from Firstchoice Innovations via SMS, WhatsApp, and Email. This consent overrides any DND (Do Not Disturb) or NCPR registration on your mobile number.

**10. ANTI-HARASSMENT & ALGORITHM DISCLAIMER**
Zero Tolerance for Harassment: Any user found abusing, stalking, or harassing another user will face an immediate, un-refundable ban.
Matchmaking Algorithm: Recommended matches are auto-generated by software algorithms. The company does not guarantee behavioral compatibility or the absolute accuracy of these algorithmic suggestions.

**11. GOVERNMENT COMPLIANCE & REGULATORY CLAUSES**
Intermediary Safe Harbour (Section 79, IT Act): Bandhan operates strictly as an 'Intermediary' under the Information Technology Act of India. We merely host information provided by users and hold no legal liability for user-generated content.
Mandatory KYC: The company reserves the right to demand Government IDs (Aadhaar/PAN) at any time to verify a profile. Refusal to comply will result in account suspension.
Government Takedown: Upon receiving a lawful order from a court or government agency, the company will remove specific content or profiles within 36 hours without notifying the user.
DPDP Act 2023 Consent: Users explicitly consent to the processing of their digital personal data in accordance with the Digital Personal Data Protection Act of 2023.

**12. DATA RETENTION & LAW ENFORCEMENT COOPERATION**
Firstchoice Innovations fully cooperates with law enforcement. We reserve the right to hand over user data, chats, and IP logs to the police or cyber cell without prior permission from the user in case of suspected criminal activity.
Post-Deletion Retention: Even after a user deletes their account, the company may retain basic data logs for a stipulated period to comply with legal and security obligations.
Inactive Accounts: The company reserves the right to permanently delete accounts that have been inactive for more than 6 to 12 months.

**13. LEGAL PROTECTIONS: INDEMNITY & CLASS ACTION WAIVER**
Indemnification: You agree to defend, indemnify, and hold Firstchoice Innovations harmless from any claims, damages, or legal fees arising due to your misuse of the platform or violation of any laws.
No Class Action: Users agree that any disputes must be brought against the company in their individual capacity. Participation in class-action or group lawsuits against the company is strictly prohibited.

**14. GENERAL LEGAL MASTERSTROKES**
Severability: If any single clause in this document is deemed invalid or unenforceable by a court, all remaining clauses shall continue to remain in full force and effect.
No Waiver: If the company delays in taking action against a user for a rule violation, it does not mean the company has waived its right to take action in the future.
Business Transfer: In the event of a merger, acquisition, or sale of the "Bandhan" software, Firstchoice Innovations reserves the right to transfer all user data to the acquiring entity without requiring fresh consent.

**15. DISPUTE RESOLUTION & GOVERNING LAW**
Arbitration: Any dispute arising out of these terms shall first be resolved through binding arbitration by an independent arbitrator appointed by the company, held in Nagpur.
Exclusive Jurisdiction: These Terms and Conditions shall be governed by the laws of India. Any legal proceedings or court cases shall be subject to the exclusive jurisdiction of the competent courts located in Nagpur, Maharashtra, India.
"""


def render_tnc_gate(gate_key, heading, subtext):
    """Blocks the caller's actual content until the person ticks 'I Agree' to
    the full Terms & Conditions. Returns True once accepted (and lets the
    caller proceed), False if the gate itself was shown (caller should stop).

    If MongoDB is connected, acceptance is also saved permanently with a
    timestamp against the user's email — real legal proof of consent. If not
    connected yet, it falls back to session-only (resets on refresh)."""
    accept_key = f"tnc_accepted_{gate_key}"
    if st.session_state.get(accept_key, False):
        return True

    st.markdown(f"### {heading}")
    st.write(subtext)
    with st.container(border=True):
        st.markdown(FULL_TERMS_TEXT)
    agree = st.checkbox("I have read and agree to the Terms & Conditions above.", key=f"tnc_checkbox_{gate_key}")
    if st.button("\u2705 I Agree & Continue", type="primary", use_container_width=True, key=f"tnc_continue_{gate_key}", disabled=not agree):
        st.session_state[accept_key] = True
        user_email = st.session_state.get("user_email")
        if db_is_connected() and user_email:
            db_record_tnc_acceptance(user_email, gate_key)
        st.rerun()
    if not agree:
        st.caption("\u26A0\uFE0F Please tick the box above to continue.")
    return False


# =====================================================================
# LOGIN / SIGNUP UI
# =====================================================================
def render_login_signup():
    init_demo_store()
    boss_email, boss_password = get_boss_credentials()
    using_real_db = db_is_connected()

    render_html("""
    <div style="text-align:center; margin-bottom:20px;">
        <h2 style="color:#1A365D;">\U0001F510 Login to Bandhan.com</h2>
        <p style="color:gray;">Please log in or create an account to continue.</p>
    </div>
    """)

    if using_real_db:
        st.caption("\u2705 Connected to secure database \u2014 your account persists across sessions.")
    else:
        st.caption("\u26A0\uFE0F Running in demo mode (no database configured yet) \u2014 accounts reset when you refresh.")

    tab_login, tab_signup = st.tabs(["\U0001F511 Login", "\U0001F4DD Create Account"])

    with tab_login:
        if st.button("\U0001F511 Quick-Fill Demo Boss Credentials", use_container_width=True):
            st.session_state["login_email"] = boss_email
            st.session_state["login_password"] = boss_password
            st.rerun()

        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        stay_logged_in_login = st.checkbox("\U0001F4CC Stay permanently logged in (skip 5-min auto-logout)", key="stay_logged_in_login_cb")
        if st.button("Login", type="primary", use_container_width=True):
            email_clean = email.strip().lower()
            password_clean = password.strip()
            boss_email_clean = boss_email.strip().lower()
            boss_password_clean = boss_password.strip()

            if email_clean == boss_email_clean and password_clean == boss_password_clean:
                st.session_state.logged_in = True
                st.session_state.user_role = "boss"
                st.session_state.user_email = email_clean
                st.session_state.user_name = "Admin"
                st.session_state.stay_logged_in = stay_logged_in_login
                st.session_state.current_view = "home"
                st.rerun()
            elif using_real_db:
                user_doc = db_find_user(email_clean)
                if user_doc and verify_password(password_clean, user_doc["password_hash"]):
                    st.session_state.logged_in = True
                    st.session_state.user_role = user_doc["role"]
                    st.session_state.user_email = email_clean
                    st.session_state.user_name = user_doc["name"]
                    st.session_state.stay_logged_in = stay_logged_in_login
                    st.session_state.current_view = "home"
                    st.rerun()
                else:
                    st.error("\u274C Invalid email or password.")
            elif email_clean in st.session_state.all_users and st.session_state.all_users[email_clean]["password"] == password_clean:
                user = st.session_state.all_users[email_clean]
                st.session_state.logged_in = True
                st.session_state.user_role = user["role"]
                st.session_state.user_email = email_clean
                st.session_state.user_name = user["name"]
                st.session_state.stay_logged_in = stay_logged_in_login
                st.session_state.current_view = "home"
                st.rerun()
            else:
                st.error("\u274C Invalid email or password.")

    with tab_signup:
        st.write("Sign up as a **Client** (bride/groom searching for a partner) or a **Vendor** (wedding service provider).")
        su_name = st.text_input("Full Name / Business Name", key="signup_name")
        su_email = st.text_input("Email", key="signup_email")
        su_password = st.text_input("Password", type="password", key="signup_password")
        su_role = st.selectbox("I am registering as a...", ["Client (Bride/Groom)", "Vendor (Service Provider)"])
        role_value = "client" if su_role.startswith("Client") else "vendor"
        stay_logged_in_signup = st.checkbox("\U0001F4CC Stay permanently logged in (skip 5-min auto-logout)", key="stay_logged_in_signup_cb")

        if st.button("Create Account", type="primary", use_container_width=True):
            su_email_clean = su_email.strip().lower()
            su_password_clean = su_password.strip()
            su_name_clean = su_name.strip()

            if not su_name_clean or not su_email_clean or not su_password_clean:
                st.warning("\u26A0\uFE0F Please fill in all fields.")
            elif su_email_clean == boss_email.strip().lower():
                st.error("An account with this email already exists. Please log in instead.")
            elif using_real_db:
                if db_find_user(su_email_clean):
                    st.error("An account with this email already exists. Please log in instead.")
                else:
                    password_hash = hash_password(su_password_clean)
                    created = db_create_user(su_email_clean, password_hash, role_value, su_name_clean)
                    if created:
                        st.session_state.logged_in = True
                        st.session_state.user_role = role_value
                        st.session_state.user_email = su_email_clean
                        st.session_state.user_name = su_name_clean
                        st.session_state.stay_logged_in = stay_logged_in_signup
                        st.session_state.current_view = "home"
                        st.success(f"\u2705 Account created and saved permanently! Welcome, {su_name_clean}.")
                        st.rerun()
                    else:
                        st.error("An account with this email already exists. Please log in instead.")
            elif su_email_clean in st.session_state.all_users:
                st.error("An account with this email already exists. Please log in instead.")
            else:
                st.session_state.all_users[su_email_clean] = {"password": su_password_clean, "role": role_value, "name": su_name_clean}
                st.session_state.logged_in = True
                st.session_state.user_role = role_value
                st.session_state.user_email = su_email_clean
                st.session_state.user_name = su_name_clean
                st.session_state.stay_logged_in = stay_logged_in_signup
                st.session_state.current_view = "home"
                st.success(f"\u2705 Account created! Welcome, {su_name_clean}.")
                st.rerun()

    st.caption("\U0001F512 Demo Boss login — email: `boss@bandhan.com`, password: `BossAdmin@2026`")


def logout():
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.user_email = None
    st.session_state.user_name = None
    st.session_state.stay_logged_in = False
    st.session_state.current_view = "home"
    st.rerun()


def inject_idle_timeout(minutes=5):
    if st.session_state.get("stay_logged_in", False):
        return
    seconds = minutes * 60
    st.components.v1.html(f"""
    <script>
    (function() {{
        var idleSeconds = 0;
        var limit = {seconds};
        function resetIdle() {{ idleSeconds = 0; }}
        ["mousemove", "keydown", "click", "scroll", "touchstart"].forEach(function(evt) {{
            window.parent.document.addEventListener(evt, resetIdle, true);
        }});
        var timer = setInterval(function() {{
            idleSeconds += 1;
            if (idleSeconds >= limit) {{
                clearInterval(timer);
                try {{
                    var url = new URL(window.parent.location.href);
                    url.searchParams.set("force_logout", "1");
                    window.parent.location.href = url.toString();
                }} catch (e) {{}}
            }}
        }}, 1000);
    }})();
    </script>
    """, height=0, width=0)


# =====================================================================
# SIDEBAR — this renders ONCE per script run, and because there is no
# real page navigation happening, it never flashes/rebuilds when the
# person clicks between views.
# =====================================================================
def render_sidebar():
    role = st.session_state.get("user_role")
    user_name = st.session_state.get("user_name", "")
    role_label = {"boss": "\U0001F451 Boss", "client": "\U0001F491 Client", "vendor": "\U0001F9D1\u200d\U0001F4BC Vendor"}.get(role, "")

    render_html(f"""
    <div style="text-align: center; margin-bottom: 15px; border-bottom: 1px solid rgba(212, 175, 55, 0.3); padding-bottom: 15px;">
    <div style="background: rgba(255,255,255,0.96); border-radius: 18px; padding: 14px 10px; display: inline-block; box-shadow: 0 4px 10px rgba(0,0,0,0.2);"><img src="data:image/png;base64,{MAIN_LOGO_B64}" style="max-width: 90%; height: auto;"></div>
    </div>
    """, container=st.sidebar)

    render_html(f"""
    <div style="text-align:center; color:#E2E8F0; margin-bottom:12px; font-size:0.85rem;">
    Logged in as <b>{user_name}</b><br><span style="color:#D4AF37;">{role_label}</span>
    </div>
    """, container=st.sidebar)

    def nav_button(label, icon, view_key):
        active = st.session_state.current_view == view_key
        if st.sidebar.button(f"{icon} {label}", key=f"nav_{view_key}", use_container_width=True, type=("primary" if active else "secondary")):
            go_to(view_key)

    nav_button("Home", "\U0001F3E0", "home")
    nav_button("Registration", "\U0001F4DD", "registration")
    nav_button("Search Partner", "\U0001F50D", "search_partner")
    nav_button("My Matches", "\u2764\uFE0F", "my_matches")
    nav_button("Chat & Alerts", "\U0001F4AC", "chat_alerts")
    nav_button("Family Meet", "\U0001F46A", "family_meet")
    nav_button("VIP Membership", "\U0001F451", "vip_membership")
    nav_button("Report & Safety", "\U0001F6A8", "report_safety")
    nav_button("Wedding Services", "\U0001F6CD\uFE0F", "wedding_services")
    nav_button("Wedding Budget", "\U0001F4B0", "wedding_budget")
    nav_button("Wedding Finance", "\U0001F4B3", "wedding_finance")
    nav_button("Kundli Match", "\U0001F549\uFE0F", "kundli_match")
    nav_button("Digital Invites", "\U0001F48C", "digital_invites")
    nav_button("Wedding Countdown", "\u23F3", "wedding_countdown")
    nav_button("Vendor Registration", "\U0001F9D1\u200d\U0001F4BC", "vendor_registration")
    nav_button("Success Stories", "\U0001F496", "success_stories")
    nav_button("AI Compatibility", "\U0001F9E0", "ai_compatibility")
    nav_button("AI Icebreaker", "\U0001F9CA", "ai_icebreaker")
    nav_button("Boost Visibility", "\U0001F680", "boost_visibility")
    nav_button("Refer & Earn", "\U0001F381", "referral_program")
    nav_button("Blog & Tips", "\U0001F4DD", "blog_tips")
    nav_button("Daily Horoscope", "\U0001F52E", "daily_horoscope")
    nav_button("Second Marriage Support", "\U0001F91D", "second_marriage")
    nav_button("Post-Marriage Resources", "\U0001F495", "post_marriage")
    nav_button("NRI Visa Assistant", "\u2708\uFE0F", "nri_visa")
    nav_button("Anniversary & Birthday", "\U0001F382", "anniversary_birthday")
    nav_button("Budget Split", "\U0001F91D", "budget_split")
    nav_button("Legal & Trust Center", "\u2696\uFE0F", "legal_pages")

    if role in ("boss", "vendor"):
        st.sidebar.markdown("<div class='nav-group-label' style='color:#D4AF37; font-weight:800; margin-top:16px;'>\U0001F451 Boss / Vendor Tools</div>", unsafe_allow_html=True)
        nav_button("Vendor Booking Dashboard", "\U0001F4C5", "vendor_bookings")
        nav_button("Vendor Insights", "\U0001F4C8", "vendor_insights")
    if role == "boss":
        nav_button("Company Dashboard", "\U0001F4CA", "company_dashboard")
        nav_button("WhatsApp Notifications", "\U0001F4AC", "whatsapp_notifications")

    st.sidebar.caption("\u2705 All 32 pages are now ported into this single file.")

    if st.sidebar.button("\U0001F6AA Logout", use_container_width=True):
        logout()


# =====================================================================
# SHARED CSS
# =====================================================================
def render_global_css(bg_color, page_css=""):
    render_html(f"""
    <style>
    [data-testid="stSidebarNav"] {{ display: none !important; }}
    .stApp {{ background-color: {bg_color} !important; font-family: 'Helvetica Neue', sans-serif; }}
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #0F2027 0%, #203A43 50%, #2C5364 100%) !important;
        border-right: 3px solid #D4AF37 !important;
    }}
    [data-testid="stSidebar"] * {{ color: #E2E8F0; }}
    [data-testid="stSidebar"] div.stButton > button {{
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(212,175,55,0.25) !important;
        color: #E2E8F0 !important;
        text-align: left !important;
        justify-content: flex-start !important;
    }}
    [data-testid="stSidebar"] div.stButton > button[kind="primary"] {{
        background: linear-gradient(90deg, #D4AF37, #AA771C) !important;
        color: #0F2027 !important;
        font-weight: 800 !important;
        border: 1px solid #FBF5B7 !important;
    }}
    div.stButton > button, div.stFormSubmitButton > button {{
        transition: box-shadow 0.25s ease, transform 0.2s ease, border-color 0.25s ease !important;
    }}
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {{
        border-color: #9F7AEA !important;
        cursor: pointer;
        animation: premiumHoverPulse 1s ease-in-out infinite !important;
    }}
    @keyframes premiumHoverPulse {{
        0%, 100% {{ box-shadow: 0 0 0 3px rgba(107,70,193,0.5), 0 6px 18px rgba(107,70,193,0.4); transform: translateY(-2px) scale(1.02); }}
        50% {{ box-shadow: 0 0 0 6px rgba(159,122,234,0.3), 0 10px 26px rgba(107,70,193,0.65); transform: translateY(-2px) scale(1.045); }}
    }}
    {page_css}
    </style>
    """)


def require_login_and_role(allowed_roles):
    init_demo_store()

    if st.query_params.get("force_logout") == "1":
        st.session_state.logged_in = False
        st.session_state.user_role = None
        st.session_state.user_email = None
        st.session_state.user_name = None
        st.session_state.stay_logged_in = False
        st.query_params.clear()

    if not st.session_state.logged_in:
        return False

    if st.session_state.user_role not in allowed_roles:
        st.error(f"\U0001F6AB Your account ({st.session_state.user_role}) doesn't have permission to view this page.")
        return False

    inject_idle_timeout(minutes=5)
    return True


# =====================================================================
# PAGE: HOME
# =====================================================================
def page_home():
    render_global_css(bg_color="#FAFAFA", page_css="""
    h1 { color: #0F2027; font-weight: 700; letter-spacing: 1px; }
    .feature-box { background-color: white; padding: 25px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); text-align: center; border-bottom: 4px solid #D4AF37; transition: transform 0.3s ease; cursor: pointer; }
    .feature-box:hover { transform: translateY(-5px); box-shadow: 0 14px 34px rgba(0,0,0,0.12); }
    .tagline { font-size: 1.5rem; color: #555555; font-weight: 300; line-height: 1.6; }
    .ecosystem-heading { text-align:center; font-size: 2.6rem; font-weight: 900; letter-spacing: 1px; padding: 18px 30px; border-radius: 16px; display:inline-block; background: linear-gradient(90deg, #FF416C, #FF4B2B, #D4AF37, #1A365D, #2C5364); background-size: 300% 300%; animation: gradientShift 6s ease infinite; color: white; text-shadow: 0 2px 6px rgba(0,0,0,0.25); }
    @keyframes gradientShift { 0% {background-position:0% 50%;} 50% {background-position:100% 50%;} 100% {background-position:0% 50%;} }
    div.stButton > button[kind="primary"] { background: linear-gradient(90deg, #FF416C, #FF4B2B, #D4AF37, #FF416C) !important; background-size: 300% 300% !important; animation: gradientShift 3s ease infinite, pulseGlow 1.8s ease-in-out infinite !important; border-radius: 18px !important; padding: 26px 18px !important; box-shadow: 0 12px 30px rgba(255,65,108,0.5) !important; border: none !important; color: white !important; font-size: 1.4rem !important; font-weight: 900 !important; letter-spacing: 0.5px !important; }
    div.stButton > button[kind="primary"]:hover { transform: translateY(-3px) scale(1.02); box-shadow: 0 18px 38px rgba(255,65,108,0.6) !important; color: white !important; }
    @keyframes pulseGlow { 0%,100% { box-shadow: 0 12px 30px rgba(255,65,108,0.5); } 50% { box-shadow: 0 12px 40px rgba(212,175,55,0.7); } }
    div.stButton > button[kind="secondary"] { background: linear-gradient(135deg, #FFF8E7, #FFFFFF) !important; border: 3px solid #D4AF37 !important; border-top: none !important; border-radius: 0 0 15px 15px !important; margin-top: -10px !important; padding: 14px 10px !important; font-weight: 800 !important; font-size: 1.05rem !important; color: #1A365D !important; box-shadow: 0 8px 20px rgba(212,175,55,0.25) !important; }
    div.stButton > button[kind="secondary"]:hover { background: linear-gradient(135deg, #D4AF37, #AA771C) !important; color: white !important; transform: translateY(-2px); }
    """)

    role_label = {"boss": "\U0001F451 Boss", "client": "\U0001F491 Client"}.get(st.session_state.get("user_role"), "")
    render_html(f"""
    <div style="text-align:center; margin-bottom:8px;">
    <span style="background:#1A365D; color:#D4AF37; padding:6px 18px; border-radius:20px; font-weight:700; font-size:0.9rem;">{role_label}</span>
    </div>
    """)
    render_html(f"""
    <div style="text-align:center; margin-bottom:6px;">
    <div style="background: rgba(255,255,255,0.96); border-radius: 18px; padding: 16px 12px; display: inline-block; box-shadow: 0 6px 16px rgba(0,0,0,0.15);"><img src="data:image/png;base64,{MAIN_LOGO_B64}" style="max-width: 230px; height: auto;"></div>
    </div>
    """)

    col1, col2 = st.columns([1.2, 1], gap="large")
    with col1:
        st.markdown("<br>", unsafe_allow_html=True)
        st.title(f"Welcome back, {st.session_state.get('user_name', '')} \U0001F48D")
        st.markdown(
            '<p class="tagline"><b>Traditional Roots, Modern Approach.</b><br>'
            "The world's first AI-powered matrimonial platform and complete wedding ecosystem. <br>"
            "From finding the perfect life partner to wedding venues and honeymoons—everything in one place."
            "</p>",
            unsafe_allow_html=True,
        )
        if st.button("\u2728 Create Your Premium Profile (Free)", key="cta_profile", type="primary", use_container_width=True):
            go_to("registration")
    with col2:
        st.image("https://images.unsplash.com/photo-1511285560929-80b456fea0bc?auto=format&fit=crop&w=800&q=80", caption="The Perfect Match Awaits", use_container_width=True)

    st.markdown("<hr style='border: 1px solid #EAEAEA;'>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center;'><span class='ecosystem-heading'>The Bandhan Ecosystem</span></div><br>", unsafe_allow_html=True)

    f_col1, f_col2, f_col3 = st.columns(3, gap="medium")
    with f_col1:
        st.image("https://images.unsplash.com/photo-1573164713988-8665fc963095?auto=format&fit=crop&w=500&q=80", use_container_width=True)
        st.markdown("<div class='feature-box'><h3 style='color:#D4AF37;'>\U0001F916 AI Matchmaking (Our Services)</h3><p>Our smart AI technology analyzes your personality, preferences, and habits to suggest the most accurate and highly compatible matches.</p></div>", unsafe_allow_html=True)
        if st.button("\U0001F916 View My Matches", key="cta_matches", type="secondary", use_container_width=True):
            go_to("my_matches")
    with f_col2:
        st.image("https://images.unsplash.com/photo-1519225421980-715cb0215aed?auto=format&fit=crop&w=500&q=80", use_container_width=True)
        st.markdown("<div class='feature-box'><h3 style='color:#D4AF37;'>\U0001F6CD\uFE0F Complete Ecosystem</h3><p style='font-weight:700; color:#1A365D; margin:2px 0 10px 0;'>Our Wedding Services</p><p>Designer bridal wear, luxury cars, banquet halls, and premium catering. Our verified vendors cover every single wedding need.</p></div>", unsafe_allow_html=True)
        if st.button("\U0001F6CD\uFE0F Explore Wedding Services", key="cta_wedding", type="secondary", use_container_width=True):
            go_to("wedding_services")
    with f_col3:
        st.image("https://images.unsplash.com/photo-1520854221256-17451cc331bf?auto=format&fit=crop&w=500&q=80", use_container_width=True)
        st.markdown("<div class='feature-box'><h3 style='color:#D4AF37;'>\U0001F512 100% Secure</h3><p>Strict Identity Verification. Your personal information and photos are completely secure, giving you full control over your privacy.</p></div>", unsafe_allow_html=True)
        if st.button("\U0001F6E1\uFE0F Trust & Safety Center", key="cta_trust", type="secondary", use_container_width=True):
            go_to("report_safety")

    st.markdown("<br><br><div style='text-align: center; color: #888888; padding: 20px;'><p>Bandhan.com © 2026 | Matrimony • Planning • Vendors • Honeymoon</p></div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: REGISTRATION (all 6 tabs, exactly as before)
# =====================================================================
INDIAN_CITIES = [
    "Any City", "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Ahmedabad", "Chennai", "Kolkata", "Surat", "Pune",
    "Jaipur", "Lucknow", "Kanpur", "Nagpur", "Indore", "Thane", "Bhopal", "Visakhapatnam", "Pimpri-Chinchwad",
    "Patna", "Vadodara", "Ghaziabad", "Ludhiana", "Agra", "Nashik", "Faridabad", "Meerut", "Rajkot", "Kalyan-Dombivli",
    "Vasai-Virar", "Varanasi", "Srinagar", "Aurangabad", "Dhanbad", "Amritsar", "Navi Mumbai", "Allahabad (Prayagraj)",
    "Ranchi", "Howrah", "Coimbatore", "Jabalpur", "Gwalior", "Vijayawada", "Jodhpur", "Madurai", "Raipur", "Kota",
    "Guwahati", "Chandigarh", "Solapur", "Hubli-Dharwad", "Bareilly", "Moradabad", "Mysore", "Gurugram", "Aligarh",
    "Jalandhar", "Bhubaneswar", "Salem", "Warangal", "Guntur", "Bhiwandi", "Saharanpur", "Gorakhpur", "Bikaner",
    "Amravati", "Noida", "Jamshedpur", "Bhilai", "Cuttack", "Firozabad", "Kochi", "Nellore", "Bhavnagar", "Dehradun",
    "Durgapur", "Asansol", "Rourkela", "Nanded", "Kolhapur", "Ajmer", "Akola", "Gulbarga", "Jamnagar", "Ujjain",
    "Loni", "Siliguri", "Jhansi", "Ulhasnagar", "Jammu", "Sangli-Miraj", "Mangalore", "Erode", "Belgaum", "Kurnool",
    "Rajahmundry", "Tirunelveli", "Malegaon", "Gaya", "Udaipur", "Maheshtala", "Panaji", "Shimla", "Thiruvananthapuram",
    "Other",
]
DEPARTMENT_OPTIONS = [
    "Select...", "IT / Software", "Banking & Finance", "Government / PSU", "Healthcare / Medical",
    "Education / Academics", "Engineering", "Sales & Marketing", "Legal", "HR / Administration",
    "Defence / Police", "Railways", "Media / Communications", "Hospitality", "Other"
]
BUSINESS_TYPE_OPTIONS = [
    "Select...", "Manufacturing", "Trading / Wholesale", "Retail Shop", "Real Estate", "Construction",
    "Textile", "Agriculture / Farming", "Restaurant / Food Business", "Transport / Logistics",
    "Consulting", "IT / Tech Startup", "Other"
]
MOTHER_TONGUE_OPTIONS = [
    "Select...", "Hindi", "Marathi", "Gujarati", "Punjabi", "Bengali", "Tamil", "Telugu", "Kannada",
    "Malayalam", "Odia", "Assamese", "Urdu", "Sindhi", "Kashmiri", "Konkani", "Bhojpuri", "Rajasthani",
    "Maithili", "Haryanvi", "Chhattisgarhi", "English", "Other"
]


def occupation_block(label_prefix, key_prefix):
    occ_type = st.selectbox(f"{label_prefix} Occupation Type", ["Select...", "Service", "Business", "Retired", "Homemaker", "Not Working"], key=f"{key_prefix}_occ_type")
    department = ""
    post = ""
    business_type = ""
    if occ_type == "Service":
        department = st.selectbox(f"{label_prefix} Department", DEPARTMENT_OPTIONS, key=f"{key_prefix}_dept")
        post = st.text_input(f"{label_prefix} Post / Designation", key=f"{key_prefix}_post", placeholder="e.g., Senior Manager")
    elif occ_type == "Business":
        business_type = st.selectbox(f"{label_prefix} Business Type", BUSINESS_TYPE_OPTIONS, key=f"{key_prefix}_biz")
    return occ_type, department, post, business_type


def compress_uploaded_image(uploaded_file, quality=88):
    try:
        original_bytes = uploaded_file.getvalue()
        original_kb = len(original_bytes) / 1024
        img = Image.open(io.BytesIO(original_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        compressed_bytes = buffer.getvalue()
        compressed_kb = len(compressed_bytes) / 1024
        return compressed_bytes, original_kb, compressed_kb, img
    except Exception:
        return None, None, None, None


def page_registration():
    render_global_css(bg_color="#FDFDFD", page_css=""".premium-header { color: #0F2027; font-family: 'Trebuchet MS', sans-serif; font-size: 2.4rem; font-weight: 800; margin-bottom: 0px; }
.highlight-gold { color: #D4AF37; }
.sub-text { font-size: 1.05rem; color: #666666; margin-bottom: 20px; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; flex-wrap: wrap; }
.stTabs [data-baseweb="tab"] { height: 48px; background: linear-gradient(135deg, #F1F5F9, #E2E8F0); border-radius: 10px 10px 0 0; padding: 8px 16px; font-weight: 800; font-size: 0.92rem; border: 2px solid transparent; transition: all 0.25s ease; }
.stTabs [data-baseweb="tab"]:hover { background: linear-gradient(135deg, #E2E8F0, #D4AF37); }
.stTabs [aria-selected="true"] { background: linear-gradient(90deg, #FF416C, #FF4B2B, #D4AF37, #1A365D, #2C5364) !important; background-size: 300% 300%; animation: gradientShift 5s ease infinite; border: 2px solid #D4AF37 !important; box-shadow: 0 4px 14px rgba(212,175,55,0.45); }
.stTabs [aria-selected="true"] p { color: white !important; font-weight: 900 !important; }
@keyframes gradientShift { 0% {background-position:0% 50%;} 50% {background-position:100% 50%;} 100% {background-position:0% 50%;} }
.trust-badge { background-color: #E3F2FD; color: #1976D2; padding: 12px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 1.05rem; }
.step-tag { background: #E2E8F0; color: #1A365D; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 700; margin-right: 6px; }
.premium-badge { background-color: #D4AF37; color: white; padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; }
.trust-badge-card { background: white; padding: 20px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border-top: 4px solid #D4AF37; text-align: center; transition: transform 0.25s ease; }
.trust-badge-card.active-badge { border-top: 6px solid #D4AF37; box-shadow: 0 10px 26px rgba(212,175,55,0.4); transform: scale(1.04); }
.next-step-box { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 30px; border-radius: 18px; text-align: center; margin-top: 20px; }
.trust-score-circle { width: 160px; height: 160px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.15); }
.next-cta-wrap div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #D4AF37, #FFF3C4, #D4AF37) !important;
    background-size: 200% 200% !important;
    border: 2px solid #AA771C !important; color: #4A3600 !important; font-weight: 900 !important;
    border-radius: 50px !important; padding: 16px 10px !important; font-size: 1.05rem !important;
    animation: ctaShimmer 2.4s ease infinite, ctaPulse 1.8s ease-in-out infinite !important;
}
@keyframes ctaShimmer { 0% {background-position:0% 50%;} 50% {background-position:100% 50%;} 100% {background-position:0% 50%;} }
@keyframes ctaPulse { 0%,100% { transform:scale(1); box-shadow:0 4px 14px rgba(212,175,55,0.4); } 50% { transform:scale(1.03); box-shadow:0 8px 26px rgba(212,175,55,0.75); } }
""")

    st.markdown("<h1 class='premium-header'>Create Your <span class='highlight-gold'>Premium Profile</span></h1>", unsafe_allow_html=True)

    if not render_tnc_gate("registration", "\U0001F4C4 Please Accept Our Terms & Conditions First", "Before creating your profile, please read and accept our Terms & Conditions. Registration cannot proceed until you agree."):
        return

    st.markdown("<p class='sub-text'>Everything you need to get started — personal details, verification, privacy, and family settings — all in one place.</p>", unsafe_allow_html=True)
    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "\U0001F464 Personal Details", "\U0001F3AF Preferences",
        "\U0001F6E1\uFE0F KYC Verification", "\U0001F9CD Liveness Check", "\U0001F512 Privacy Settings",
        "\U0001F46A Family Assisted & Trust"
    ])

    with tab1:
        st.markdown("### **Basic Information**")
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("First Name")
            email = st.text_input("Email Address")
            gender = st.selectbox("Gender", ["Select...", "Male", "Female", "Other"])
        with col2:
            last_name = st.text_input("Last Name")
            phone = st.text_input("Phone Number")
            dob = st.date_input("Date of Birth", value=datetime.date(2000, 1, 1), min_value=datetime.date(1970, 1, 1), max_value=datetime.date(2008, 1, 1))

        hw_col1, hw_col2 = st.columns(2)
        with hw_col1:
            height_cm = st.number_input("Height (in cm)", min_value=120, max_value=220, value=165, step=1)
        with hw_col2:
            weight_kg = st.number_input("Weight (in kg)", min_value=30, max_value=200, value=60, step=1)

        st.markdown("### **Profile Photos**")
        st.caption("Upload up to 2 clear profile photos. We'll process them for a crisp, Full HD display quality.")
        photo_col1, photo_col2 = st.columns(2)
        with photo_col1:
            profile_photo_1 = st.file_uploader("Profile Photo 1", type=["jpg", "jpeg", "png"], key="profile_photo_1")
            if profile_photo_1:
                preview_bytes, _, _, _ = compress_uploaded_image(profile_photo_1, quality=95)
                if preview_bytes:
                    st.image(preview_bytes, caption="Photo 1 preview", use_container_width=True)
        with photo_col2:
            profile_photo_2 = st.file_uploader("Profile Photo 2", type=["jpg", "jpeg", "png"], key="profile_photo_2")
            if profile_photo_2:
                preview_bytes2, _, _, _ = compress_uploaded_image(profile_photo_2, quality=95)
                if preview_bytes2:
                    st.image(preview_bytes2, caption="Photo 2 preview", use_container_width=True)

        st.markdown("### **Background & Profession**")
        col3, col4 = st.columns(2)
        with col3:
            religion = st.selectbox("Religion", ["Select...", "Hindu", "Muslim", "Sikh", "Christian", "Jain", "Other"])
            custom_religion = ""
            if religion == "Other":
                custom_religion = st.text_input("Please specify your Religion / Caste", key="custom_religion_input")
                if st.button("\U0001F4BE Save Religion / Caste", key="save_religion_btn"):
                    if custom_religion.strip():
                        st.session_state.saved_custom_religion = custom_religion.strip()
                        st.success(f"\u2705 Saved: {custom_religion.strip()}")
                    else:
                        st.warning("Please enter a value before saving.")

            education = st.selectbox("Highest Education", ["Select...", "Bachelors", "Masters", "Doctorate", "Other"])
            custom_education = ""
            if education == "Other":
                custom_education = st.text_input("Please specify your Education", key="custom_education_input")
                if st.button("\U0001F4BE Save Education", key="save_education_btn"):
                    if custom_education.strip():
                        st.session_state.saved_custom_education = custom_education.strip()
                        st.success(f"\u2705 Saved: {custom_education.strip()}")
                    else:
                        st.warning("Please enter a value before saving.")
        with col4:
            income = st.selectbox("Annual Income", ["Select...", "Below \u20b93 Lakh", "\u20b93 Lakh - \u20b96 Lakh", "\u20b96 Lakh - \u20b910 Lakh", "\u20b910 Lakh - \u20b920 Lakh", "\u20b920 Lakh - \u20b950 Lakh", "Above \u20b950 Lakh"])
            mother_tongue = st.selectbox("Mother Tongue", MOTHER_TONGUE_OPTIONS)
            custom_mother_tongue = ""
            if mother_tongue == "Other":
                custom_mother_tongue = st.text_input("Please specify your Mother Tongue", key="custom_mt_input")

        st.markdown("### **Your Occupation**")
        my_occ_type, my_department, my_post, my_business_type = occupation_block("Your", "self")

        st.markdown("### **Family Background**")
        fam_col1, fam_col2 = st.columns(2)
        with fam_col1:
            st.markdown("##### \U0001F468 Father's Occupation")
            father_occ_type, father_department, father_post, father_business_type = occupation_block("Father's", "father")
        with fam_col2:
            st.markdown("##### \U0001F469 Mother's Occupation")
            mother_occ_type, mother_department, mother_post, mother_business_type = occupation_block("Mother's", "mother")

        sib_col1, sib_col2, sib_col3 = st.columns(3)
        with sib_col1:
            num_brothers = st.number_input("Number of Brothers", min_value=0, max_value=15, value=0, step=1)
        with sib_col2:
            num_sisters = st.number_input("Number of Sisters", min_value=0, max_value=15, value=0, step=1)
        with sib_col3:
            marital_status = st.selectbox("Marital Status", ["Select...", "Never Married", "Divorced", "Widowed", "Separated"])

        lives_with_family = st.radio("Do you currently live with your family?", ["Yes", "No"], horizontal=True)

    with tab2:
        st.markdown("### **What are you looking for?**")
        ai_match = st.toggle("\U0001F916 Enable AI Smart Match (Recommended)", value=True)
        pref_col1, pref_col2 = st.columns(2)
        with pref_col1:
            age_range = st.slider("Preferred Age Range", 21, 60, (25, 30))
            pref_gender = st.selectbox("Looking for", ["Select...", "Male", "Female", "Other"])
        with pref_col2:
            min_height = st.slider("Minimum Height (in cm)", 140, 210, 150)
            pref_lifestyle = st.selectbox("Partner's Lifestyle Preference", ["No Preference", "Homemaker", "Working Professional"])
        st.markdown("### **Location Preference**")
        pref_city = st.selectbox("Preferred City", INDIAN_CITIES)

    with tab3:
        st.markdown("<div class='trust-badge'>Get the Verified Blue Tick \u2705 & Trust Badge to increase your profile visibility by 300%</div><br>", unsafe_allow_html=True)
        st.markdown("### Step 1: Upload Government ID")
        id_type = st.selectbox("Select ID Type", ["Aadhaar Card", "PAN Card", "Passport", "Driving License"])
        id_number = st.text_input(f"Enter {id_type} Number", placeholder="Enter ID number securely")
        id_file = st.file_uploader(f"Upload Front Side of {id_type}", type=['jpg', 'png', 'jpeg'])
        if id_file is not None:
            compressed_bytes, original_kb, compressed_kb, preview_img = compress_uploaded_image(id_file)
            if compressed_bytes:
                st.session_state.kyc_id_compressed = compressed_bytes
                saved_pct = round((1 - (compressed_kb / original_kb)) * 100, 1) if original_kb else 0
                st.success(f"\U0001F5DC\uFE0F Document auto-compressed for faster upload — {original_kb:.0f} KB \u2192 {compressed_kb:.0f} KB (\u2212{saved_pct}%), quality preserved.")
                st.image(preview_img, caption="Compressed preview (same visual quality)", width=260)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### Step 2: Live AI Face Match")
        st.info("\U0001F4F7 Please capture a live photo to match with your provided ID.")
        kyc_photo = st.camera_input("Take a selfie for KYC")
        if st.button("\U0001F680 Submit for AI & Trust Verification", type="primary", use_container_width=True, key="kyc_submit"):
            if id_number and kyc_photo:
                with st.spinner("AI is scanning your ID and matching facial features securely..."):
                    time.sleep(2)
                st.session_state.kyc_verified = True
                st.success("\u2705 Verification Successful! Your face matches the ID.")
            else:
                st.warning("\u26A0\uFE0F Please provide your ID details and take a selfie to proceed.")

    with tab4:
        st.markdown("### Guided Liveness Actions")
        st.write("Follow the on-screen prompts during your live capture. This prevents use of photos, videos, or AI-generated deepfake images.")
        actions = ["Blink twice", "Turn head slightly left", "Turn head slightly right", "Smile naturally"]
        chips = "".join(f"<span class='step-tag'>\u2713 {a}</span>" for a in actions)
        st.markdown(chips, unsafe_allow_html=True)
        st.markdown("<br><br>", unsafe_allow_html=True)
        live_photo = st.camera_input("Follow the prompts and capture your live photo")
        st.markdown("### AI Deepfake Analysis")
        st.write("Our model checks for signs of synthetic generation, screen-replay artifacts, and photo-of-a-photo patterns.")
        if st.button("\U0001F50D Run Liveness & Deepfake Check", type="primary", use_container_width=True, key="liveness_submit"):
            if live_photo:
                with st.spinner("Analyzing facial motion, texture, and lighting consistency..."):
                    time.sleep(2)
                st.success("\u2705 Liveness Confirmed. No signs of deepfake or spoofing detected.")
            else:
                st.warning("\u26A0\uFE0F Please capture a live photo first.")

    with tab5:
        col1, col2 = st.columns([1.5, 1])
        with col1:
            st.markdown("### \U0001F4F8 Photo Visibility Settings")
            photo_setting = st.radio("Who can see your profile photos?", ["Everyone (Recommended)", "Only Premium Members", "Only Members I Accept (Blur for others)"])
            if photo_setting == "Only Members I Accept (Blur for others)":
                st.warning("Your photos will appear blurred to all users until you accept their request.")
            st.markdown("### \U0001F6E1\uFE0F Anti-Screenshot Protection <span class='premium-badge'>PLATINUM</span>", unsafe_allow_html=True)
            screenshot_block = st.toggle("Block Screenshots (Requires Platinum Plan)")
            if screenshot_block:
                st.success("Screenshot protection is actively monitoring your profile.")
        with col2:
            st.markdown("### \U0001F4DE Contact Info Privacy")
            contact_setting = st.selectbox("Phone Number Visibility", ["Hide Completely", "Show to Accepted Matches", "Show to Premium Members"])
            st.markdown("### \U0001F575\uFE0F Incognito Mode")
            incognito = st.toggle("Browse profiles silently (They won't know you visited)")

    with tab6:
        st.markdown("### Who is creating this profile?")
        managed_by = st.radio("This profile is being managed by:", ["Myself", "My Parent / Guardian", "My Sibling / Relative"])
        if managed_by != "Myself":
            st.markdown("### Family Contact Details")
            c1, c2 = st.columns(2)
            with c1:
                relation = st.selectbox("Relationship to the Candidate", ["Father", "Mother", "Brother", "Sister", "Other Relative"])
                family_name = st.text_input("Your Full Name", key="family_name")
            with c2:
                family_phone = st.text_input("Your Contact Number", key="family_phone")
                family_email = st.text_input("Your Email Address", key="family_email")
            notify_family = st.checkbox("Send match notifications and updates to family contact as well", value=True)
            family_approval = st.checkbox("Require family approval before accepting any 'Interest'")
        else:
            st.info("This profile will be managed independently. You can add a family contact anytime.")

        st.markdown("---")
        st.markdown("### \U0001F3C6 Family Trust Score")
        st.write("Your family's trust score is calculated automatically based on how complete your profile is and your current subscription plan.")
        subscription_plan = st.selectbox("Your Current Subscription Plan", ["No Active Subscription", "Half-Yearly Package", "1-Year Subscription"], key="subscription_plan_select")

        required_fields_filled = [
            bool(first_name.strip()) if first_name else False,
            bool(last_name.strip()) if last_name else False,
            bool(email.strip()) if email else False,
            bool(phone.strip()) if phone else False,
            gender != "Select...",
            religion != "Select..." and (religion != "Other" or bool(custom_religion.strip())),
            education != "Select..." and (education != "Other" or bool(custom_education.strip())),
            income != "Select...",
        ]
        completeness_fraction = sum(required_fields_filled) / len(required_fields_filled)
        is_profile_complete = completeness_fraction == 1.0

        if subscription_plan == "1-Year Subscription" and is_profile_complete:
            trust_score = 100
            trust_label = "\U0001F48E Legacy Family"
            trust_color = "#1A365D"
            badge_note = "Complete profile — maximum trust unlocked."
        elif subscription_plan == "Half-Yearly Package":
            trust_score = int(75 + completeness_fraction * 5)
            trust_label = "\U0001F947 Highly Trusted Family"
            trust_color = "#D4AF37"
            badge_note = "Your profile has earned a strong trust boost."
        else:
            trust_score = int(50 + completeness_fraction * 10)
            trust_label = "\U0001F949 Basic Trust (AI Estimated)"
            trust_color = "#64748B"
            badge_note = "Complete your profile to raise your trust score."

        tc1, tc2 = st.columns([1, 1.6])
        with tc1:
            render_html(f"""
            <div class="trust-score-circle" style="background: linear-gradient(135deg, {trust_color}, #FDFDFD); border: 4px solid {trust_color};">
                <div style="font-size:2.2rem; font-weight:900; color:{trust_color};">{trust_score}%</div>
                <div style="font-size:0.75rem; color:#555; font-weight:700;">TRUST SCORE</div>
            </div>
            """)
        with tc2:
            st.markdown(f"#### {trust_label}")
            st.write(badge_note)
            st.progress(trust_score / 100)
            if not is_profile_complete:
                missing_count = len(required_fields_filled) - sum(required_fields_filled)
                st.caption(f"\u2139\uFE0F {missing_count} field(s) still incomplete in Personal Details.")

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"<div class='trust-badge-card{' active-badge' if trust_label.endswith('Basic Trust (AI Estimated)') else ''}'><h2 style='color:#D4AF37;'>\U0001F949</h2><h4>Basic Trust</h4><p style='color:gray; font-size:0.85rem;'>AI-estimated, 50\u201360%</p></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='trust-badge-card{' active-badge' if trust_label.endswith('Highly Trusted Family') else ''}'><h2 style='color:#D4AF37;'>\U0001F947</h2><h4>Highly Trusted</h4><p style='color:gray; font-size:0.85rem;'>Strong profile trust, 75\u201380%</p></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='trust-badge-card{' active-badge' if trust_label.endswith('Legacy Family') else ''}'><h2 style='color:#D4AF37;'>\U0001F48E</h2><h4>Legacy Family</h4><p style='color:gray; font-size:0.85rem;'>Complete profile, maximum trust, 100%</p></div>", unsafe_allow_html=True)

        st.markdown("---")
        submit = st.button("Complete Registration & Enter Ecosystem", type="primary", use_container_width=True, key="final_submit_btn")

        if submit:
            if not first_name:
                st.error("Please enter your First Name in the Personal Details tab.")
            else:
                st.success(f"\U0001F389 Registration Successful, {first_name}! Welcome to the Bandhan Premium Ecosystem.")
                st.balloons()
                render_html("""
                <div class="next-step-box">
                    <h3 style="color:#D4AF37; margin-top:0;">\u2728 What's next? Start planning your big day!</h3>
                </div>
                """)
                cta_col1, cta_col2 = st.columns(2)
                st.markdown("<div class='next-cta-wrap'>", unsafe_allow_html=True)
                with cta_col1:
                    if st.button("\U0001F4B3 Explore Wedding Finance", key="cta_finance", type="primary", use_container_width=True):
                        go_to("wedding_finance")
                with cta_col2:
                    if st.button("\U0001F6CD\uFE0F Explore Wedding Services", key="cta_services", type="primary", use_container_width=True):
                        go_to("wedding_services")
                st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: SEARCH PARTNER
# =====================================================================
INDIAN_CITIES_SEARCH = INDIAN_CITIES[:-1]  # same list minus the trailing "Other"


def page_search_partner():
    render_global_css(bg_color="#F8F9FA", page_css=""".search-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 35px; border-radius: 15px; color: white; text-align: center; border-bottom: 5px solid #D4AF37; margin-bottom: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.15); }
.search-title { font-family: 'Georgia', serif; font-size: 2.8rem; font-weight: 900; margin: 0; background: linear-gradient(to right, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.filter-card { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; }
.profile-result-card { background: white; padding: 20px; border-radius: 12px; margin-top: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 6px solid #27AE60; border-top: 1px solid #EAEAEA; border-right: 1px solid #EAEAEA; border-bottom: 1px solid #EAEAEA; }
.result-photo { width: 100%; border-radius: 10px; height: 150px; object-fit: cover; }
.result-photo-blurred { filter: blur(10px); }
.tier-badge-gold { background: #D4AF37; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.72rem; font-weight: 800; }
.tier-badge-platinum { background: linear-gradient(90deg, #6D6D6D, #C0C0C0, #6D6D6D); color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.72rem; font-weight: 800; }""")

    st.markdown("""
    <div class="search-header">
        <h1 class="search-title">Search Partner</h1>
        <p style="font-size:1.1rem; margin-top:10px; color:#FBF5B7; font-style:italic;">Filter through thousands of verified profiles to find your perfect life partner.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='filter-card'>", unsafe_allow_html=True)
    st.markdown("<h3>\U0001F3AF Set Your Partner Preferences</h3><br>", unsafe_allow_html=True)

    looking_for = st.radio("I am searching for a...", ["Bride", "Groom"], horizontal=True)
    st.markdown("<br>", unsafe_allow_html=True)

    f_col1, f_col2 = st.columns(2, gap="large")
    with f_col1:
        age_range = st.slider("Select Age Range (Years)", 18, 60, (21, 28))
        religion = st.selectbox("Religion", ["Any", "Hindu", "Muslim", "Sikh", "Christian", "Jain", "Buddhist", "Other"])
        custom_religion = ""
        if religion == "Other":
            custom_religion = st.text_input("Please specify Religion / Caste", key="search_custom_religion")
        profession = st.selectbox("Profession / Occupation", ["Any", "Software Engineer", "Doctor", "Business Owner", "Chartered Accountant", "Civil Servant", "Banker", "Teacher", "Other"])
        custom_profession = ""
        if profession == "Other":
            custom_profession = st.text_input("Please specify Profession", key="search_custom_profession")
        education = st.selectbox("Minimum Education", ["Any", "10th Pass", "12th Pass", "Diploma", "Graduate", "Post Graduate", "B.Tech / B.E.", "MBA / PG", "MBBS / MD", "Doctorate"])
    with f_col2:
        city = st.selectbox("Preferred City / Location", INDIAN_CITIES_SEARCH)
        income = st.selectbox("Annual Income", ["Any", "\u20b93 Lakh - \u20b95 Lakh", "\u20b95 Lakh - \u20b910 Lakh", "\u20b910 Lakh - \u20b920 Lakh", "\u20b920 Lakh - \u20b950 Lakh", "\u20b950 Lakh+"])
        manglik = st.selectbox("Kundli / Manglik Preference", ["Doesn't Matter", "Non-Manglik", "Manglik"])
        marital_status = st.selectbox("Marital Status", ["Any", "Unmarried", "Divorced", "Widowed"])

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("\U0001F50D Search Matching Profiles", type="primary", use_container_width=True):
        with st.spinner("Searching verified database based on your filters..."):
            time.sleep(1.5)
        st.success(f"\u2728 Found 42 verified {looking_for.lower()} profiles matching your exact preferences!")

        membership_tier = st.session_state.get("membership_tier", "free")
        if membership_tier == "free":
            st.caption("\U0001F512 Photos are blurred and contact numbers are hidden for free members. Upgrade to Gold or Platinum to unlock more.")
        elif membership_tier in ("silver", "gold"):
            st.caption("\U0001F947 Gold member: photos unlocked. Upgrade to Platinum to also unlock contact numbers.")
        elif membership_tier == "platinum":
            st.caption("\U0001F48E Platinum member: full access to photos and contact numbers.")

        results = [
            {"name": "Ritu Deshmukh", "age": 24, "city": "Nagpur", "match": 96, "border": "#27AE60",
             "profession": "Software Engineer", "education": "B.Tech", "income": "\u20b912 Lakhs p.a.",
             "religion": "Hindu (Non-Manglik)", "verified": "Verified ID (Aadhaar)", "active": "Active 2 hours ago",
             "photo": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=400&q=80",
             "phone": "+91 98450 12345"},
            {"name": "Sneha Patil", "age": 26, "city": "Pune", "match": 92, "border": "#1A365D",
             "profession": "Chartered Accountant", "education": "CA / M.Com", "income": "\u20b915 Lakhs p.a.",
             "religion": "Hindu", "verified": "Verified ID (PAN Card)", "active": "Active Online Now",
             "photo": "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?auto=format&fit=crop&w=400&q=80",
             "phone": "+91 99230 67890"},
        ]

        for idx, r in enumerate(results, start=1):
            photo_col, info_col = st.columns([1, 3])
            with photo_col:
                blur_class = "" if membership_tier in ("silver", "gold", "platinum") else " result-photo-blurred"
                st.markdown(f"<img src='{r['photo']}' class='result-photo{blur_class}'>", unsafe_allow_html=True)
                if membership_tier == "platinum":
                    st.markdown("<span class='tier-badge-platinum'>\U0001F48E Platinum View</span>", unsafe_allow_html=True)
                elif membership_tier in ("silver", "gold"):
                    st.markdown("<span class='tier-badge-gold'>\U0001F947 Gold View</span>", unsafe_allow_html=True)
                else:
                    st.caption("\U0001F512 Locked")
            with info_col:
                st.markdown(f"""
                <div class="profile-result-card" style="border-left-color: {r['border']}; margin-top:0;">
                    <h3 style="color:#1A365D; margin-top:0;">{idx}. {r['name']} ({r['age']} yrs, {r['city']}) \u2B50 {r['match']}% Match</h3>
                    <p><b>Profession:</b> {r['profession']} | <b>Education:</b> {r['education']} | <b>Income:</b> {r['income']} | <b>Religion:</b> {r['religion']}</p>
                    <p style="color:gray; font-size:0.9rem;">{r['verified']} \u2022 {r['active']}</p>
                </div>
                """, unsafe_allow_html=True)
                if membership_tier == "platinum":
                    st.markdown(f"<div style='background:#F0FFF4; border:1px solid #27AE60; border-radius:8px; padding:6px 12px; display:inline-block;'>\U0001F4DE <b>{r['phone']}</b></div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='background:#F8F9FA; border:1px dashed #AAAAAA; border-radius:8px; padding:6px 12px; display:inline-block; color:gray;'>\U0001F512 +91 XXXXX XXXXX \u2014 <i>Platinum only</i></div>", unsafe_allow_html=True)

            b1, b2, b3 = st.columns(3)
            b1.button("\U0001F46A Family Meet", key=f"fmeet_{r['name']}", use_container_width=True)
            b2.button("\U0001F4DE Contact", key=f"contact_{r['name']}", use_container_width=True)
            b3.button("\U0001F49B Meet", key=f"meet_{r['name']}", use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: MY MATCHES
# =====================================================================
def page_my_matches():
    render_global_css(bg_color="#F8F9FA", page_css=""".reco-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.match-card { background: white; border-radius: 14px; padding: 20px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 18px; }
.score-ring { font-size: 1.8rem; font-weight: 900; color: #27AE60; }
.trait-chip { display: inline-block; background: #E2E8F0; color: #1A365D; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; margin: 3px; font-weight: 600; }
.activity-card { background: white; padding: 18px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #D4AF37; margin-bottom: 12px; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; flex-wrap: wrap; }
.stTabs [data-baseweb="tab"] { height: 48px; background: linear-gradient(135deg, #F1F5F9, #E2E8F0); border-radius: 10px 10px 0 0; padding: 8px 16px; font-weight: 800; font-size: 0.95rem; border: 2px solid transparent; transition: all 0.25s ease; }
.stTabs [aria-selected="true"] { background: linear-gradient(90deg, #FF416C, #FF4B2B, #D4AF37, #1A365D, #2C5364) !important; background-size: 300% 300%; animation: gradientShift 5s ease infinite; border: 2px solid #D4AF37 !important; box-shadow: 0 4px 14px rgba(212,175,55,0.45); }
.stTabs [aria-selected="true"] p { color: white !important; font-weight: 900 !important; }
@keyframes gradientShift { 0% {background-position:0% 50%;} 50% {background-position:100% 50%;} 100% {background-position:0% 50%;} }
.match-photo { width: 100%; border-radius: 12px; margin-bottom: 10px; object-fit: cover; height: 180px; }
.match-photo-blurred { filter: blur(10px); }
.paid-badge { background: #D4AF37; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 800; }
.upgrade-blink-wrap div.stButton > button {
    background: linear-gradient(135deg, #D4AF37, #FFF3C4, #D4AF37) !important;
    background-size: 200% 200% !important;
    border: 2px solid #AA771C !important; color: #4A3600 !important; font-weight: 900 !important;
    animation: ctaShimmer 2.4s ease infinite, ctaPulse 1.8s ease-in-out infinite !important;
}
@keyframes ctaShimmer { 0% {background-position:0% 50%;} 50% {background-position:100% 50%;} 100% {background-position:0% 50%;} }
@keyframes ctaPulse { 0%,100% { transform:scale(1); box-shadow:0 4px 14px rgba(212,175,55,0.4); } 50% { transform:scale(1.03); box-shadow:0 8px 26px rgba(212,175,55,0.75); } }""")

    st.markdown("""
    <div class="reco-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\u2728 My Matches</h1>
        <p style="color:#FBF5B7; margin-top:8px;">AI-curated matches based on your preferences, activity, and compatibility signals — updated daily.</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["\U0001F49E Today's Matches", "\U0001F441\uFE0F Who Viewed / Shortlisted You"])
    is_paid_member = st.session_state.get("is_paid_member", False)

    with tab1:
        sort_by = st.selectbox("Sort matches by", ["Highest Compatibility", "Most Recently Active", "Newest Profiles"])
        if not is_paid_member:
            st.caption("\U0001F512 Photos are blurred for free members. Upgrade to VIP to see full-quality photos of your matches.")
        st.markdown("<br>", unsafe_allow_html=True)

        matches = [
            {"name": "Ritu Deshmukh", "age": 24, "city": "Nagpur", "profession": "Software Engineer", "score": 96,
             "traits": ["Same Religion", "Similar Values", "Career-focused", "Non-Manglik match"],
             "photo": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=400&q=80"},
            {"name": "Sneha Patil", "age": 26, "city": "Pune", "profession": "Chartered Accountant", "score": 92,
             "traits": ["Education match", "Family values align", "Active user"],
             "photo": "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?auto=format&fit=crop&w=400&q=80"},
            {"name": "Ananya Rao", "age": 25, "city": "Bangalore", "profession": "Doctor", "score": 89,
             "traits": ["Common interests", "Income bracket match", "Verified profile"],
             "photo": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=400&q=80"},
            {"name": "Kavya Iyer", "age": 27, "city": "Hyderabad", "profession": "Banker", "score": 85,
             "traits": ["Similar lifestyle", "Same city preference", "KYC Verified"],
             "photo": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=400&q=80"},
        ]
        for m in matches:
            st.markdown("<div class='match-card'>", unsafe_allow_html=True)
            photo_col, c1, c2 = st.columns([0.9, 2.4, 0.8])
            with photo_col:
                blur_class = "" if is_paid_member else " match-photo-blurred"
                st.markdown(f"<img src='{m['photo']}' class='match-photo{blur_class}'>", unsafe_allow_html=True)
                if is_paid_member:
                    st.markdown("<span class='paid-badge'>\U0001F48E VIP View</span>", unsafe_allow_html=True)
                else:
                    st.caption("\U0001F512 Upgrade to unblur")
            with c1:
                st.markdown(f"<h3 style='margin:0; color:#1A365D;'>{m['name']} ({m['age']} yrs, {m['city']})</h3>", unsafe_allow_html=True)
                st.markdown(f"<p style='color:gray; margin:4px 0;'>{m['profession']}</p>", unsafe_allow_html=True)
                chips = "".join(f"<span class='trait-chip'>{t}</span>" for t in m['traits'])
                st.markdown(f"<div style='margin-top:8px;'>{chips}</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='score-ring' style='text-align:center;'>{m['score']}%</div><p style='text-align:center; color:gray; font-size:0.85rem;'>Compatibility</p>", unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            if b1.button("\U0001F49B Send Interest", key=f"int_{m['name']}", use_container_width=True):
                st.toast("\U0001F49B Someone showed interest in your profile!")
            b2.button("\U0001F4AC Message", key=f"msg_{m['name']}", use_container_width=True)
            b3.button("\u274C Not Interested", key=f"skip_{m['name']}", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("### \U0001F441\uFE0F Recent Profile Activity")
        activity = [
            ("Priya Sharma", "viewed your profile", "2 hours ago", "view"),
            ("Aisha Khan", "shortlisted you", "5 hours ago", "shortlist"),
            (None, "Someone showed interest in your profile", "1 day ago", "interest"),
            ("Neha Verma", "viewed your profile", "2 days ago", "view"),
        ]
        for name, action, when, kind in activity:
            if kind == "interest":
                display_text = action
            elif is_paid_member:
                display_text = f"<b style='color:#1A365D;'>{name}</b> {action}"
            else:
                display_text = "Someone viewed your profile"

            st.markdown(f"""
            <div class="activity-card">
                {display_text}
                <span style="float:right; color:gray; font-size:0.85rem;">{when}</span>
            </div>
            """, unsafe_allow_html=True)

            if kind != "interest" and name:
                if is_paid_member:
                    if st.button(f"\U0001F464 View {name}'s Profile", key=f"viewprofile_{name}_{when}", use_container_width=True):
                        go_to("my_matches")
                else:
                    st.caption("\U0001F512 If you want to see who viewed your profile, please upgrade.")
                    st.markdown("<div class='upgrade-blink-wrap'>", unsafe_allow_html=True)
                    if st.button("\U0001F451 Upgrade Now", key=f"upgrade_{name}_{when}", use_container_width=True):
                        go_to("vip_membership")
                    st.markdown("</div>", unsafe_allow_html=True)

        if not is_paid_member:
            st.info("\U0001F48E Upgrade to any VIP plan to see exactly who viewed your profile and visit their profile directly.")


# =====================================================================
# PAGE: CHAT & ALERTS
# =====================================================================
def page_chat_alerts():
    render_global_css(bg_color="#F8F9FA", page_css=""".tool-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); padding: 30px; border-radius: 15px; color: white; text-align: center; border-bottom: 5px solid #D4AF37; margin-bottom: 25px; }
.section-card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 25px; }
.status-dot { height: 12px; width: 12px; background-color: #27AE60; border-radius: 50%; display: inline-block; margin-right: 8px; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; flex-wrap: wrap; }
.stTabs [data-baseweb="tab"] { height: 48px; background: linear-gradient(135deg, #F1F5F9, #E2E8F0); border-radius: 10px 10px 0 0; padding: 8px 16px; font-weight: 800; font-size: 0.95rem; border: 2px solid transparent; transition: all 0.25s ease; }
.stTabs [aria-selected="true"] { background: linear-gradient(90deg, #FF416C, #FF4B2B, #D4AF37, #1A365D, #2C5364) !important; background-size: 300% 300%; animation: gradientShift 5s ease infinite; border: 2px solid #D4AF37 !important; box-shadow: 0 4px 14px rgba(212,175,55,0.45); }
.stTabs [aria-selected="true"] p { color: white !important; font-weight: 900 !important; }
@keyframes gradientShift { 0% {background-position:0% 50%;} 50% {background-position:100% 50%;} 100% {background-position:0% 50%;} }
.vip-blink-wrap div.stButton > button {
    background: linear-gradient(135deg, #FFD700, #FFF9C4, #FFD700) !important;
    background-size: 200% 200% !important;
    border: 2px solid #C9A200 !important; color: #4A3600 !important; font-weight: 900 !important;
    animation: ctaShimmer 2.4s ease infinite, ctaPulse 1.8s ease-in-out infinite !important;
}
@keyframes ctaShimmer { 0% {background-position:0% 50%;} 50% {background-position:100% 50%;} 100% {background-position:0% 50%;} }
@keyframes ctaPulse { 0%,100% { transform:scale(1); box-shadow:0 4px 14px rgba(255,215,0,0.4); } 50% { transform:scale(1.03); box-shadow:0 8px 26px rgba(255,215,0,0.8); } }""")

    if 'unread_msgs' not in st.session_state:
        st.session_state.unread_msgs = 0
    else:
        st.session_state.unread_msgs = 0

    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("""
        <div class="tool-header">
            <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F4AC Chat & Alerts</h1>
            <p style="font-size:1.1rem; margin-top:10px; color:#E3F2FD;">Chat safely with your verified matches and receive instant WhatsApp & Match updates.</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("\U0001F514 Simulate New Message", type="primary", use_container_width=True):
            st.session_state.unread_msgs += 1
            st.toast("\u0928\u092f\u093e \u092e\u0948\u0938\u0947\u091c \u0906\u092f\u093e \u0939\u0948!")
            st.rerun()

    tab_chat, tab_alerts = st.tabs(["\U0001F4AC Secure In-App Messages", "\U0001F514 Match & WhatsApp Alerts"])

    with tab_chat:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        chat_col1, chat_col2 = st.columns([1, 3], gap="medium")

        with chat_col1:
            st.markdown("### \U0001F4AC Conversations")
            st.markdown("---")
            contact = st.radio("Select a Match:", ["Priya Sharma (98% Match)", "Aisha Khan (94% Match)", "Bandhan Premium Support"])
            contact_name = contact.split(" (")[0]

        with chat_col2:
            st.markdown(f"<h2 style='color:#1A365D; margin-top:0;'>{contact_name}</h2>", unsafe_allow_html=True)
            st.markdown("<div><span class='status-dot'></span><span style='color:gray;'>Online Now & Verified</span></div>", unsafe_allow_html=True)

            is_paid_member = st.session_state.get("is_paid_member", False)
            if "Support" not in contact_name:
                if is_paid_member:
                    st.markdown(f"<div style='margin-top:8px; background:#F0FFF4; border:1px solid #27AE60; border-radius:8px; padding:8px 14px; display:inline-block;'>\U0001F4DE <b>+91 98{abs(hash(contact_name)) % 100000:05d} {abs(hash(contact_name)) % 90000 + 10000}</b> <span style='color:#27AE60; font-size:0.8rem;'>(VIP unlocked)</span></div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='margin-top:8px; background:#F8F9FA; border:1px dashed #AAAAAA; border-radius:8px; padding:8px 14px; display:inline-block; color:gray;'>\U0001F512 +91 XXXXX XXXXX — <i>Upgrade to any VIP plan to view phone numbers</i></div>", unsafe_allow_html=True)
                    st.markdown("<div class='vip-blink-wrap'>", unsafe_allow_html=True)
                    if st.button("\U0001F451 View VIP Plans", key=f"viewvip_{contact_name}"):
                        go_to("vip_membership")
                    st.markdown("</div>", unsafe_allow_html=True)

            family_meet_key = f"family_meet_{contact_name}"
            if family_meet_key not in st.session_state:
                st.session_state[family_meet_key] = "none"

            with st.expander("\U0001F46A Family Meet Request (optional)"):
                if not is_paid_member:
                    st.warning("\U0001F512 Family Meet Requests are available to paid members only.")
                    st.markdown("<div class='vip-blink-wrap'>", unsafe_allow_html=True)
                    if st.button("\U0001F451 Upgrade to Unlock Family Meet", key=f"upgrade_fm_{contact_name}"):
                        go_to("vip_membership")
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    status = st.session_state[family_meet_key]
                    if "Support" in contact_name:
                        st.caption("Family meet requests aren't applicable for Support.")
                    elif status == "none":
                        st.write(f"Want both families to meet? Send {contact_name}'s family a request — they can accept or decline.")
                        if st.button(f"\U0001F46A Send Family Meet Request to {contact_name}", key=f"send_fm_{contact_name}"):
                            st.session_state[family_meet_key] = "pending"
                            st.rerun()
                    elif status == "pending":
                        st.info(f"\u23F3 Family meet request sent to {contact_name}'s family. Waiting for their response.")
                        st.caption("Demo: simulate their family's response below.")
                        sc1, sc2 = st.columns(2)
                        if sc1.button("\u2705 (Demo) They Accept", key=f"acc_fm_{contact_name}"):
                            st.session_state[family_meet_key] = "accepted"
                            st.rerun()
                        if sc2.button("\u274C (Demo) They Decline", key=f"dec_fm_{contact_name}"):
                            st.session_state[family_meet_key] = "declined"
                            st.rerun()
                    elif status == "accepted":
                        st.success(f"\u2705 {contact_name}'s family accepted your meet request!")
                        if st.button("\U0001F4C5 Schedule the Family Meet", key=f"sched_fm_{contact_name}"):
                            go_to("family_meet")
                    elif status == "declined":
                        st.warning(f"{contact_name}'s family declined the meet request for now. You can try again later.")
                        if st.button("\U0001F501 Send New Request", key=f"retry_fm_{contact_name}"):
                            st.session_state[family_meet_key] = "pending"
                            st.rerun()

            st.markdown("---")

            chat_key = f"chat_{contact_name}"
            if chat_key not in st.session_state:
                if "Support" in contact_name:
                    st.session_state[chat_key] = [{"role": "assistant", "content": "Hello! How can I assist you today?"}]
                else:
                    st.session_state[chat_key] = [{"role": "assistant", "content": "Hi there! I saw we have a high AI compatibility score."}]

            for message in st.session_state[chat_key]:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input(f"Message {contact_name}..."):
                st.session_state[chat_key].append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    message_placeholder.markdown("*(typing...)*")
                    time.sleep(1.2)
                    reply = "That sounds wonderful! Shall we connect on a quick call this weekend?" if "Support" not in contact_name else "A manager will call you shortly."
                    message_placeholder.markdown(reply)
                st.session_state[chat_key].append({"role": "assistant", "content": reply})
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_alerts:
        st.markdown("<div class='section-card'><h3>\U0001F514 Notifications</h3><p>Your alerts will appear here.</p></div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: FAMILY MEET SCHEDULER
# =====================================================================
def page_family_meet():
    render_global_css(bg_color="#F8F9FA", page_css=""".meet-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.meet-card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 20px; }
.topic-chip { display: inline-block; background: #E2E8F0; color: #1A365D; padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; margin: 4px; font-weight: 600; }""")

    st.markdown("""
    <div class="meet-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F46A Virtual Family Video Meet Schedule</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Invite up to 4 people from each side to a video call, with automatic reminders for everyone.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='meet-card'>", unsafe_allow_html=True)
    st.markdown("### Schedule a Family Video Meet")

    logged_in_name = st.session_state.get("user_name", "")
    render_html(f"""
    <div style="background:#F0F4F8; border-left:4px solid #D4AF37; border-radius:8px; padding:10px 16px; margin-bottom:16px;">
        <span style="color:gray; font-size:0.85rem;">Scheduling as</span><br>
        <b style="color:#1A365D; font-size:1.1rem;">{logged_in_name}</b>
    </div>
    """)

    d1, d2, d3 = st.columns(3)
    with d1:
        meet_date = st.date_input("Preferred Date")
    with d2:
        meet_time = st.time_input("Preferred Time")
    with d3:
        ampm_override = st.selectbox("AM / PM", ["Auto (from time above)", "AM", "PM"])

    time_str = meet_time.strftime("%I:%M %p")
    if ampm_override != "Auto (from time above)":
        time_str = meet_time.strftime("%I:%M") + f" {ampm_override}"

    reminder_lead = st.selectbox("Send advance reminder to all invitees", ["1 hour before", "3 hours before", "6 hours before", "1 day before", "2 days before"], index=3)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### \U0001F464 Add Up to 4 Invitees from Each Side")
    st.caption("Every person added here will receive a video call invitation and the advance reminder you selected above.")

    bride_col, groom_col = st.columns(2)
    with bride_col:
        st.markdown("##### \U0001F470 Bride's Side (max 4)")
        bride_contacts = []
        for i in range(1, 5):
            bc1, bc2 = st.columns(2)
            b_name = bc1.text_input(f"Name {i}", key=f"bride_name_{i}", placeholder="Full Name")
            b_contact = bc2.text_input(f"Phone / Email {i}", key=f"bride_contact_{i}", placeholder="+91... or email")
            if b_name and b_contact:
                bride_contacts.append({"name": b_name, "contact": b_contact})
    with groom_col:
        st.markdown("##### \U0001F935 Groom's Side (max 4)")
        groom_contacts = []
        for i in range(1, 5):
            gc1, gc2 = st.columns(2)
            g_name = gc1.text_input(f"Name {i}", key=f"groom_name_{i}", placeholder="Full Name")
            g_contact = gc2.text_input(f"Phone / Email {i}", key=f"groom_contact_{i}", placeholder="+91... or email")
            if g_name and g_contact:
                groom_contacts.append({"name": g_name, "contact": g_contact})

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("\U0001F4C5 Send Video Meet Invitations", type="primary", use_container_width=True):
        if not bride_contacts or not groom_contacts:
            st.warning("Please add at least one contact from each side (up to 4 each) before sending invitations.")
        else:
            total_invited = len(bride_contacts) + len(groom_contacts)
            st.success(f"\u2705 Video meet scheduled by {logged_in_name} for {meet_date} at {time_str}.")
            st.success(f"\U0001F4E9 Invitations sent to all {total_invited} invitees ({len(bride_contacts)} from Bride's side, {len(groom_contacts)} from Groom's side).")
            st.info(f"\u23F0 An advance reminder will be sent to everyone {reminder_lead} the video call.")
            st.markdown("**Invited:**")
            for c in bride_contacts:
                st.write(f"\U0001F470 {c['name']} \u2014 {c['contact']}")
            for c in groom_contacts:
                st.write(f"\U0001F935 {c['name']} \u2014 {c['contact']}")
            st.caption("\U0001F4F9 The video call will start automatically for all invitees at the scheduled time.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='meet-card'>", unsafe_allow_html=True)
    st.markdown("### \U0001F4AC AI-Suggested Conversation Topics")
    st.write("Helpful, non-awkward topics to guide the first family conversation:")
    topics = ["Family traditions & festivals", "How the couple met", "Career & future plans",
              "Living arrangements post-marriage", "Shared hobbies", "Wedding timeline preferences"]
    chips = "".join(f"<span class='topic-chip'>{t}</span>" for t in topics)
    st.markdown(chips, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.info("\U0001F4F9 Actual video calling requires a real-time video integration (e.g. Twilio/Agora) — this page currently handles scheduling and prep only.")


# =====================================================================
# PAGE: VIP MEMBERSHIP
# =====================================================================
def page_vip_membership():
    render_global_css(bg_color="#F8F9FA", page_css=""".vip-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 40px; border-radius: 20px; color: white; text-align: center; border: 2px solid #D4AF37; box-shadow: 0 15px 35px rgba(0,0,0,0.2); margin-bottom: 30px; }
.vip-title { font-family: 'Georgia', serif; font-size: 3rem; font-weight: 900; margin: 0; background: linear-gradient(to right, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.plan-card { background: white; border-radius: 15px; padding: 30px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border: 1px solid #EAEAEA; border-top: 6px solid #D4AF37; transition: transform 0.3s ease; margin-bottom: 20px; }
.plan-card:hover { transform: translateY(-8px); box-shadow: 0 15px 30px rgba(212, 175, 55, 0.25); }
.price-tag { font-size: 2.5rem; color: #27AE60; font-weight: 900; margin: 15px 0; }""")

    st.markdown("""
    <div class="vip-header">
        <h1 class="vip-title">Bandhan VIP & Premium Memberships</h1>
        <p style="font-size:1.2rem; margin-top:15px; color:#FBF5B7; font-style:italic;">Upgrade your account to unlock direct phone numbers, unlimited secure chats, verified badges, and priority matching.</p>
    </div>
    """, unsafe_allow_html=True)

    if not render_tnc_gate("payment", "\U0001F4C4 Please Accept Our Terms & Conditions to Continue", "Before choosing or purchasing any subscription plan (3-month, 6-month, or 1-year), please read and accept our Terms & Conditions — especially Section 3 (Payment & No-Refund Policy)."):
        return

    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        st.markdown("""
        <div class="plan-card">
            <h3>\U0001F949 Silver</h3>
            <p style="color:gray;">Essential features for quick matching</p>
            <div class="price-tag">\u20b9 499</div>
            <p style="font-size:0.9rem; color:#555;">Valid for 3 Months</p>
            <hr>
            <p style="text-align:left;">
            \u2705 View 50 Verified Phone Numbers<br>
            \u2705 Send 100 Direct Messages<br>
            \u2705 Basic Profile Trust Badge<br>
            \u274C Dedicated Relationship Manager
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Choose Silver Plan", key="p1", use_container_width=True):
            st.session_state.is_paid_member = True
            st.session_state.membership_tier = "silver"
            st.success("\U0001F389 Silver VIP Selected! Redirecting to secure payment gateway...")

    with col2:
        st.markdown("""
        <div class="plan-card" style="border-top: 6px solid #1A365D;">
            <h3>\U0001F947 Gold (Most Popular)</h3>
            <p style="color:gray;">Best value for serious matchmaking</p>
            <div class="price-tag">\u20b9 1,499</div>
            <p style="font-size:0.9rem; color:#555;">Valid for 6 Months</p>
            <hr>
            <p style="text-align:left;">
            \u2705 Unlimited Phone Numbers & Calls<br>
            \u2705 Unlimited Direct Live Chat<br>
            \u2705 Gold Verified Trust Badge<br>
            \u2705 Profile Highlight in Search Results
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Choose Gold Plan", key="p2", type="primary", use_container_width=True):
            st.session_state.is_paid_member = True
            st.session_state.membership_tier = "gold"
            st.balloons()
            st.success("\U0001F389 Gold VIP Selected! Premium benefits unlocked successfully.")

    with col3:
        st.markdown("""
        <div class="plan-card" style="border-top: 6px solid #E74C3C;">
            <h3>\U0001F48E Platinum (VIP)</h3>
            <p style="color:gray;">Personalized matchmaking & luxury service</p>
            <div class="price-tag">\u20b9 2,499</div>
            <p style="font-size:0.9rem; color:#555;">Valid for 1 Year</p>
            <hr>
            <p style="text-align:left;">
            \u2705 Dedicated Relationship Manager<br>
            \u2705 Hand-picked Verified Matches<br>
            \u2705 Complete Privacy Shield<br>
            \u2705 Wedding Planning Assistance
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Choose Platinum Plan", key="p3", use_container_width=True):
            st.session_state.is_paid_member = True
            st.session_state.membership_tier = "platinum"
            st.success("\U0001F389 Platinum VIP Selected! Our senior relationship manager will contact you shortly.")


# =====================================================================
# PAGE: REPORT & SAFETY
# =====================================================================
def page_report_safety():
    render_global_css(bg_color="#F8F9FA", page_css=""".safety-header { background: linear-gradient(135deg, #7B1113 0%, #1A365D 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.safety-card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; }
.blocked-item { background: #FFF5F5; border-left: 4px solid #E53E3E; padding: 12px 15px; border-radius: 8px; margin-bottom: 10px; }""")

    st.markdown("""
    <div class="safety-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F6A8 Report & Safety Center</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Your safety matters. Report suspicious profiles and manage your blocked list.</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["\U0001F6A9 Report a Profile", "\U0001F6AB Blocked Profiles", "\U0001F916 Fake Profile Detection"])

    with tab1:
        st.markdown("<div class='safety-card'>", unsafe_allow_html=True)
        st.markdown("### Report Suspicious or Inappropriate Behaviour")
        profile_name = st.text_input("Profile Name / ID to Report")
        reason = st.selectbox("Reason for Report", [
            "Fake / Misleading Profile", "Inappropriate Photos", "Harassment or Abusive Messages",
            "Asking for Money", "Already Married / Undisclosed Relationship", "Spam or Solicitation", "Other"
        ])
        details = st.text_area("Additional Details (optional)")
        also_block = st.checkbox("Also block this profile from contacting me")
        if st.button("\U0001F6A9 Submit Report", type="primary", use_container_width=True):
            if profile_name:
                st.success(f"\u2705 Report submitted against **{profile_name}**. Our Trust & Safety team will review within 24 hours." + (" Profile has also been blocked." if also_block else ""))
            else:
                st.warning("Please enter the profile name or ID.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("<div class='safety-card'>", unsafe_allow_html=True)
        st.markdown("### Your Blocked Profiles")
        blocked = ["Unknown_User_4521", "Suspicious_Profile_882"]
        if blocked:
            for b in blocked:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"<div class='blocked-item'>\U0001F6AB {b}</div>", unsafe_allow_html=True)
                c2.button("Unblock", key=f"unblock_{b}")
        else:
            st.info("You haven't blocked any profiles yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.markdown("<div class='safety-card'>", unsafe_allow_html=True)
        st.markdown("### \U0001F916 AI Fake Profile Detection")
        st.write("Our AI continuously scans profiles for signs of fraud — stolen photos, inconsistent details, and suspicious activity patterns.")
        st.markdown("<br>", unsafe_allow_html=True)
        flagged = [
            {"id": "#BND-9021", "reason": "Reverse image search match found on stock photo site", "risk": "High"},
            {"id": "#BND-9187", "reason": "Multiple accounts from same device ID", "risk": "Medium"},
        ]
        for f in flagged:
            color = "#E53E3E" if f["risk"] == "High" else "#D4AF37"
            st.markdown(f"""
            <div style="background:white; border-left:5px solid {color}; padding:15px; border-radius:8px; margin-bottom:10px; box-shadow:0 4px 10px rgba(0,0,0,0.05);">
                <b>{f['id']}</b> — Risk: <span style="color:{color}; font-weight:bold;">{f['risk']}</span><br>
                <span style="color:gray; font-size:0.9rem;">{f['reason']}</span>
            </div>
            """, unsafe_allow_html=True)
        st.caption("Visible to Admin & Trust and Safety team only.")
        st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: WEDDING SERVICES
# =====================================================================
def page_wedding_services():
    render_global_css(bg_color="#F8F9FA", page_css=""".main-header { background: -webkit-linear-gradient(45deg, #1A365D, #D4AF37); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-family: 'Trebuchet MS', sans-serif; font-weight: 900; font-size: 3rem; text-align: center; margin-bottom: 0px; }
.step-box { background: white; border-radius: 15px; padding: 25px; margin-bottom: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border: 1px solid #EAEAEA; border-left: 8px solid #D4AF37; transition: transform 0.3s ease; }
.step-box:hover { transform: translateY(-5px); box-shadow: 0 15px 30px rgba(212, 175, 55, 0.25); }
.service-main-title-box { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); color: white; padding: 12px 18px; border-radius: 10px; margin-bottom: 12px; border-bottom: 3px solid #D4AF37; box-shadow: 0 4px 10px rgba(0,0,0,0.15); display: flex; align-items: center; gap: 15px; }
.step-badge { background: #D4AF37; color: #0F2027; padding: 4px 12px; border-radius: 50px; font-weight: 900; font-size: 0.95rem; text-transform: uppercase; }
.service-sub-title-box { background: linear-gradient(135deg, #E2E8F0 0%, #CBD5E1 100%); border-left: 5px solid #2563EB; color: #1E3A8A; padding: 10px 15px; border-radius: 8px; margin-bottom: 10px; font-weight: 800; font-size: 1.1rem; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
.service-desc-text { color: #334155; font-size: 0.95rem; line-height: 1.5; margin-bottom: 15px; }
.cart-box { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); color: white; padding: 25px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
.vendor-card { background: white; border-radius: 12px; padding: 16px 18px; margin-bottom: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 6px solid #999; }
.vendor-card.tier-platinum { border-left-color: #6D6D6D; background: linear-gradient(135deg, #FFFFFF, #F4F4F4); }
.vendor-card.tier-gold { border-left-color: #D4AF37; }
.vendor-card.tier-free { border-left-color: #CBD5E1; }
.tier-chip-platinum { background: linear-gradient(90deg, #6D6D6D, #C0C0C0, #6D6D6D); color: white; padding: 2px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: 800; }
.tier-chip-gold { background: #D4AF37; color: white; padding: 2px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: 800; }
.tier-chip-free { background: #CBD5E1; color: #334155; padding: 2px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: 800; }
.search-vendors-wrap div.stButton > button[kind="primary"] { background: linear-gradient(90deg, #FF416C, #FF4B2B, #D4AF37, #1A365D) !important; background-size: 300% 300% !important; animation: gradientShift 4s ease infinite !important; border: none !important; color: white !important; font-weight: 900 !important; box-shadow: 0 6px 16px rgba(212,175,55,0.4) !important; }
.search-vendors-wrap div.stButton > button[kind="primary"]:hover { transform: translateY(-2px); box-shadow: 0 10px 22px rgba(212,175,55,0.55) !important; }
@keyframes gradientShift { 0% {background-position:0% 50%;} 50% {background-position:100% 50%;} 100% {background-position:0% 50%;} }""")

    if "vendor_favorites" not in st.session_state:
        st.session_state.vendor_favorites = []
    if "active_service_category" not in st.session_state:
        st.session_state.active_service_category = None

    is_paid_member = st.session_state.get("is_paid_member", False)

    VENDORS = [
        {"name": "Royal Events & Management Co.", "category": "Wedding Planner / Management", "city": "Nagpur", "rating": 4.8, "phone": "+91 98450 11101", "tier": "platinum"},
        {"name": "Nagpur Event Crafters", "category": "Wedding Planner / Management", "city": "Nagpur", "rating": 4.5, "phone": "+91 98450 11102", "tier": "gold"},
        {"name": "Budget Wedding Planners", "category": "Wedding Planner / Management", "city": "Nagpur", "rating": 4.1, "phone": "+91 98450 11103", "tier": "free"},
        {"name": "The Grand Orchid Banquets", "category": "Banquet Hall / Lawn / Resort", "city": "Nagpur", "rating": 4.9, "phone": "+91 98450 11201", "tier": "platinum"},
        {"name": "Greenfield Lawns", "category": "Banquet Hall / Lawn / Resort", "city": "Nagpur", "rating": 4.5, "phone": "+91 98450 11202", "tier": "gold"},
        {"name": "City View Banquet", "category": "Banquet Hall / Lawn / Resort", "city": "Nagpur", "rating": 4.0, "phone": "+91 98450 11203", "tier": "free"},
        {"name": "Meera Designer Studio", "category": "Designer Wedding Apparel", "city": "Pune", "rating": 4.9, "phone": "+91 98450 11301", "tier": "platinum"},
        {"name": "Ethnic Threads Boutique", "category": "Designer Wedding Apparel", "city": "Pune", "rating": 4.4, "phone": "+91 98450 11302", "tier": "gold"},
        {"name": "Local Bridal Wear", "category": "Designer Wedding Apparel", "city": "Pune", "rating": 4.0, "phone": "+91 98450 11303", "tier": "free"},
        {"name": "Suvarna Jewels", "category": "Wedding Jewelry & Ornaments", "city": "Mumbai", "rating": 4.9, "phone": "+91 98450 11401", "tier": "platinum"},
        {"name": "Radiance Gold House", "category": "Wedding Jewelry & Ornaments", "city": "Mumbai", "rating": 4.5, "phone": "+91 98450 11402", "tier": "gold"},
        {"name": "Glow & Grace Makeovers", "category": "Makeup Artist & Grooming", "city": "Nagpur", "rating": 4.8, "phone": "+91 98450 11501", "tier": "platinum"},
        {"name": "Bridal Touch Studio", "category": "Makeup Artist & Grooming", "city": "Nagpur", "rating": 4.4, "phone": "+91 98450 11502", "tier": "gold"},
        {"name": "Simple Glam Makeovers", "category": "Makeup Artist & Grooming", "city": "Nagpur", "rating": 3.9, "phone": "+91 98450 11503", "tier": "free"},
        {"name": "Frame & Story Films", "category": "Photography & Videography", "city": "Bangalore", "rating": 4.9, "phone": "+91 98450 11601", "tier": "platinum"},
        {"name": "Candid Moments Studio", "category": "Photography & Videography", "city": "Bangalore", "rating": 4.5, "phone": "+91 98450 11602", "tier": "gold"},
        {"name": "Floral Dreams Decor", "category": "Mandap, Stage & Floral Decoration", "city": "Nagpur", "rating": 4.7, "phone": "+91 98450 11701", "tier": "platinum"},
        {"name": "Petal & Light Decorators", "category": "Mandap, Stage & Floral Decoration", "city": "Nagpur", "rating": 4.3, "phone": "+91 98450 11702", "tier": "gold"},
        {"name": "Basic Stage Setup Co.", "category": "Mandap, Stage & Floral Decoration", "city": "Nagpur", "rating": 3.8, "phone": "+91 98450 11703", "tier": "free"},
        {"name": "Swaad Caterers", "category": "Catering & Food Service", "city": "Pune", "rating": 4.8, "phone": "+91 98450 11801", "tier": "platinum"},
        {"name": "Royal Feast Catering", "category": "Catering & Food Service", "city": "Pune", "rating": 4.4, "phone": "+91 98450 11802", "tier": "gold"},
        {"name": "Homestyle Caterers", "category": "Catering & Food Service", "city": "Pune", "rating": 4.0, "phone": "+91 98450 11803", "tier": "free"},
        {"name": "Beats & Baraat DJ Co.", "category": "Music, DJ & Entertainment", "city": "Nagpur", "rating": 4.6, "phone": "+91 98450 11901", "tier": "platinum"},
        {"name": "Party Vibes DJ", "category": "Music, DJ & Entertainment", "city": "Nagpur", "rating": 4.1, "phone": "+91 98450 11902", "tier": "free"},
        {"name": "PrintCraft Invitations", "category": "Wedding Invitations & Digital Cards", "city": "Mumbai", "rating": 4.5, "phone": "+91 98450 12001", "tier": "gold"},
        {"name": "Elegant Cards Studio", "category": "Wedding Invitations & Digital Cards", "city": "Mumbai", "rating": 4.7, "phone": "+91 98450 12002", "tier": "platinum"},
        {"name": "Royal Fleet Transport", "category": "Transportation Services", "city": "Nagpur", "rating": 4.5, "phone": "+91 98450 12101", "tier": "platinum"},
        {"name": "City Cabs & Buses", "category": "Transportation Services", "city": "Nagpur", "rating": 4.0, "phone": "+91 98450 12102", "tier": "free"},
        {"name": "Shahi Baraat Services", "category": "Baraat: Ghodi, Buggy & Band", "city": "Nagpur", "rating": 4.8, "phone": "+91 98450 12201", "tier": "platinum"},
        {"name": "Traditional Band Party", "category": "Baraat: Ghodi, Buggy & Band", "city": "Nagpur", "rating": 4.2, "phone": "+91 98450 12202", "tier": "gold"},
        {"name": "Acharya Ritual Services", "category": "Vedic Priest & Ritual Services", "city": "Nagpur", "rating": 4.9, "phone": "+91 98450 12301", "tier": "platinum"},
        {"name": "Shastri Pooja Samagri", "category": "Vedic Priest & Ritual Services", "city": "Nagpur", "rating": 4.3, "phone": "+91 98450 12302", "tier": "gold"},
    ]
    TIER_ORDER = {"platinum": 0, "gold": 1, "free": 2}
    TIER_LABEL = {"platinum": "\U0001F48E Platinum", "gold": "\U0001F947 Gold", "free": "Free Listing"}

    def get_sorted_vendors(category):
        matched = [v for v in VENDORS if v["category"] == category]
        return sorted(matched, key=lambda v: TIER_ORDER[v["tier"]])

    def render_vendor_row(v):
        st.markdown(f"<div class='vendor-card tier-{v['tier']}'>", unsafe_allow_html=True)
        vc1, vc2, vc3 = st.columns([3, 1, 3])
        with vc1:
            st.markdown(f"**{v['name']}** <span class='tier-chip-{v['tier']}'>{TIER_LABEL[v['tier']]}</span><br><span style='color:gray; font-size:0.85rem;'>{v['category']} \u2022 {v['city']}</span>", unsafe_allow_html=True)
        with vc2:
            st.markdown(f"\u2B50 {v['rating']}")
        with vc3:
            b1, b2, b3 = st.columns(3)
            b1.button("\U0001F4DE Call", key=f"call_{v['name']}", use_container_width=True)
            b2.button("\U0001F4AC Message", key=f"msg_{v['name']}", use_container_width=True)
            already_fav = v["name"] in st.session_state.vendor_favorites
            fav_label = "\u2764\uFE0F Saved" if already_fav else "\U0001FA76 Add to Favorites"
            if b3.button(fav_label, key=f"fav_{v['name']}", use_container_width=True, disabled=already_fav):
                st.session_state.vendor_favorites.append(v["name"])
                st.toast(f"\u2764\uFE0F {v['name']} saved to your Favorite Vendors!")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<h1 class='main-header'>Complete Wedding Services & Management</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; font-size:1.2rem; color:gray;'>Browse verified categories and search real vendors directly — no cart, no online payment, just direct contact.</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#999; font-size:0.85rem;'>\U0001F512 Bandhan.com only lists vendors. All pricing and payments are settled directly between you and the vendor via call or message.</p>", unsafe_allow_html=True)
    st.markdown("---")

    tab1, tab2 = st.tabs(["\U0001F4CB Step-by-Step Wedding Services", "\u2764\uFE0F My Favorite Vendors"])

    with tab1:
        if st.session_state.active_service_category:
            cat = st.session_state.active_service_category
            st.markdown(f"### \U0001F50D Vendors for: {cat}")
            if st.button("\u2190 Back to All Services", key="back_to_services"):
                st.session_state.active_service_category = None
                st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

            if not is_paid_member:
                st.warning("\U0001F512 Vendor search is available to paid members only.")
                if st.button("\U0001F451 View VIP Plans to Unlock Vendor Search"):
                    go_to("vip_membership")
            else:
                sorted_vendors = get_sorted_vendors(cat)
                if not sorted_vendors:
                    st.info("No verified vendors in this category yet.")
                else:
                    st.caption("Platinum vendors are shown first, followed by Gold, then Free-listed vendors.")
                    for v in sorted_vendors:
                        render_vendor_row(v)
        else:
            st.markdown("### \U0001F6E0\uFE0F All-in-One Wedding Services Master Checklist")
            st.write("Browse through all essential wedding categories, view images, and search real verified vendors for each.")
            st.markdown("<br>", unsafe_allow_html=True)

            def render_service_card(step_num, title, img_url, sub_title, desc, price_text, category_name):
                st.markdown("<div class='step-box'>", unsafe_allow_html=True)
                st.markdown(f"""
                <div class='service-main-title-box'>
                    <span class='step-badge'>Service {step_num}</span>
                    <h3 style='margin:0; color:#FBF5B7; font-family: Georgia, serif; font-size: 1.35rem;'>{title}</h3>
                </div>
                """, unsafe_allow_html=True)

                c1, c2 = st.columns([1, 2], gap="medium")
                with c1:
                    try:
                        st.image(img_url, use_container_width=True)
                    except Exception:
                        st.warning(f"\u26A0\uFE0F Image not found: {img_url}")
                with c2:
                    st.markdown(f"<div class='service-sub-title-box'>{sub_title}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='service-desc-text'>{desc}</div>", unsafe_allow_html=True)
                    st.markdown(f"<span style='color:gray; font-size:0.85rem;'>Typical market range: {price_text}</span>", unsafe_allow_html=True)
                    st.markdown("<div class='search-vendors-wrap'>", unsafe_allow_html=True)
                    if st.button("\U0001F50D Search Vendors", key=f"search_{category_name}", type="primary", use_container_width=True):
                        st.session_state.active_service_category = category_name
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            render_service_card(1, "Professional Wedding Planner & Management Agency",
                "871745.jpg", "End-to-End Wedding Management & Coordination",
                "Complete event execution, guest hospitality, and logistics handled by top-rated professional planners.",
                "\u20b9 1,00,000 \u2013 \u20b93,00,000", "Wedding Planner / Management")
            render_service_card(2, "Banquet Hall, Lawn & Resort",
                "https://images.unsplash.com/photo-1519167758481-83f550bb49b3?auto=format&fit=crop&w=600&q=80",
                "The Royal Orchid Banquet & Wedding Lawn",
                "Spacious air-conditioned hall with green lawn, stage setup, power backup, and guest stay rooms.",
                "\u20b9 80,000 \u2013 \u20b92,50,000 / Day", "Banquet Hall / Lawn / Resort")
            render_service_card(3, "Designer Wedding Apparel (Outfits)",
                "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=600&q=80",
                "Royal Bridal Lehenga & Groom Sherwani Package",
                "Exclusive designer wedding collection featuring traditional hand-embroidery and custom fitting.",
                "\u20b9 30,000 \u2013 \u20b91,50,000", "Designer Wedding Apparel")
            render_service_card(4, "Wedding Jewelry & Ornaments",
                "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=600&q=80",
                "Certified Gold & Diamond Bridal Set",
                "Certified Hallmark gold necklace set, maang tikka, earrings, and traditional wedding ornaments.",
                "\u20b9 1,00,000 \u2013 \u20b95,00,000", "Wedding Jewelry & Ornaments")
            render_service_card(5, "Professional Makeup Artist & Grooming",
                "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=600&q=80",
                "Celebrity Bridal & Groom Makeup Package",
                "HD airbrush bridal makeup, hair styling, draping, and groom grooming session by professional artists.",
                "\u20b9 15,000 \u2013 \u20b970,000", "Makeup Artist & Grooming")
            render_service_card(6, "Cinematic Photography & Videography",
                "https://images.unsplash.com/photo-1511285560929-80b456fea0bc?auto=format&fit=crop&w=600&q=80",
                "4K Cinematic Video, Drone & Candid Shoot",
                "Complete candid photography, traditional video, drone shots, pre-wedding shoot, and photo album.",
                "\u20b9 30,000 \u2013 \u20b91,50,000", "Photography & Videography")
            render_service_card(7, "Mandap, Stage & Floral Decoration",
                "https://images.unsplash.com/photo-1587271407850-8d438ca9fdf2?auto=format&fit=crop&w=600&q=80",
                "Royal Floral Mandap & Lighting Setup",
                "Exotic fresh flower arrangements, grand entrance gate, ambient fairy lighting, and theme stage decoration.",
                "\u20b9 40,000 \u2013 \u20b92,00,000", "Mandap, Stage & Floral Decoration")
            render_service_card(8, "Premium Catering & Food Service",
                "https://images.unsplash.com/photo-1555244162-803834f70033?auto=format&fit=crop&w=600&q=80",
                "Deluxe Multi-Cuisine Menu (Per 300 Guests)",
                "Welcome drinks, starters, North/South Indian main courses, live chaat counters, and exotic royal desserts.",
                "\u20b9 60,000 \u2013 \u20b92,50,000", "Catering & Food Service")
            render_service_card(9, "Music, Entertainment & Live DJ",
                "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=600&q=80",
                "Professional DJ Setup, Sound & Dhol Group",
                "High-power JBL sound system, intelligent dance floor lighting, professional live DJ, and traditional Punjabi dhol.",
                "\u20b9 12,000 \u2013 \u20b950,000", "Music, DJ & Entertainment")
            render_service_card(10, "Wedding Invitations & Digital Cards",
                "https://images.unsplash.com/photo-1632610992723-82d7c212f6d7?auto=format&fit=crop&w=600&q=80",
                "Premium Boxed Invitations & WhatsApp Video Invite",
                "100 designer box invitation cards with dry fruits/sweets packing + Custom animated WhatsApp video invitation link.",
                "\u20b9 8,000 \u2013 \u20b935,000", "Wedding Invitations & Digital Cards")
            render_service_card(11, "Guest & Couple Transportation Services",
                "https://images.unsplash.com/photo-1561100966-f6aa0145e8e6?auto=format&fit=crop&w=600&q=80",
                "Luxury Bridal Car & Guest Buses (AC Tempo Traveller)",
                "Decorated luxury bridal car (Mercedes/Audi), plus 2 AC buses & tempo travellers for guest pickup and drop services.",
                "\u20b9 15,000 \u2013 \u20b970,000", "Transportation Services")
            render_service_card(12, "Royal Baraat: Ghodi, Buggy & Band",
                "https://images.unsplash.com/photo-1707190981293-7468f51f157f?auto=format&fit=crop&w=600&q=80",
                "Royal Decorated Ghodi, Buggy & Brass Band",
                "Grand royal decorated Ghodi/Buggy for groom entry, traditional brass band team, lighting umbrella (Fanos), and fireworks.",
                "\u20b9 10,000 \u2013 \u20b945,000", "Baraat: Ghodi, Buggy & Band")
            render_service_card(13, "Vedic Priest & Ritual Services",
                "898989.jpg", "Experienced Acharya & Complete Pooja Samagri",
                "Experienced purohits for kundli matching, muhurat checking, engagement, and wedding phera rituals with complete samagri.",
                "\u20b9 5,000 \u2013 \u20b925,000", "Vedic Priest & Ritual Services")

    with tab2:
        st.markdown("<div class='cart-box'>", unsafe_allow_html=True)
        st.markdown("<h2 style='color:white; margin-top:0;'>\u2764\uFE0F Your Favorite Vendors</h2>", unsafe_allow_html=True)
        if len(st.session_state.vendor_favorites) == 0:
            st.warning("You haven't saved any vendors yet. Use 'Search Vendors' on any service and tap 'Add to Favorites'.")
        else:
            for fav_name in st.session_state.vendor_favorites:
                v = next((x for x in VENDORS if x["name"] == fav_name), None)
                if v:
                    render_vendor_row(v)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("\U0001F5D1\uFE0F Clear All Favorites"):
                st.session_state.vendor_favorites = []
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption("\U0001F512 Bandhan.com does not process payments. Please finalize pricing and booking directly with the vendor via call or message.")


# =====================================================================
# PAGE: WEDDING BUDGET CALCULATOR
# =====================================================================
def page_wedding_budget():
    render_global_css(bg_color="#fdfbfb", page_css=""".premium-title-container { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 30px 20px; border-radius: 20px; text-align: center; box-shadow: 0 15px 35px rgba(0,0,0,0.2); border: 2px solid #D4AF37; margin-bottom: 30px; }
.title-flex { display: flex; justify-content: center; align-items: center; gap: 20px; flex-wrap: wrap; }
.premium-title { font-family: 'Georgia', serif; font-size: 3.5rem; font-weight: 900; margin: 0; background: linear-gradient(to right, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: 2px; text-transform: uppercase; }
.inner-sticker { width: 75px; filter: drop-shadow(2px 4px 6px rgba(0,0,0,0.4)); }
.step-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); color: white; padding: 12px 20px; border-radius: 12px; font-size: 1.4rem; font-weight: bold; display: flex; align-items: center; gap: 15px; margin-bottom: 15px; border-left: 6px solid #D4AF37; box-shadow: 0 6px 15px rgba(0,0,0,0.1); }
.step-icon { width: 35px; height: 35px; }
.total-box { background: linear-gradient(135deg, #D4AF37 0%, #AA771C 100%); color: white; padding: 20px; border-radius: 12px; text-align: center; font-size: 2.2rem; font-weight: bold; box-shadow: 0 10px 20px rgba(212, 175, 55, 0.3); text-shadow: 1px 1px 2px rgba(0,0,0,0.2); }""")

    st.markdown("""
    <div class="premium-title-container">
    <div class="title-flex">
    <img src="https://cdn-icons-png.flaticon.com/512/3135/3135715.png" class="inner-sticker">
    <h1 class="premium-title">Wedding Budget</h1>
    <img src="https://cdn-icons-png.flaticon.com/512/2953/2953363.png" class="inner-sticker">
    </div>
    <p style="color:#FBF5B7; font-size:1.2rem; margin-top:10px; font-style:italic;">Plan Your Dream Royal Wedding Flawlessly</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2], gap="large")
    with col1:
        st.markdown("""
        <div class="step-header">
        <img src="https://cdn-icons-png.flaticon.com/512/5501/5501375.png" class="step-icon">
        Step 1: Set Total Budget
        </div>
        """, unsafe_allow_html=True)
        total_budget = st.number_input("Enter Amount (in INR \u20b9)", min_value=100000, max_value=50000000, value=2500000, step=50000)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="step-header">
        <img src="https://cdn-icons-png.flaticon.com/512/3126/3126647.png" class="step-icon">
        Step 2: Guest Count
        </div>
        """, unsafe_allow_html=True)
        guests = st.slider("Estimated Number of Guests", 50, 2000, 500)

        st.markdown("<br>", unsafe_allow_html=True)
        st.button("\U0001F504 Recalculate Plan", type="primary", use_container_width=True, key="wb_recalc")

    with col2:
        st.markdown(f"<div class='total-box'>Grand Total: \u20b9 {total_budget:,.0f}</div><br>", unsafe_allow_html=True)

        venue_cat = int(total_budget * 0.36)
        jewelry = int(total_budget * 0.22)
        apparel = int(total_budget * 0.14)
        photo_misc = int(total_budget * 0.18)
        other_expenses = int(total_budget * 0.10)

        def create_budget_card(title, amount, percentage, img_url, color):
            return f"""
            <div style="display:flex; background:white; border-radius:15px; margin-bottom:15px; box-shadow:0 8px 20px rgba(0,0,0,0.06); overflow:hidden; border:1px solid #EAEAEA; border-left:6px solid {color}; transition: transform 0.3s;">
                <img src="{img_url}" style="width:140px; object-fit:cover;">
                <div style="padding:15px; width:100%; display:flex; flex-direction:column; justify-content:center;">
                    <h4 style="margin:0; color:#1A365D; font-size:1.1rem;">{title} ({percentage}%)</h4>
                    <h2 style="margin:5px 0; color:#27AE60; font-weight:800;">\u20b9 {amount:,.0f}</h2>
                    <div style="background:#F0F0F0; border-radius:10px; height:8px; width:100%; margin-top:5px;">
                        <div style="background:{color}; width:{percentage}%; height:100%; border-radius:10px;"></div>
                    </div>
                </div>
            </div>
            """

        st.markdown(create_budget_card("\U0001F3F0 Venue & Premium Catering", venue_cat, 36,
            "https://images.unsplash.com/photo-1519225421980-715cb0215aed?auto=format&fit=crop&w=400&q=80", "#D4AF37"), unsafe_allow_html=True)
        st.markdown(create_budget_card("\U0001F48D Wedding Jewelry & Ornaments", jewelry, 22,
            "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=400&q=80", "#8E44AD"), unsafe_allow_html=True)
        st.markdown(create_budget_card("\U0001F457 Designer Apparel & Styling", apparel, 14,
            "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=400&q=80", "#E74C3C"), unsafe_allow_html=True)
        st.markdown(create_budget_card("\U0001F4F8 Photography, Music & Misc", photo_misc, 18,
            "https://images.unsplash.com/photo-1511285560929-80b456fea0bc?auto=format&fit=crop&w=400&q=80", "#2980B9"), unsafe_allow_html=True)
        st.markdown(create_budget_card("\U0001F4B0 Other Expenses", other_expenses, 10,
            "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=400&q=80", "#16A085"), unsafe_allow_html=True)


# =====================================================================
# PAGE: WEDDING FINANCE
# =====================================================================
def page_wedding_finance():
    render_global_css(bg_color="#F4F6F9", page_css=""".finance-header { position: relative; background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 40px 30px; border-radius: 20px; color: white; text-align: center; box-shadow: 0 15px 35px rgba(0,0,0,0.2); border: 2px solid #D4AF37; margin-bottom: 30px; overflow: hidden; }
.header-flex { display: flex; justify-content: center; align-items: center; gap: 20px; flex-wrap: wrap; }
.card-img-left { width: 80px; filter: drop-shadow(2px 4px 8px rgba(0,0,0,0.5)); }
.finance-title { font-family: 'Georgia', serif; font-size: 3rem; font-weight: 900; margin: 0; background: linear-gradient(to right, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.money-img-right { width: 75px; filter: drop-shadow(2px 4px 8px rgba(0,0,0,0.5)); }
.calc-container { background: white; padding: 35px; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.08); border: 1px solid #EAEAEA; }
.section-box-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); color: #FBF5B7; padding: 14px 20px; border-radius: 12px; font-size: 1.25rem; font-weight: 800; margin-bottom: 15px; border-left: 5px solid #D4AF37; box-shadow: 0 5px 15px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 10px; }
.premium-value-box { background: linear-gradient(135deg, #F8F9FA 0%, #E9ECEF 100%); border: 2px solid #CBD5E1; padding: 12px 20px; border-radius: 10px; text-align: center; font-size: 1.4rem; font-weight: 900; color: #D97706; box-shadow: inset 0 2px 4px rgba(0,0,0,0.05); margin-top: 10px; margin-bottom: 25px; letter-spacing: 0.5px; }
.emi-box { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); color: white; padding: 35px; border-radius: 20px; text-align: center; box-shadow: 0 15px 30px rgba(26, 54, 93, 0.25); border: 2px solid #D4AF37; }
.emi-amount { font-size: 3.2rem; color: #27AE60; font-weight: 900; margin: 15px 0; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
.finance-partners-header { background: linear-gradient(90deg, #FF416C, #FF4B2B, #D4AF37, #1A365D, #2C5364); background-size: 300% 300%; animation: gradientShift 5s ease infinite; padding: 22px 26px; border-radius: 16px; color: white; text-align: center; box-shadow: 0 10px 26px rgba(212,175,55,0.4); margin-bottom: 20px; }
.finance-partners-header h2 { margin: 0; font-family: 'Georgia', serif; font-size: 2rem; }
@keyframes gradientShift { 0% {background-position:0% 50%;} 50% {background-position:100% 50%;} 100% {background-position:0% 50%;} }
.partner-card { background: white; border-radius: 12px; padding: 16px 18px; margin-bottom: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 6px solid #999; }
.partner-card.tier-platinum { border-left-color: #6D6D6D; background: linear-gradient(135deg, #FFFFFF, #F4F4F4); }
.partner-card.tier-gold { border-left-color: #D4AF37; }
.partner-card.tier-free { border-left-color: #CBD5E1; }
.tier-chip-platinum { background: linear-gradient(90deg, #6D6D6D, #C0C0C0, #6D6D6D); color: white; padding: 2px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: 800; }
.tier-chip-gold { background: #D4AF37; color: white; padding: 2px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: 800; }
.tier-chip-free { background: #CBD5E1; color: #334155; padding: 2px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: 800; }""")

    st.markdown("""
    <div class="finance-header">
        <div class="header-flex">
            <img src="https://cdn-icons-png.flaticon.com/512/6963/6963703.png" class="card-img-left" title="Instant Credit Card">
            <h1 class="finance-title">Instant Wedding Finance</h1>
            <img src="https://cdn-icons-png.flaticon.com/512/2489/2489756.png" class="money-img-right" title="Wedding Money">
        </div>
        <p style="font-size:1.2rem; margin-top:15px; color:#FBF5B7; font-style:italic;">Get up to \u20b950 Lakhs with zero processing fee and flexible EMI options.</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1.2, 1], gap="large")
    with col1:
        st.markdown("<div class='calc-container'>", unsafe_allow_html=True)
        st.markdown("<div class='section-box-header'>\U0001F9EE Advanced EMI Calculator</div>", unsafe_allow_html=True)
        st.markdown("<hr style='margin: 10px 0 20px 0;'>", unsafe_allow_html=True)

        st.markdown("<div class='section-box-header' style='font-size: 1.1rem;'>\U0001F4B3 Select Loan Amount (\u20b9)</div>", unsafe_allow_html=True)
        loan_amount = st.slider("", min_value=100000, max_value=5000000, value=1500000, step=50000, label_visibility="collapsed", key="wf_loan")
        st.markdown(f"<div class='premium-value-box'>\u20b9 {loan_amount:,.0f}</div>", unsafe_allow_html=True)

        st.markdown("<div class='section-box-header' style='font-size: 1.1rem;'>\u23F3 Select Tenure (Years)</div>", unsafe_allow_html=True)
        tenure = st.slider("", min_value=1, max_value=10, value=5, step=1, label_visibility="collapsed", key="wf_tenure")
        st.markdown(f"<div class='premium-value-box'>{tenure} Years ({tenure * 12} Months)</div>", unsafe_allow_html=True)

        st.markdown("<div class='section-box-header' style='font-size: 1.1rem;'>\U0001F4CA Rate of Interest (% p.a.)</div>", unsafe_allow_html=True)
        interest_rate = st.number_input("", min_value=5.0, max_value=25.0, value=10.5, step=0.5, label_visibility="collapsed", key="wf_rate")
        st.markdown(f"<div class='premium-value-box'>{interest_rate}% p.a.</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        monthly_rate = interest_rate / (12 * 100)
        months = tenure * 12
        emi = (loan_amount * monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="emi-box">
            <h3 style="color:#D4AF37; margin:0; font-size:1.5rem; text-transform:uppercase; letter-spacing:1px;">Estimated Monthly EMI</h3>
            <div class="emi-amount">\u20b9 {emi:,.0f}</div>
            <p style="color:#E2E8F0; font-size:1rem; margin:0;">Total Tenure: <b>{months} Months</b> @ <b>{interest_rate}% Interest</b></p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("Apply for Instant Pre-Approval", key="wf_apply"):
            st.session_state.finance_applied = True
            st.balloons()
            st.success("\u2705 Application Submitted Successfully! Our partner bank executive will contact you within 24 hours.")

    st.markdown("---")

    if "finance_applied" not in st.session_state:
        st.session_state.finance_applied = False
    if "finance_favorites" not in st.session_state:
        st.session_state.finance_favorites = []

    render_html("""
    <div class="finance-partners-header">
        <h2>\U0001F3E6 Verified Finance Partners</h2>
        <p style="color:#FBF5B7; margin-top:6px;">Banks and NBFCs listed here are Aadhaar/PAN/GST-verified through our Vendor Registration process.</p>
    </div>
    """)

    if not st.session_state.finance_applied:
        st.info("\U0001F4DD Click 'Apply for Instant Pre-Approval' above to view our verified finance partners.")
    else:
        is_paid_member = st.session_state.get("is_paid_member", False)
        if not is_paid_member:
            st.warning("\U0001F512 Verified Finance Partners are available to paid members only.")
            if st.button("\U0001F451 View VIP Plans to Unlock Finance Partners"):
                go_to("vip_membership")
        else:
            finance_partners = [
                {"name": "Bandhan Partner Bank Ltd.", "type": "Bank", "rate": "9.8% p.a. onwards", "phone": "+91 98450 21001", "tier": "platinum"},
                {"name": "Nagpur Cooperative Wedding Finance", "type": "NBFC", "rate": "10.5% p.a. onwards", "phone": "+91 98450 21002", "tier": "gold"},
                {"name": "QuickWed Finance Solutions", "type": "NBFC", "rate": "11.2% p.a. onwards", "phone": "+91 98450 21003", "tier": "free"},
            ]
            tier_order = {"platinum": 0, "gold": 1, "free": 2}
            tier_label = {"platinum": "\U0001F48E Platinum", "gold": "\U0001F947 Gold", "free": "Free Listing"}
            sorted_partners = sorted(finance_partners, key=lambda p: tier_order[p["tier"]])

            st.caption("Platinum partners are shown first, followed by Gold, then Free-listed partners.")
            st.markdown("<br>", unsafe_allow_html=True)

            for p in sorted_partners:
                st.markdown(f"<div class='partner-card tier-{p['tier']}'>", unsafe_allow_html=True)
                pc1, pc2, pc3 = st.columns([3, 1, 3])
                with pc1:
                    st.markdown(f"**{p['name']}** <span class='tier-chip-{p['tier']}'>{tier_label[p['tier']]}</span><br><span style='color:gray; font-size:0.85rem;'>{p['type']}</span>", unsafe_allow_html=True)
                with pc2:
                    st.markdown(f"Rate: {p['rate']}")
                with pc3:
                    b1, b2, b3 = st.columns(3)
                    b1.button("\U0001F4DE Call", key=f"call_{p['name']}", use_container_width=True)
                    b2.button("\U0001F4AC Message", key=f"msg_{p['name']}", use_container_width=True)
                    already_fav = p["name"] in st.session_state.finance_favorites
                    fav_label = "\u2764\uFE0F Saved" if already_fav else "\U0001FA76 Favorite"
                    if b3.button(fav_label, key=f"fav_{p['name']}", use_container_width=True, disabled=already_fav):
                        st.session_state.finance_favorites.append(p["name"])
                        st.toast(f"\u2764\uFE0F {p['name']} saved to your Favorites!")
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    render_html("""
    <div style="text-align:center; background:linear-gradient(135deg,#1A365D,#0F2027); padding:22px; border-radius:14px;">
        <p style="color:#E2E8F0; margin-bottom:12px;">Are you a bank or NBFC offering wedding loans? Get listed here.</p>
    </div>
    """)
    if st.button("\U0001F9D1\u200d\U0001F4BC Register as a Finance Partner", key="wf_register_finance"):
        go_to("vendor_registration")


# =====================================================================
# PAGE: KUNDLI MATCH
# =====================================================================
KUNDLI_STATE_DISTRICTS = {
    "Andhra Pradesh": ["Alluri Sitharama Raju", "Anakapalli", "Anantapur", "Annamayya", "Bapatla", "Chittoor", "Dr. B.R. Ambedkar Konaseema", "East Godavari", "Eluru", "Guntur", "Kakinada", "Krishna", "Kurnool", "Nandyal", "NTR", "Palnadu", "Parvathipuram Manyam", "Prakasam", "Sri Potti Sriramulu Nellore", "Sri Sathya Sai", "Srikakulam", "Tirupati", "Visakhapatnam", "Vizianagaram", "West Godavari", "YSR Kadapa"],
    "Arunachal Pradesh": ["Anjaw", "Changlang", "Dibang Valley", "East Kameng", "East Siang", "Kamle", "Kra Daadi", "Kurung Kumey", "Lepa Rada", "Lohit", "Longding", "Lower Dibang Valley", "Lower Siang", "Lower Subansiri", "Namsai", "Pakke-Kessang", "Papum Pare", "Shi Yomi", "Siang", "Tawang", "Tirap", "Upper Dibang Valley", "Upper Siang", "Upper Subansiri", "West Kameng", "West Siang"],
    "Assam": ["Baksa", "Barpeta", "Biswanath", "Bongaigaon", "Cachar", "Charaideo", "Chirang", "Darrang", "Dhemaji", "Dhubri", "Dibrugarh", "Dima Hasao", "Goalpara", "Golaghat", "Hailakandi", "Hojai", "Jorhat", "Kamrup", "Kamrup Metropolitan", "Karbi Anglong", "Karimganj", "Kokrajhar", "Lakhimpur", "Majuli", "Morigaon", "Nagaon", "Nalbari", "Sivasagar", "Sonitpur", "South Salmara-Mankachar", "Tinsukia", "Udalguri", "West Karbi Anglong"],
    "Bihar": ["Araria", "Arwal", "Aurangabad", "Banka", "Begusarai", "Bhagalpur", "Bhojpur", "Buxar", "Darbhanga", "East Champaran", "Gaya", "Gopalganj", "Jamui", "Jehanabad", "Kaimur", "Katihar", "Khagaria", "Kishanganj", "Lakhisarai", "Madhepura", "Madhubani", "Munger", "Muzaffarpur", "Nalanda", "Nawada", "Patna", "Purnia", "Rohtas", "Saharsa", "Samastipur", "Saran", "Sheikhpura", "Sheohar", "Sitamarhi", "Siwan", "Supaul", "Vaishali", "West Champaran"],
    "Chhattisgarh": ["Balod", "Baloda Bazar", "Balrampur", "Bastar", "Bemetara", "Bijapur", "Bilaspur", "Dantewada", "Dhamtari", "Durg", "Gariaband", "Gaurela-Pendra-Marwahi", "Janjgir-Champa", "Jashpur", "Kabirdham", "Kanker", "Kondagaon", "Korba", "Koriya", "Mahasamund", "Mungeli", "Narayanpur", "Raigarh", "Raipur", "Rajnandgaon", "Sukma", "Surajpur", "Surguja"],
    "Goa": ["North Goa", "South Goa"],
    "Gujarat": ["Ahmedabad", "Amreli", "Anand", "Aravalli", "Banaskantha", "Bharuch", "Bhavnagar", "Botad", "Chhota Udepur", "Dahod", "Dang", "Devbhoomi Dwarka", "Gandhinagar", "Gir Somnath", "Jamnagar", "Junagadh", "Kheda", "Kutch", "Mahisagar", "Mehsana", "Morbi", "Narmada", "Navsari", "Panchmahal", "Patan", "Porbandar", "Rajkot", "Sabarkantha", "Surat", "Surendranagar", "Tapi", "Vadodara", "Valsad"],
    "Haryana": ["Ambala", "Bhiwani", "Charkhi Dadri", "Faridabad", "Fatehabad", "Gurugram", "Hisar", "Jhajjar", "Jind", "Kaithal", "Karnal", "Kurukshetra", "Mahendragarh", "Nuh", "Palwal", "Panchkula", "Panipat", "Rewari", "Rohtak", "Sirsa", "Sonipat", "Yamunanagar"],
    "Himachal Pradesh": ["Bilaspur", "Chamba", "Hamirpur", "Kangra", "Kinnaur", "Kullu", "Lahaul and Spiti", "Mandi", "Shimla", "Sirmaur", "Solan", "Una"],
    "Jharkhand": ["Bokaro", "Chatra", "Deoghar", "Dhanbad", "Dumka", "East Singhbhum", "Garhwa", "Giridih", "Godda", "Gumla", "Hazaribagh", "Jamtara", "Khunti", "Koderma", "Latehar", "Lohardaga", "Pakur", "Palamu", "Ramgarh", "Ranchi", "Sahebganj", "Seraikela-Kharsawan", "Simdega", "West Singhbhum"],
    "Karnataka": ["Bagalkot", "Ballari", "Belagavi", "Bengaluru Rural", "Bengaluru Urban", "Bidar", "Chamarajanagar", "Chikballapur", "Chikkamagaluru", "Chitradurga", "Dakshina Kannada", "Davanagere", "Dharwad", "Gadag", "Hassan", "Haveri", "Kalaburagi", "Kodagu", "Kolar", "Koppal", "Mandya", "Mysuru", "Raichur", "Ramanagara", "Shivamogga", "Tumakuru", "Udupi", "Uttara Kannada", "Vijayapura", "Vijayanagara", "Yadgir"],
    "Kerala": ["Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod", "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad", "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad"],
    "Madhya Pradesh": ["Agar Malwa", "Alirajpur", "Anuppur", "Ashoknagar", "Balaghat", "Barwani", "Betul", "Bhind", "Bhopal", "Burhanpur", "Chhatarpur", "Chhindwara", "Damoh", "Datia", "Dewas", "Dhar", "Dindori", "Guna", "Gwalior", "Harda", "Narmadapuram (Hoshangabad)", "Indore", "Jabalpur", "Jhabua", "Katni", "Khandwa", "Khargone", "Mandla", "Mandsaur", "Morena", "Narsinghpur", "Neemuch", "Niwari", "Panna", "Raisen", "Rajgarh", "Ratlam", "Rewa", "Sagar", "Satna", "Sehore", "Seoni", "Shahdol", "Shajapur", "Sheopur", "Shivpuri", "Sidhi", "Singrauli", "Tikamgarh", "Ujjain", "Umaria", "Vidisha"],
    "Maharashtra": ["Ahmednagar", "Akola", "Amravati", "Chhatrapati Sambhajinagar (Aurangabad)", "Beed", "Bhandara", "Buldhana", "Chandrapur", "Dhule", "Gadchiroli", "Gondia", "Hingoli", "Jalgaon", "Jalna", "Kolhapur", "Latur", "Mumbai City", "Mumbai Suburban", "Nagpur", "Nanded", "Nandurbar", "Nashik", "Dharashiv (Osmanabad)", "Palghar", "Parbhani", "Pune", "Raigad", "Ratnagiri", "Sangli", "Satara", "Sindhudurg", "Solapur", "Thane", "Wardha", "Washim", "Yavatmal"],
    "Manipur": ["Bishnupur", "Chandel", "Churachandpur", "Imphal East", "Imphal West", "Jiribam", "Kakching", "Kamjong", "Kangpokpi", "Noney", "Pherzawl", "Senapati", "Tamenglong", "Tengnoupal", "Thoubal", "Ukhrul"],
    "Meghalaya": ["East Garo Hills", "East Jaintia Hills", "East Khasi Hills", "Eastern West Khasi Hills", "North Garo Hills", "Ri Bhoi", "South Garo Hills", "South West Garo Hills", "South West Khasi Hills", "West Garo Hills", "West Jaintia Hills", "West Khasi Hills"],
    "Mizoram": ["Aizawl", "Champhai", "Hnahthial", "Khawzawl", "Kolasib", "Lawngtlai", "Lunglei", "Mamit", "Saitual", "Serchhip", "Saiha"],
    "Nagaland": ["Chumoukedima", "Dimapur", "Kiphire", "Kohima", "Longleng", "Mokokchung", "Mon", "Niuland", "Noklak", "Peren", "Phek", "Shamator", "Tseminyu", "Tuensang", "Wokha", "Zunheboto"],
    "Odisha": ["Angul", "Balangir", "Balasore", "Bargarh", "Bhadrak", "Boudh", "Cuttack", "Deogarh", "Dhenkanal", "Gajapati", "Ganjam", "Jagatsinghpur", "Jajpur", "Jharsuguda", "Kalahandi", "Kandhamal", "Kendrapara", "Kendujhar", "Khordha", "Koraput", "Malkangiri", "Mayurbhanj", "Nabarangpur", "Nayagarh", "Nuapada", "Puri", "Rayagada", "Sambalpur", "Subarnapur", "Sundargarh"],
    "Punjab": ["Amritsar", "Barnala", "Bathinda", "Faridkot", "Fatehgarh Sahib", "Fazilka", "Ferozepur", "Gurdaspur", "Hoshiarpur", "Jalandhar", "Kapurthala", "Ludhiana", "Malerkotla", "Mansa", "Moga", "Muktsar", "Pathankot", "Patiala", "Rupnagar", "Sahibzada Ajit Singh Nagar (Mohali)", "Sangrur", "Shaheed Bhagat Singh Nagar", "Tarn Taran"],
    "Rajasthan": ["Ajmer", "Alwar", "Banswara", "Baran", "Barmer", "Bharatpur", "Bhilwara", "Bikaner", "Bundi", "Chittorgarh", "Churu", "Dausa", "Dholpur", "Dungarpur", "Hanumangarh", "Jaipur", "Jaisalmer", "Jalore", "Jhalawar", "Jhunjhunu", "Jodhpur", "Karauli", "Kota", "Nagaur", "Pali", "Pratapgarh", "Rajsamand", "Sawai Madhopur", "Sikar", "Sirohi", "Sri Ganganagar", "Tonk", "Udaipur"],
    "Sikkim": ["Gangtok", "Gyalshing", "Mangan", "Namchi", "Pakyong", "Soreng"],
    "Tamil Nadu": ["Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore", "Dharmapuri", "Dindigul", "Erode", "Kallakurichi", "Kanchipuram", "Kanyakumari", "Karur", "Krishnagiri", "Madurai", "Mayiladuthurai", "Nagapattinam", "Namakkal", "Nilgiris", "Perambalur", "Pudukkottai", "Ramanathapuram", "Ranipet", "Salem", "Sivaganga", "Tenkasi", "Thanjavur", "Theni", "Thoothukudi", "Tiruchirappalli", "Tirunelveli", "Tirupathur", "Tiruppur", "Tiruvallur", "Tiruvannamalai", "Tiruvarur", "Vellore", "Viluppuram", "Virudhunagar"],
    "Telangana": ["Adilabad", "Bhadradri Kothagudem", "Hyderabad", "Jagtial", "Jangaon", "Jayashankar Bhupalpally", "Jogulamba Gadwal", "Kamareddy", "Karimnagar", "Khammam", "Komaram Bheem", "Mahabubabad", "Mahabubnagar", "Mancherial", "Medak", "Medchal-Malkajgiri", "Mulugu", "Nagarkurnool", "Nalgonda", "Narayanpet", "Nirmal", "Nizamabad", "Peddapalli", "Rajanna Sircilla", "Rangareddy", "Sangareddy", "Siddipet", "Suryapet", "Vikarabad", "Wanaparthy", "Warangal", "Hanumakonda", "Yadadri Bhuvanagiri"],
    "Tripura": ["Dhalai", "Gomati", "Khowai", "North Tripura", "Sepahijala", "South Tripura", "Unakoti", "West Tripura"],
    "Uttar Pradesh": ["Agra", "Aligarh", "Ambedkar Nagar", "Amethi", "Amroha", "Auraiya", "Ayodhya", "Azamgarh", "Baghpat", "Bahraich", "Ballia", "Balrampur", "Banda", "Barabanki", "Bareilly", "Basti", "Bhadohi", "Bijnor", "Budaun", "Bulandshahr", "Chandauli", "Chitrakoot", "Deoria", "Etah", "Etawah", "Farrukhabad", "Fatehpur", "Firozabad", "Gautam Buddha Nagar", "Ghaziabad", "Ghazipur", "Gonda", "Gorakhpur", "Hamirpur", "Hapur", "Hardoi", "Hathras", "Jalaun", "Jaunpur", "Jhansi", "Kannauj", "Kanpur Dehat", "Kanpur Nagar", "Kasganj", "Kaushambi", "Kheri", "Kushinagar", "Lalitpur", "Lucknow", "Maharajganj", "Mahoba", "Mainpuri", "Mathura", "Mau", "Meerut", "Mirzapur", "Moradabad", "Muzaffarnagar", "Pilibhit", "Pratapgarh", "Prayagraj", "Rae Bareli", "Rampur", "Saharanpur", "Sambhal", "Sant Kabir Nagar", "Shahjahanpur", "Shamli", "Shravasti", "Siddharthnagar", "Sitapur", "Sonbhadra", "Sultanpur", "Unnao", "Varanasi"],
    "Uttarakhand": ["Almora", "Bageshwar", "Chamoli", "Champawat", "Dehradun", "Haridwar", "Nainital", "Pauri Garhwal", "Pithoragarh", "Rudraprayag", "Tehri Garhwal", "Udham Singh Nagar", "Uttarkashi"],
    "West Bengal": ["Alipurduar", "Bankura", "Birbhum", "Cooch Behar", "Dakshin Dinajpur", "Darjeeling", "Hooghly", "Howrah", "Jalpaiguri", "Jhargram", "Kalimpong", "Kolkata", "Malda", "Murshidabad", "Nadia", "North 24 Parganas", "Paschim Bardhaman", "Paschim Medinipur", "Purba Bardhaman", "Purba Medinipur", "Purulia", "South 24 Parganas", "Uttar Dinajpur"],
    "Andaman and Nicobar Islands": ["Nicobar", "North and Middle Andaman", "South Andaman"],
    "Chandigarh": ["Chandigarh"],
    "Dadra and Nagar Haveli and Daman and Diu": ["Dadra and Nagar Haveli", "Daman", "Diu"],
    "Delhi": ["Central Delhi", "East Delhi", "New Delhi", "North Delhi", "North East Delhi", "North West Delhi", "Shahdara", "South Delhi", "South East Delhi", "South West Delhi", "West Delhi"],
    "Jammu and Kashmir": ["Anantnag", "Bandipora", "Baramulla", "Budgam", "Doda", "Ganderbal", "Jammu", "Kathua", "Kishtwar", "Kulgam", "Kupwara", "Poonch", "Pulwama", "Rajouri", "Ramban", "Reasi", "Samba", "Shopian", "Srinagar", "Udhampur"],
    "Ladakh": ["Kargil", "Leh"],
    "Lakshadweep": ["Lakshadweep"],
    "Puducherry": ["Karaikal", "Mahe", "Puducherry", "Yanam"],
}
KUNDLI_ALL_STATES = sorted(KUNDLI_STATE_DISTRICTS.keys())


def page_kundli_match():
    render_global_css(bg_color="#FFFDF8", page_css=""".header-kundali { color: #D35400; font-family: 'Georgia', serif; font-size: 2.8rem; text-align: center; font-weight: bold; }
.guna-score { font-size: 4rem; color: #27AE60; font-weight: 900; text-align: center; }
.card-box { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border-top: 3px solid #D35400; }""")

    st.markdown("<h1 class='header-kundali'>\U0001F549\uFE0F AI Kundali & Guna Milan</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:gray;'>Our advanced Vedic AI calculates accurate planetary positions and the 36 Gunas for perfect compatibility.</p>", unsafe_allow_html=True)
    st.markdown("---")

    def birth_place_block(prefix):
        place = st.text_input("Place of Birth (City / Village)", key=f"{prefix}_place")
        state = st.selectbox("State", KUNDLI_ALL_STATES, key=f"{prefix}_state")
        district = st.selectbox("District", KUNDLI_STATE_DISTRICTS[state], key=f"{prefix}_district")
        lat_col, lon_col = st.columns(2)
        with lat_col:
            latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=0.0, step=0.0001, format="%.4f", key=f"{prefix}_lat")
        with lon_col:
            longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=0.0, step=0.0001, format="%.4f", key=f"{prefix}_lon")
        return place, state, district, latitude, longitude

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("### \U0001F935 Boy's Birth Details")
        b_name = st.text_input("Name", key="b_name")
        b_date = st.date_input("Date of Birth", key="b_date")
        b_time = st.time_input("Time of Birth", key="b_time")
        b_place, b_state, b_district, b_lat, b_lon = birth_place_block("b")
    with col2:
        st.markdown("### \U0001F470 Girl's Birth Details")
        g_name = st.text_input("Name", key="g_name")
        g_date = st.date_input("Date of Birth", key="g_date")
        g_time = st.time_input("Time of Birth", key="g_time")
        g_place, g_state, g_district, g_lat, g_lon = birth_place_block("g")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("\U0001F52E Calculate 36 Guna Match", type="primary", use_container_width=True):
        if b_name and g_name:
            with st.spinner("Analyzing planetary positions and Ashtakoota Gunas..."):
                time.sleep(2.5)
            st.success("Analysis Complete!")
            st.markdown("<div class='card-box'><h3 style='text-align:center;'>Total Guna Score</h3><div class='guna-score'>28.5 / 36</div><p style='text-align:center; color:#27AE60; font-weight:bold;'>Highly Compatible Match! (Nadi Dosha: None)</p></div>", unsafe_allow_html=True)
        else:
            st.error("Please enter both names to calculate Kundali.")


# =====================================================================
# PAGE: DIGITAL INVITES
# =====================================================================
INVITE_FONT_STYLES = {
    "AI Recommended (Elegant Serif)": {
        "title": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "body": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    },
    "Modern Sans-Serif": {
        "title": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "body": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    },
    "Bold Display": {
        "title": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "body": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    },
}
INVITE_COLOR_THEMES = {
    "AI Recommended (Gold & Deep Navy)": {"accent": (212, 175, 55, 255), "title": (255, 255, 255, 255), "body": (220, 220, 220, 255), "panel": (15, 32, 39, 215)},
    "Royal Maroon & Gold": {"accent": (255, 215, 120, 255), "title": (255, 245, 230, 255), "body": (240, 220, 210, 255), "panel": (85, 15, 25, 220)},
    "Blush Pink & Ivory": {"accent": (200, 120, 140, 255), "title": (60, 40, 45, 255), "body": (90, 70, 75, 255), "panel": (255, 240, 235, 235)},
    "Classic Black & White": {"accent": (255, 255, 255, 255), "title": (255, 255, 255, 255), "body": (210, 210, 210, 255), "panel": (10, 10, 10, 210)},
}
INVITE_FALLBACK_BG_URLS = {
    "Royal Heritage": "https://images.unsplash.com/photo-1544928147-79a2dbc1f389?auto=format&fit=crop&w=1200&q=90",
    "Modern Minimalist": "https://images.unsplash.com/photo-1515934751635-c81c6bc9a2d8?auto=format&fit=crop&w=1200&q=90",
    "Floral Elegance": "https://images.unsplash.com/photo-1465495976277-4387d4b0b4c6?auto=format&fit=crop&w=1200&q=90",
}
INVITE_THEME_PROMPTS = {
    "Royal Heritage": "Luxurious royal Indian wedding invitation background, gold filigree borders, deep maroon and gold palette, ornate patterns, no text, elegant digital art",
    "Modern Minimalist": "Minimalist modern wedding invitation background, soft pastel tones, clean geometric lines, subtle gold accents, no text, elegant digital art",
    "Floral Elegance": "Romantic floral wedding invitation background, soft blush and ivory flowers, delicate botanical illustration style, no text, elegant digital art",
}


def invite_get_openai_key():
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return None


def invite_generate_ai_background(prompt, api_key):
    try:
        resp = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1024x1024", "response_format": "b64_json"},
            timeout=60,
        )
        resp.raise_for_status()
        b64_data = resp.json()["data"][0]["b64_json"]
        return base64.b64decode(b64_data)
    except Exception as e:
        st.error(f"\u26A0\uFE0F AI image generation failed: {e}")
        return None


def invite_load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def invite_fetch_theme_bytes(theme_name):
    resp = requests.get(INVITE_FALLBACK_BG_URLS[theme_name], timeout=15)
    resp.raise_for_status()
    return resp.content


def invite_get_background_bytes(theme_name, api_key):
    if api_key:
        ai_bytes = invite_generate_ai_background(INVITE_THEME_PROMPTS[theme_name], api_key)
        if ai_bytes:
            return ai_bytes, True
    try:
        return invite_fetch_theme_bytes(theme_name), False
    except Exception:
        placeholder = Image.new("RGB", (1200, 1200), color=(15, 32, 39))
        buf = BytesIO()
        placeholder.save(buf, format="PNG")
        return buf.getvalue(), False


def invite_overlay_text(bg_bytes, groom, bride, groom_parents, bride_parents, event_type,
                         wedding_date, day_name, wedding_time_str, venue, special_note,
                         font_style="AI Recommended (Elegant Serif)", color_theme="AI Recommended (Gold & Deep Navy)"):
    W, H = 1600, 1900
    img = Image.open(BytesIO(bg_bytes)).convert("RGBA").resize((W, H))
    colors = INVITE_COLOR_THEMES[color_theme]
    fonts = INVITE_FONT_STYLES[font_style]

    panel_top = int(H * 0.49)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([0, panel_top, W, H], fill=colors["panel"])
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    font_event = invite_load_font(fonts["body"], 42)
    font_title = invite_load_font(fonts["title"], 84)
    font_parents = invite_load_font(fonts["body"], 34)
    font_sub = invite_load_font(fonts["body"], 44)
    font_small = invite_load_font(fonts["body"], 34)
    font_note = invite_load_font(fonts["body"], 30)

    def center_text(y, text, font, fill):
        if not text:
            return
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((W - w) / 2, y), text, font=font, fill=fill)

    y = panel_top + 30
    center_text(y, f"{event_type} Invitation", font_event, colors["accent"]); y += 65
    center_text(y, f"{groom} & {bride}", font_title, colors["title"]); y += 110
    if groom_parents or bride_parents:
        parents_line = f"S/o {groom_parents}   \u2022   D/o {bride_parents}" if groom_parents and bride_parents else (groom_parents or bride_parents)
        center_text(y, parents_line, font_parents, colors["body"]); y += 60
    center_text(y, f"{day_name}, {wedding_date}", font_sub, colors["title"]); y += 65
    center_text(y, f"at {wedding_time_str}", font_sub, colors["accent"]); y += 65
    center_text(y, venue, font_small, colors["title"]); y += 60
    if special_note:
        center_text(y, special_note, font_note, colors["body"]); y += 55
    center_text(H - 60, "Joyfully invite you to celebrate their union", font_small, colors["body"])

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG", quality=95)
    return buf.getvalue()


def invite_build_animated_gif(bg_bytes, groom, bride, groom_parents, bride_parents, event_type,
                               wedding_date, day_name, wedding_time_str, venue, special_note,
                               font_style="AI Recommended (Elegant Serif)", color_theme="AI Recommended (Gold & Deep Navy)"):
    W, H = 900, 1050
    base = Image.open(BytesIO(bg_bytes)).convert("RGBA").resize((W, H))
    colors = INVITE_COLOR_THEMES[color_theme]
    fonts = INVITE_FONT_STYLES[font_style]
    panel_top = int(H * 0.45)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle([0, panel_top, W, H], fill=colors["panel"])
    base = Image.alpha_composite(base, overlay)

    font_event = invite_load_font(fonts["body"], 26)
    font_title = invite_load_font(fonts["title"], 48)
    font_parents = invite_load_font(fonts["body"], 20)
    font_sub = invite_load_font(fonts["body"], 26)
    font_note = invite_load_font(fonts["body"], 19)

    def center_text(draw, y, text, font, fill):
        if not text:
            return
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((W - w) / 2, y), text, font=font, fill=fill)

    parents_line = f"S/o {groom_parents}  \u2022  D/o {bride_parents}" if groom_parents and bride_parents else (groom_parents or bride_parents or "")
    y0 = panel_top + 25
    stages = [
        [],
        [(y0, f"{event_type} Invitation", font_event, colors["accent"])],
        [(y0, f"{event_type} Invitation", font_event, colors["accent"]), (y0 + 40, f"{groom} & {bride}", font_title, colors["title"])],
        [(y0, f"{event_type} Invitation", font_event, colors["accent"]), (y0 + 40, f"{groom} & {bride}", font_title, colors["title"]), (y0 + 100, parents_line, font_parents, colors["body"])],
        [(y0, f"{event_type} Invitation", font_event, colors["accent"]), (y0 + 40, f"{groom} & {bride}", font_title, colors["title"]), (y0 + 100, parents_line, font_parents, colors["body"]),
         (y0 + 135, f"{day_name}, {wedding_date}", font_sub, colors["title"]), (y0 + 170, f"at {wedding_time_str}", font_sub, colors["accent"])],
        [(y0, f"{event_type} Invitation", font_event, colors["accent"]), (y0 + 40, f"{groom} & {bride}", font_title, colors["title"]), (y0 + 100, parents_line, font_parents, colors["body"]),
         (y0 + 135, f"{day_name}, {wedding_date}", font_sub, colors["title"]), (y0 + 170, f"at {wedding_time_str}", font_sub, colors["accent"]),
         (y0 + 210, venue, font_sub, colors["title"]),
         (y0 + 250, special_note if special_note else "Save The Date", font_note, colors["body"])],
    ]
    frames = []
    for stage in stages:
        frame = base.copy()
        fd = ImageDraw.Draw(frame)
        for y, text, font, fill in stage:
            center_text(fd, y, text, font, fill)
        frames.append(frame.convert("RGB"))

    buf = BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:] + [frames[-1]] * 3, duration=700, loop=0)
    return buf.getvalue()


def invite_overlay_text_on_uploaded_gif(uploaded_gif_bytes, groom, bride, event_type, wedding_date, day_name, wedding_time_str, venue,
                                         color_theme="AI Recommended (Gold & Deep Navy)"):
    colors = INVITE_COLOR_THEMES[color_theme]
    src = Image.open(BytesIO(uploaded_gif_bytes))
    frames_out = []
    durations = []
    for frame in ImageSequence.Iterator(src):
        f = frame.convert("RGBA")
        W, H = f.size
        overlay = Image.new("RGBA", f.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        band_top = int(H * 0.78)
        d.rectangle([0, band_top, W, H], fill=colors["panel"])
        f = Image.alpha_composite(f, overlay)
        fd = ImageDraw.Draw(f)
        font_title = invite_load_font(INVITE_FONT_STYLES["AI Recommended (Elegant Serif)"]["title"], max(int(H * 0.045), 16))
        font_sub = invite_load_font(INVITE_FONT_STYLES["AI Recommended (Elegant Serif)"]["body"], max(int(H * 0.03), 12))

        def center_text(y, text, font, fill):
            bbox = fd.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            fd.text(((W - w) / 2, y), text, font=font, fill=fill)

        center_text(band_top + int(H * 0.01), f"{groom} & {bride}", font_title, colors["title"])
        center_text(band_top + int(H * 0.07), f"{day_name}, {wedding_date} at {wedding_time_str}  \u2022  {venue}", font_sub, colors["accent"])
        frames_out.append(f.convert("RGB"))
        durations.append(frame.info.get("duration", 500))

    buf = BytesIO()
    frames_out[0].save(buf, format="GIF", save_all=True, append_images=frames_out[1:], duration=durations, loop=0)
    return buf.getvalue()


def invite_render_expiry_gated_download(session_prefix, label, mime, icon):
    bytes_key = f"{session_prefix}_bytes"
    time_key = f"{session_prefix}_created_at"
    name_key = f"{session_prefix}_filename"

    if not st.session_state.get(bytes_key):
        return

    created_at = st.session_state[time_key]
    elapsed = dt.datetime.now() - created_at
    validity = dt.timedelta(hours=24)

    if elapsed > validity:
        del st.session_state[bytes_key]
        del st.session_state[time_key]
        del st.session_state[name_key]
        st.info("\u23F3 Your previously generated invite has expired (24-hour validity) and was automatically deleted. Please generate a new one.")
        return

    remaining = validity - elapsed
    hrs, rem = divmod(int(remaining.total_seconds()), 3600)
    mins = rem // 60

    st.markdown("---")
    st.markdown(f"<div class='expiry-box'>", unsafe_allow_html=True)
    st.markdown(f"#### \U0001F4E5 {label}")
    st.write(f"\u23F3 This download is valid for **24 hours** from generation. Time remaining: **{hrs}h {mins}m**. After this, it will be automatically deleted.")
    consent = st.checkbox(
        "I understand this invite is stored temporarily and will be automatically deleted after 24 hours.",
        key=f"{session_prefix}_consent_cb",
    )
    if consent:
        st.download_button(
            f"{icon} Download (Full HD)",
            data=st.session_state[bytes_key],
            file_name=st.session_state[name_key],
            mime=mime,
            use_container_width=True,
        )
    else:
        st.warning("\u26A0\uFE0F Please tick the box above to enable the download button.")
    st.markdown("</div>", unsafe_allow_html=True)


def page_digital_invites():
    render_global_css(bg_color="#FCFBF9", page_css=""".invite-header { background: -webkit-linear-gradient(45deg, #8E2DE2, #4A00E0); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-family: 'Georgia', serif; font-weight: 900; font-size: 3rem; text-align: center; margin-bottom: 10px; }
.template-card { background-color: white; padding: 15px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.08); text-align: center; border: 2px solid transparent; transition: all 0.3s ease; }
.template-card:hover { border: 2px solid #4A00E0; transform: translateY(-5px); }
.expiry-box { background: linear-gradient(135deg, #FFF3E0, #FFE8CC); border: 2px solid #E67E22; border-radius: 12px; padding: 16px 20px; margin-top: 15px; }""")

    st.markdown("<h1 class='invite-header'>Design Your Royal E-Invite</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; font-size:1.2rem; color:#555;'>AI-generated banners and animated invites, personalized with your names, date, and venue \u2014 in Full HD.</p>", unsafe_allow_html=True)
    st.markdown("---")

    api_key = invite_get_openai_key()
    if not api_key:
        st.warning("\U0001F511 AI image generation needs an OpenAI API key added to Streamlit Cloud \u2192 App Settings \u2192 Secrets, as `OPENAI_API_KEY = \"sk-...\"`. Until then, themed stock backgrounds are used instead of AI art.")

    tab1, tab2 = st.tabs(["\U0001F5BC\uFE0F AI-Generated Banners", "\U0001F3AC Animated Invites"])

    with tab1:
        st.markdown("### **1. Choose Your Background**")
        bg_source = st.radio("Background source", ["Use a Bandhan Theme (AI / Stock)", "Upload Your Own Background Image"], key="banner_bg_source", horizontal=True)

        uploaded_bg_bytes = None
        if bg_source == "Use a Bandhan Theme (AI / Stock)":
            col1, col2, col3 = st.columns(3)
            theme_cols = {"Royal Heritage": col1, "Modern Minimalist": col2, "Floral Elegance": col3}
            if "selected_theme" not in st.session_state:
                st.session_state.selected_theme = "Royal Heritage"

            for theme_name, col in theme_cols.items():
                with col:
                    st.markdown("<div class='template-card'>", unsafe_allow_html=True)
                    st.image(INVITE_FALLBACK_BG_URLS[theme_name], use_container_width=True)
                    st.markdown(f"#### {theme_name}")
                    search_query = urllib.parse.quote(f"{theme_name} indian wedding invitation design")
                    render_html(f"""
                    <a href="https://www.google.com/search?tbm=isch&q={search_query}" target="_blank" style="font-size:0.85rem; color:#4A00E0;">\U0001F50D Browse more designs on Google Images</a>
                    """)
                    if st.button(f"Select {theme_name.split()[0]}", key=f"pick_{theme_name}", use_container_width=True):
                        st.session_state.selected_theme = theme_name
                    try:
                        theme_raw = invite_fetch_theme_bytes(theme_name)
                        st.download_button("\u2B07\uFE0F Download this background", data=theme_raw, file_name=f"{theme_name.replace(' ', '_')}.jpg", mime="image/jpeg", key=f"dl_{theme_name}", use_container_width=True)
                    except Exception:
                        pass
                    st.markdown("</div>", unsafe_allow_html=True)

            st.markdown(f"<p style='margin-top:10px;'>\u2705 Selected theme: <b>{st.session_state.selected_theme}</b></p>", unsafe_allow_html=True)
        else:
            st.info("\U0001F4A1 Found a background you love on Google Images or elsewhere? Download it to your device, then upload it here.")
            uploaded_bg_file = st.file_uploader("Upload background image (JPG / PNG)", type=["jpg", "jpeg", "png"], key="banner_bg_upload")
            if uploaded_bg_file:
                uploaded_bg_bytes = uploaded_bg_file.getvalue()
                st.image(uploaded_bg_bytes, caption="Your uploaded background", width=300)

        st.markdown("<br>### **2. Customize Font & Colors (optional)**", unsafe_allow_html=True)
        with st.expander("\U0001F3A8 Leave this untouched for our AI-recommended professional look"):
            fc1, fc2 = st.columns(2)
            banner_font = fc1.selectbox("Font Style", list(INVITE_FONT_STYLES.keys()), key="banner_font")
            banner_color = fc2.selectbox("Color Theme", list(INVITE_COLOR_THEMES.keys()), key="banner_color")

        st.markdown("<br>### **3. Enter Your Invitation Details**", unsafe_allow_html=True)
        with st.form("banner_form"):
            event_type = st.radio("This invitation is for:", ["Engagement", "Wedding"], horizontal=True)
            f_col1, f_col2 = st.columns(2)
            groom_name = f_col1.text_input("Groom's Name", placeholder="e.g., Rahul")
            bride_name = f_col2.text_input("Bride's Name", placeholder="e.g., Anjali")
            p_col1, p_col2 = st.columns(2)
            groom_parents = p_col1.text_input("Groom's Parents' Names", placeholder="e.g., Mr. Ramesh & Mrs. Sunita Sharma")
            bride_parents = p_col2.text_input("Bride's Parents' Names", placeholder="e.g., Mr. Suresh & Mrs. Meena Verma")
            d_col1, d_col2, d_col3 = st.columns(3)
            wedding_date = d_col1.date_input("Date")
            wedding_time = d_col2.time_input("Time")
            ampm_override = d_col3.selectbox("AM / PM", ["Auto (from time above)", "AM", "PM"])
            venue_text = st.text_input("Venue / Location", placeholder="e.g., The Royal Orchid Banquet, Nagpur")
            special_note = st.text_input("Special Note (optional)", placeholder="e.g., RSVP by 1st Dec, Traditional Attire Requested")
            generate_banner = st.form_submit_button("\U0001F3A8 Generate AI Banner (Full HD)", type="primary")

        if generate_banner:
            if not groom_name or not bride_name:
                st.warning("Please enter both names before generating.")
            elif bg_source == "Upload Your Own Background Image" and not uploaded_bg_bytes:
                st.warning("Please upload a background image first, or switch to a Bandhan Theme.")
            else:
                day_name = wedding_date.strftime("%A")
                time_str = wedding_time.strftime("%I:%M %p")
                if ampm_override != "Auto (from time above)":
                    time_str = wedding_time.strftime("%I:%M") + f" {ampm_override}"
                with st.spinner("\U0001F3A8 Generating your Full HD wedding invitation..."):
                    if uploaded_bg_bytes:
                        bg_bytes, used_ai = uploaded_bg_bytes, False
                    else:
                        bg_bytes, used_ai = invite_get_background_bytes(st.session_state.selected_theme, api_key)
                    final_card = invite_overlay_text(bg_bytes, groom_name, bride_name, groom_parents, bride_parents, event_type,
                                                      wedding_date, day_name, time_str, venue_text, special_note,
                                                      font_style=banner_font, color_theme=banner_color)
                st.session_state.banner_invite_bytes = final_card
                st.session_state.banner_invite_created_at = dt.datetime.now()
                st.session_state.banner_invite_filename = f"{groom_name}_{bride_name}_invite_FullHD.png"
                source_note = "your uploaded background" if uploaded_bg_bytes else ("AI-generated art" if used_ai else "themed stock background")
                st.success(f"\u2705 Your Full HD invitation card is ready! ({source_note})")
                st.image(final_card, use_container_width=True)

        invite_render_expiry_gated_download("banner_invite", "Your Saved Invitation Card is Ready to Download", "image/png", "\u2B07\uFE0F")

    with tab2:
        st.markdown("### **Generate an Animated Invite**")
        st.write("Enter your details and we'll build a short animated invite (downloadable GIF) with your names, date, and venue fading in.")

        anim_source = st.radio("Animation source", ["Build from a Bandhan Theme (AI / Stock)", "Upload Your Own Animated GIF"], key="anim_source", horizontal=True)

        uploaded_gif_bytes = None
        if anim_source == "Build from a Bandhan Theme (AI / Stock)":
            v_col1, v_col2 = st.columns(2)
            with v_col1:
                story_style = st.selectbox("Visual Style", ["Royal Heritage", "Modern Minimalist", "Floral Elegance"])
            with v_col2:
                music_vibe = st.selectbox("Background Music Vibe", ["Classical Instrumental", "Bollywood Romantic", "Soft Acoustic", "Upbeat & Fun"])
            st.caption("\u2139\uFE0F Note: the GIF format itself cannot carry audio. This selection is saved as a note for our team when producing a full MP4 video invite with music.")
        else:
            st.info("\U0001F4A1 Have an existing animated GIF (from your phone, Canva, etc.)? Upload it and we'll overlay your invitation text on top of it automatically.")
            uploaded_gif_file = st.file_uploader("Upload your animated GIF", type=["gif"], key="anim_gif_upload")
            if uploaded_gif_file:
                uploaded_gif_bytes = uploaded_gif_file.getvalue()
                st.image(uploaded_gif_bytes, caption="Your uploaded animation", width=300)
            st.caption("\u26A0\uFE0F MP4/video uploads aren't supported yet in this demo \u2014 that needs additional server-side video processing. Please upload a GIF for now.")
            music_vibe = None
            story_style = None

        with st.expander("\U0001F3A8 Customize Font & Colors (optional \u2014 AI default looks professional as-is)"):
            ac1, ac2 = st.columns(2)
            anim_font = ac1.selectbox("Font Style", list(INVITE_FONT_STYLES.keys()), key="anim_font")
            anim_color = ac2.selectbox("Color Theme", list(INVITE_COLOR_THEMES.keys()), key="anim_color")

        with st.form("video_invite_form"):
            v_event_type = st.radio("This invitation is for:", ["Engagement", "Wedding"], horizontal=True, key="v_event_type")
            vf_col1, vf_col2 = st.columns(2)
            v_groom = vf_col1.text_input("Groom's Name", placeholder="e.g., Rahul", key="v_groom")
            v_bride = vf_col2.text_input("Bride's Name", placeholder="e.g., Anjali", key="v_bride")
            vp_col1, vp_col2 = st.columns(2)
            v_groom_parents = vp_col1.text_input("Groom's Parents' Names", placeholder="e.g., Mr. Ramesh & Mrs. Sunita Sharma", key="v_groom_parents")
            v_bride_parents = vp_col2.text_input("Bride's Parents' Names", placeholder="e.g., Mr. Suresh & Mrs. Meena Verma", key="v_bride_parents")
            vd_col1, vd_col2, vd_col3 = st.columns(3)
            v_date = vd_col1.date_input("Date", key="v_date")
            v_time = vd_col2.time_input("Time", key="v_time")
            v_ampm_override = vd_col3.selectbox("AM / PM", ["Auto (from time above)", "AM", "PM"], key="v_ampm")
            v_venue = st.text_input("Venue / Location", placeholder="e.g., The Royal Orchid Banquet, Nagpur", key="v_venue")
            v_special_note = st.text_input("Special Note (optional)", placeholder="e.g., RSVP by 1st Dec, Traditional Attire Requested", key="v_special_note")
            how_we_met = st.text_area("Tell us briefly how you met (shown in the storyboard notes):", placeholder="We met in college...")
            generate_gif = st.form_submit_button("\U0001F3AC Generate Animated Invite (GIF)", type="primary")

        if generate_gif:
            if not v_groom or not v_bride:
                st.warning("Please enter both names before generating.")
            elif anim_source == "Upload Your Own Animated GIF" and not uploaded_gif_bytes:
                st.warning("Please upload a GIF first, or switch to a Bandhan Theme.")
            else:
                v_day_name = v_date.strftime("%A")
                v_time_str = v_time.strftime("%I:%M %p")
                if v_ampm_override != "Auto (from time above)":
                    v_time_str = v_time.strftime("%I:%M") + f" {v_ampm_override}"
                with st.spinner("\U0001F3AC Generating your animated invite..."):
                    if uploaded_gif_bytes:
                        gif_bytes = invite_overlay_text_on_uploaded_gif(uploaded_gif_bytes, v_groom, v_bride, v_event_type, v_date, v_day_name, v_time_str, v_venue, color_theme=anim_color)
                        used_ai = False
                    else:
                        bg_bytes, used_ai = invite_get_background_bytes(story_style, api_key)
                        gif_bytes = invite_build_animated_gif(bg_bytes, v_groom, v_bride, v_groom_parents, v_bride_parents, v_event_type,
                                                               v_date, v_day_name, v_time_str, v_venue, v_special_note, font_style=anim_font, color_theme=anim_color)
                st.session_state.animated_invite_bytes = gif_bytes
                st.session_state.animated_invite_created_at = dt.datetime.now()
                st.session_state.animated_invite_filename = f"{v_groom}_{v_bride}_animated_invite.gif"
                source_note = "your uploaded animation" if uploaded_gif_bytes else ("AI-generated art" if used_ai else "themed stock background")
                st.success(f"\u2705 Animated Invite Ready & Saved! ({source_note})")
                st.image(gif_bytes, use_container_width=True)
                if story_style:
                    st.markdown(f"""
                    <div style='background-color: white; padding: 20px; border-radius: 10px; border-left: 5px solid #4A00E0; margin-top:15px;'>
                        <h4>\U0001F3A5 Storyboard Notes</h4>
                        <p><b>Style:</b> {story_style} | <b>Suggested Music:</b> {music_vibe}</p>
                        <p><i>"{how_we_met}"</i></p>
                    </div>
                    """, unsafe_allow_html=True)
                st.button("\u2699\uFE0F Send to Rendering Engine (Export MP4 with Music)")

        invite_render_expiry_gated_download("animated_invite", "Your Saved Animated Invite is Ready to Download", "image/gif", "\u2B07\uFE0F")


# =====================================================================
# PAGE: WEDDING COUNTDOWN TRACKER
# =====================================================================
def page_wedding_countdown():
    render_global_css(bg_color="#FFFDF8", page_css=""".countdown-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); padding: 35px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.countdown-num { font-size: 3.5rem; font-weight: 900; color: #D4AF37; }
.task-card { background: white; padding: 14px 18px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 10px; border-left: 4px solid #27AE60; }""")

    st.markdown("""
    <div class="countdown-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\u23F3 Wedding Countdown & Planning Tracker</h1>
        <p style="color:#FBF5B7; margin-top:8px;">For matched couples — track your wedding date and shared to-do list together.</p>
    </div>
    """, unsafe_allow_html=True)

    wedding_date = st.date_input("Your Wedding Date", value=datetime.date.today() + datetime.timedelta(days=120))
    days_left = (wedding_date - datetime.date.today()).days
    st.markdown(f"<div style='text-align:center;'><div class='countdown-num'>{max(days_left, 0)}</div><p style='color:gray;'>Days to go</p></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4CB Wedding Services Checklist")
    st.write("Track which services you've booked. Anything not booked yet shows a reminder with a direct button to browse verified vendors.")

    SERVICE_LIST = [
        "Wedding Planner / Management", "Banquet Hall / Lawn / Resort", "Designer Wedding Apparel",
        "Wedding Jewelry & Ornaments", "Makeup Artist & Grooming", "Photography & Videography",
        "Mandap, Stage & Floral Decoration", "Catering & Food Service", "Music, DJ & Entertainment",
        "Wedding Invitations & Digital Cards", "Transportation Services", "Baraat: Ghodi, Buggy & Band",
        "Vedic Priest & Ritual Services",
    ]
    VENDOR_DIRECTORY = {
        "Wedding Planner / Management": [{"name": "Royal Events & Management Co.", "city": "Nagpur", "rating": 4.8, "phone": "+91-98XXXXXX01"}],
        "Banquet Hall / Lawn / Resort": [{"name": "The Grand Orchid Banquets", "city": "Nagpur", "rating": 4.6, "phone": "+91-98XXXXXX02"}],
        "Designer Wedding Apparel": [{"name": "Meera Designer Studio", "city": "Pune", "rating": 4.7, "phone": "+91-98XXXXXX03"}],
        "Wedding Jewelry & Ornaments": [{"name": "Suvarna Jewels", "city": "Mumbai", "rating": 4.9, "phone": "+91-98XXXXXX04"}],
        "Makeup Artist & Grooming": [{"name": "Glow & Grace Makeovers", "city": "Nagpur", "rating": 4.5, "phone": "+91-98XXXXXX05"}],
        "Photography & Videography": [{"name": "Frame & Story Films", "city": "Bangalore", "rating": 4.8, "phone": "+91-98XXXXXX06"}],
        "Mandap, Stage & Floral Decoration": [{"name": "Floral Dreams Decor", "city": "Nagpur", "rating": 4.6, "phone": "+91-98XXXXXX07"}],
        "Catering & Food Service": [{"name": "Swaad Caterers", "city": "Pune", "rating": 4.7, "phone": "+91-98XXXXXX08"}],
        "Music, DJ & Entertainment": [{"name": "Beats & Baraat DJ Co.", "city": "Nagpur", "rating": 4.4, "phone": "+91-98XXXXXX09"}],
        "Wedding Invitations & Digital Cards": [{"name": "PrintCraft Invitations", "city": "Mumbai", "rating": 4.5, "phone": "+91-98XXXXXX10"}],
        "Transportation Services": [{"name": "Royal Fleet Transport", "city": "Nagpur", "rating": 4.3, "phone": "+91-98XXXXXX11"}],
        "Baraat: Ghodi, Buggy & Band": [{"name": "Shahi Baraat Services", "city": "Nagpur", "rating": 4.6, "phone": "+91-98XXXXXX12"}],
        "Vedic Priest & Ritual Services": [{"name": "Acharya Ritual Services", "city": "Nagpur", "rating": 4.9, "phone": "+91-98XXXXXX13"}],
    }

    if "service_booked" not in st.session_state:
        st.session_state.service_booked = {s: False for s in SERVICE_LIST}
    if "show_vendors_for" not in st.session_state:
        st.session_state.show_vendors_for = None

    for service in SERVICE_LIST:
        row1, row2 = st.columns([4, 1])
        with row1:
            booked = st.checkbox(service, value=st.session_state.service_booked[service], key=f"svc_{service}")
            st.session_state.service_booked[service] = booked
        with row2:
            if not booked:
                if st.button("\U0001F50D Find Vendors", key=f"find_{service}", use_container_width=True):
                    st.session_state.show_vendors_for = service

        if not booked:
            st.warning(f"\u23F0 Reminder: **{service}** is not booked yet. Book soon to stay on schedule!")

        if st.session_state.show_vendors_for == service:
            st.markdown(f"<div style='background:white; padding:14px; border-radius:10px; border-left:4px solid #D4AF37; margin-bottom:10px;'>", unsafe_allow_html=True)
            st.markdown(f"**Verified Vendors for {service}:**")
            for v in VENDOR_DIRECTORY.get(service, []):
                vc1, vc2, vc3 = st.columns([3, 1, 2])
                vc1.markdown(f"{v['name']} \u2705 <span style='color:gray; font-size:0.85rem;'>({v['city']})</span>", unsafe_allow_html=True)
                vc2.markdown(f"\u2B50 {v['rating']}")
                b1, b2 = vc3.columns(2)
                b1.button("\U0001F4DE Call", key=f"tcall_{service}_{v['name']}", use_container_width=True)
                b2.button("\U0001F4AC Msg", key=f"tmsg_{service}_{v['name']}", use_container_width=True)
            if st.button("Close", key=f"close_{service}"):
                st.session_state.show_vendors_for = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4DD Other To-Dos")

    if "wedding_tasks" not in st.session_state:
        st.session_state.wedding_tasks = [
            {"task": "Finalize guest list", "done": True},
            {"task": "Send invitations", "done": False},
        ]

    for i, t in enumerate(st.session_state.wedding_tasks):
        checked = st.checkbox(t["task"], value=t["done"], key=f"task_{i}")
        st.session_state.wedding_tasks[i]["done"] = checked

    with st.form("add_task_form"):
        new_task = st.text_input("Add a new task")
        add_task = st.form_submit_button("\u2795 Add Task")
        if add_task and new_task:
            st.session_state.wedding_tasks.append({"task": new_task, "done": False})
            st.rerun()

    services_booked_count = sum(1 for v in st.session_state.service_booked.values() if v)
    other_completed = sum(1 for t in st.session_state.wedding_tasks if t["done"])
    total_items = len(SERVICE_LIST) + len(st.session_state.wedding_tasks)
    total_done = services_booked_count + other_completed
    st.progress(total_done / total_items if total_items else 0)
    st.caption(f"{total_done} of {total_items} items completed ({services_booked_count}/{len(SERVICE_LIST)} services booked)")


# =====================================================================
# PAGE: VENDOR REGISTRATION
# =====================================================================
def page_vendor_registration():
    render_global_css(bg_color="#F8F9FA", page_css=""".vendor-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.vendor-card { background: white; padding: 28px; border-radius: 16px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; }
.otp-box { background: #FFF8E1; border-left: 5px solid #D4AF37; padding: 16px 20px; border-radius: 10px; margin-top: 10px; }
.verified-badge { background: #DCFCE7; color: #166534; padding: 10px 18px; border-radius: 10px; font-weight: 700; text-align: center; }""")

    if st.session_state.user_role not in ("boss", "vendor"):
        st.error("\U0001F6AB Your account doesn't have permission to view this page.")
        if st.button("\u2190 Back to Home"):
            go_to("home")
        return

    render_html("""
    <div class="vendor-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F9D1\u200D\U0001F4BC Vendor Registration</h1>
        <p style="color:#FBF5B7; margin-top:8px;">List your wedding service or finance business on Bandhan. Every vendor is document-verified before going live.</p>
    </div>
    """)

    if "vendor_otp" not in st.session_state:
        st.session_state.vendor_otp = None
    if "vendor_otp_verified" not in st.session_state:
        st.session_state.vendor_otp_verified = False

    st.markdown("<div class='vendor-card'>", unsafe_allow_html=True)

    st.markdown("### Step 1: Business Details")
    vendor_type = st.selectbox("What are you registering as?", [
        "Wedding Planner / Management Agency", "Banquet Hall / Lawn / Resort", "Designer Wedding Apparel",
        "Wedding Jewelry & Ornaments", "Makeup Artist & Grooming", "Photography & Videography",
        "Mandap, Stage & Floral Decoration", "Catering & Food Service", "Music, DJ & Entertainment",
        "Wedding Invitations & Digital Cards", "Transportation Services", "Baraat: Ghodi, Buggy & Band",
        "Vedic Priest & Ritual Services", "Wedding Finance / Loan Provider (Bank / NBFC)"
    ])

    col1, col2 = st.columns(2)
    with col1:
        business_name = st.text_input("Business / Shop Name")
        owner_name = st.text_input("Owner's Full Name")
        shop_number = st.text_input("Shop / Office Number & Address")
    with col2:
        contact_number = st.text_input("Business Contact Number")
        business_email = st.text_input("Business Email")
        city = st.text_input("City / Location")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Step 2: Identity & Business Documents")
    doc_col1, doc_col2 = st.columns(2)
    with doc_col1:
        aadhar_number = st.text_input("Aadhaar Card Number", max_chars=12, placeholder="12-digit Aadhaar number")
        pan_number = st.text_input("PAN Card Number", max_chars=10, placeholder="ABCDE1234F")
    with doc_col2:
        gst_number = st.text_input("GST Number (if applicable)", placeholder="Leave blank if not registered")
        license_number = st.text_input("Trade / Shop License Number (if applicable)", placeholder="Leave blank if not applicable")

    doc_upload = st.file_uploader("Upload Aadhaar / PAN / License (photo or PDF)", type=['jpg', 'png', 'jpeg', 'pdf'])

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Step 3: OTP Verification")
    st.write("To prevent fake vendor listings, we verify your identity with an OTP sent to your Aadhaar/PAN-linked mobile number.")

    otp_mobile = st.text_input("Mobile Number linked to Aadhaar/PAN", max_chars=10, placeholder="10-digit mobile number")

    send_otp_col, verify_col = st.columns([1, 2])
    with send_otp_col:
        if st.button("\U0001F4F2 Send OTP", use_container_width=True):
            if aadhar_number and pan_number and otp_mobile and len(otp_mobile) == 10:
                st.session_state.vendor_otp = str(random.randint(100000, 999999))
                st.session_state.vendor_otp_verified = False
            else:
                st.warning("\u26A0\uFE0F Please fill Aadhaar, PAN, and a valid 10-digit mobile number first.")

    if st.session_state.vendor_otp:
        render_html(f"""
        <div class="otp-box">
        \U0001F4E9 <b>Demo Mode:</b> In production this OTP is sent via SMS to <b>{otp_mobile}</b> using an SMS/Aadhaar-eKYC provider (e.g. MSG91, Twilio). For this demo, your OTP is: <b style="color:#D4AF37; font-size:1.2rem;">{st.session_state.vendor_otp}</b>
        </div>
        """)
        with verify_col:
            entered_otp = st.text_input("Enter the 6-digit OTP", max_chars=6, key="otp_entry")
            if st.button("\u2705 Verify OTP", type="primary", use_container_width=True):
                if entered_otp == st.session_state.vendor_otp:
                    st.session_state.vendor_otp_verified = True
                    st.success("\u2705 OTP Verified! Your identity has been confirmed.")
                else:
                    st.error("\u274C Incorrect OTP. Please try again.")

    if st.session_state.vendor_otp_verified:
        render_html("<div class='verified-badge'>\U0001F6E1\uFE0F Identity Verified — Ready to Submit</div>")

    st.markdown("<br>", unsafe_allow_html=True)
    agree_terms = st.checkbox("I confirm all details provided are accurate and I agree to Bandhan's Vendor Terms & Conditions.")

    if st.button("\U0001F680 Submit Vendor Registration", type="primary", use_container_width=True):
        missing = []
        if not business_name: missing.append("Business Name")
        if not owner_name: missing.append("Owner Name")
        if not aadhar_number: missing.append("Aadhaar Number")
        if not pan_number: missing.append("PAN Number")
        if not doc_upload: missing.append("Document Upload")
        if not st.session_state.vendor_otp_verified: missing.append("OTP Verification")
        if not agree_terms: missing.append("Terms Agreement")

        if missing:
            st.error("\u26A0\uFE0F Please complete the following before submitting: " + ", ".join(missing))
        else:
            st.balloons()
            st.success(f"\U0001F389 Congratulations {owner_name}! **{business_name}** has been submitted for review. Once approved by our Trust & Safety team, you'll appear in the {vendor_type} listings with a Verified badge.")

    st.markdown("</div>", unsafe_allow_html=True)
    st.info("\U0001F4A1 Already registered? Approved vendors appear automatically under their category on the Wedding Services and Wedding Finance pages, where couples can call or message them directly.")


# =====================================================================
# PAGE: SUCCESS STORIES
# =====================================================================
STORY_STATE_DISTRICTS = KUNDLI_STATE_DISTRICTS
STORY_ALL_STATES = KUNDLI_ALL_STATES
MAX_PHOTO_MB = 10


def story_process_cinematic_photo(uploaded_file):
    raw_bytes = uploaded_file.getvalue()
    size_mb = len(raw_bytes) / (1024 * 1024)
    if size_mb > MAX_PHOTO_MB:
        return None, size_mb

    img = Image.open(BytesIO(raw_bytes)).convert("RGB")
    canvas_w, canvas_h = 1920, 1080
    img_ratio = img.width / img.height
    canvas_ratio = canvas_w / canvas_h

    if img_ratio > canvas_ratio:
        new_w = canvas_w
        new_h = int(canvas_w / img_ratio)
    else:
        new_h = canvas_h
        new_w = int(canvas_h * img_ratio)

    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
    canvas.paste(resized, ((canvas_w - new_w) // 2, (canvas_h - new_h) // 2))

    buf = BytesIO()
    canvas.save(buf, format="JPEG", quality=95)
    return buf.getvalue(), size_mb


def page_success_stories():
    render_global_css(bg_color="#F8F9FA", page_css=""".stories-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 30px; border-radius: 20px; color: white; text-align: center; box-shadow: 0 15px 35px rgba(0,0,0,0.2); border: 2px solid #D4AF37; margin-bottom: 30px; }
.stories-title { font-family: 'Georgia', serif; font-size: 2.8rem; font-weight: 900; margin: 0; background: linear-gradient(to right, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.header-flank-img { width: 100%; height: 140px; object-fit: cover; border-radius: 14px; box-shadow: 0 8px 20px rgba(0,0,0,0.3); border: 2px solid #D4AF37; }
.story-card { background: white; border-radius: 15px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border: 1px solid #EAEAEA; border-top: 6px solid #D4AF37; margin-bottom: 25px; transition: transform 0.3s ease; }
.story-card:hover { transform: translateY(-5px); box-shadow: 0 15px 30px rgba(212, 175, 55, 0.25); }
.couple-name { color: #1A365D; font-family: 'Georgia', serif; font-size: 1.5rem; font-weight: bold; margin-bottom: 5px; }
.story-date { color: #718096; font-size: 0.9rem; margin-bottom: 15px; }
.story-quote { color: #334155; font-size: 1rem; line-height: 1.6; font-style: italic; }
.share-box { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); color: white; padding: 30px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); margin-top: 40px; }
.cinematic-frame { background: #000; border-radius: 12px; padding: 0; overflow: hidden; box-shadow: 0 12px 30px rgba(0,0,0,0.35); }""")

    h_left, h_center, h_right = st.columns([1, 2.2, 1])
    with h_left:
        st.markdown("<img class='header-flank-img' src='https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=800&q=90'>", unsafe_allow_html=True)
    with h_center:
        st.markdown("""
        <div class="stories-header">
            <h1 class="stories-title">Bandhan Success Stories</h1>
            <p style="font-size:1.1rem; margin-top:12px; color:#FBF5B7; font-style:italic;">Real couples, real connections, and happily ever afters made possible through Bandhan.</p>
        </div>
        """, unsafe_allow_html=True)
    with h_right:
        st.markdown("<img class='header-flank-img' src='https://images.unsplash.com/photo-1583939003579-730e3918a45a?auto=format&fit=crop&w=800&q=90'>", unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("""
        <div class="story-card">
            <img src="https://images.unsplash.com/photo-1583939003579-730e3918a45a?auto=format&fit=crop&w=600&q=80" style="width:100%; border-radius:10px; margin-bottom:15px; height:220px; object-fit:cover;">
            <div class="couple-name">Rahul & Priya Sharma</div>
            <div class="story-date">\U0001F4C5 Married on: 14th February 2026 | Nagpur</div>
            <div class="story-quote">"We found each other through Bandhan's secure matching and privacy features. The platform made it so easy to connect with families, check kundlis, and plan our dream wedding seamlessly. Thank you Bandhan for giving us our happily ever after!"</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="story-card">
            <img src="https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=600&q=80" style="width:100%; border-radius:10px; margin-bottom:15px; height:220px; object-fit:cover;">
            <div class="couple-name">Amit & Neha Verma</div>
            <div class="story-date">\U0001F4C5 Married on: 28th November 2025 | Pune</div>
            <div class="story-quote">"The verified profiles and secure in-app calling gave us immense confidence. We used the Bandhan Budget Calculator and Wedding Services planner to execute everything without any stress. Highly recommended!"</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="story-card">
            <img src="https://images.unsplash.com/photo-1511285560929-80b456fea0bc?auto=format&fit=crop&w=600&q=80" style="width:100%; border-radius:10px; margin-bottom:15px; height:220px; object-fit:cover;">
            <div class="couple-name">Vikram & Pooja Patil</div>
            <div class="story-date">\U0001F4C5 Married on: 10th January 2026 | Mumbai</div>
            <div class="story-quote">"Finding a life partner who shares the same values and goals was effortless here. The matchmaking algorithm is top-notch. Our families met and everything clicked instantly. Eternally grateful to Bandhan!"</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="story-card">
            <img src="https://images.unsplash.com/photo-1519225421980-715cb0215aed?auto=format&fit=crop&w=600&q=80" style="width:100%; border-radius:10px; margin-bottom:15px; height:220px; object-fit:cover;">
            <div class="couple-name">Rohan & Ananya Gupta</div>
            <div class="story-date">\U0001F4C5 Married on: 5th May 2025 | Bangalore</div>
            <div class="story-quote">"From our first secure call to booking our wedding venue through Bandhan's ecosystem, the journey was magical. Best matchmaking and planning platform ever!"</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="share-box">
        <h2 style="color:#D4AF37; margin-top:0; font-family:'Georgia', serif;">\U0001F496 Share Your Success Story</h2>
        <p style="color:#E2E8F0;">Did you find your soulmate through Bandhan? Share your journey with us and inspire thousands of others!</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("success_story_form"):
        s_col1, s_col2 = st.columns(2)
        with s_col1:
            groom_name = st.text_input("Groom's Name")
            bride_name = st.text_input("Bride's Name")
            marriage_date = st.date_input("Date of Marriage")
            contact_email = st.text_input("Email / Mobile Number")
        with s_col2:
            city_name = st.text_input("Wedding City", placeholder="Type your city (any city in India)")
            wedding_state = st.selectbox("State", STORY_ALL_STATES)
            wedding_district = st.selectbox("District", STORY_STATE_DISTRICTS[wedding_state])
            venue_name = st.text_input("Venue of Marriage", placeholder="e.g., The Royal Orchid Banquet")

        story_text = st.text_area("Your Love & Success Story", placeholder="Write about how you met on Bandhan and your wedding experience...")
        couple_photo = st.file_uploader(f"Upload Your Couple Photo (max {MAX_PHOTO_MB} MB)", type=["jpg", "jpeg", "png"])
        submitted = st.form_submit_button("\U0001F4E4 Submit Your Success Story", type="primary")

        if submitted:
            if not (groom_name and bride_name and story_text):
                st.warning("Please fill in the essential details (Names and Story) before submitting.")
            elif couple_photo is None:
                st.warning("Please upload a couple photo to complete your submission.")
            else:
                processed_bytes, size_mb = story_process_cinematic_photo(couple_photo)
                if processed_bytes is None:
                    st.error(f"\u26A0\uFE0F Your photo is {size_mb:.1f} MB, which is over the {MAX_PHOTO_MB} MB limit. Please upload a smaller file.")
                else:
                    st.balloons()
                    st.components.v1.html("""
                    <div style="text-align:center; padding:20px; font-family:'Georgia', serif; overflow:hidden; position:relative; height:260px;">
                        <style>
                        @keyframes popIn { 0% { transform:scale(0.3); opacity:0; } 60% { transform:scale(1.1); opacity:1; } 100% { transform:scale(1); } }
                        @keyframes glowPulse { 0%,100% { text-shadow:0 0 10px #D4AF37,0 0 20px #FF416C; } 50% { text-shadow:0 0 25px #D4AF37,0 0 45px #FF4B2B; } }
                        @keyframes fallDown { 0% { transform:translateY(-40px) rotate(0deg); opacity:1; } 100% { transform:translateY(300px) rotate(360deg); opacity:0; } }
                        .confetti-piece { position:absolute; top:0; font-size:28px; animation: fallDown linear infinite; }
                        .congrats-text { font-size:2.2rem; font-weight:900; background:linear-gradient(90deg,#FF416C,#FF4B2B,#D4AF37,#1A365D,#FF416C); background-size:300% 300%; -webkit-background-clip:text; -webkit-text-fill-color:transparent; animation: popIn 0.8s ease-out, glowPulse 1.8s ease-in-out infinite 0.8s; margin-top:70px; }
                        .bestluck-text { font-size:1.6rem; font-weight:800; color:#1A365D; margin-top:14px; animation: popIn 1s ease-out 0.3s both; }
                        </style>
                        <div class="confetti-piece" style="left:5%; animation-duration:2.2s;">\U0001F38A</div>
                        <div class="confetti-piece" style="left:18%; animation-duration:2.6s; animation-delay:0.2s;">\U0001F389</div>
                        <div class="confetti-piece" style="left:32%; animation-duration:2.1s; animation-delay:0.4s;">\U0001F38A</div>
                        <div class="confetti-piece" style="left:48%; animation-duration:2.5s; animation-delay:0.1s;">\U0001F38A</div>
                        <div class="confetti-piece" style="left:63%; animation-duration:2.3s; animation-delay:0.3s;">\U0001F389</div>
                        <div class="confetti-piece" style="left:78%; animation-duration:2.7s; animation-delay:0.5s;">\U0001F38A</div>
                        <div class="confetti-piece" style="left:90%; animation-duration:2.2s; animation-delay:0.15s;">\U0001F389</div>
                        <div class="congrats-text">\U0001F38A Congratulations for Your Future Life! \U0001F38A</div>
                        <div class="bestluck-text">Best of luck! \U0001F44D</div>
                    </div>
                    <script>
                    (function() {
                        try {
                            const ctx = new (window.AudioContext || window.webkitAudioContext)();
                            function clapBurst(delay) {
                                setTimeout(function() {
                                    const bufferSize = ctx.sampleRate * 0.08;
                                    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
                                    const data = buffer.getChannelData(0);
                                    for (let i = 0; i < bufferSize; i++) {
                                        data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize);
                                    }
                                    const noise = ctx.createBufferSource();
                                    noise.buffer = buffer;
                                    const gain = ctx.createGain();
                                    gain.gain.value = 0.5;
                                    const filter = ctx.createBiquadFilter();
                                    filter.type = "highpass";
                                    filter.frequency.value = 1000;
                                    noise.connect(filter).connect(gain).connect(ctx.destination);
                                    noise.start();
                                }, delay);
                            }
                            for (let i = 0; i < 18; i++) {
                                clapBurst(Math.random() * 1800);
                            }
                        } catch (e) {}
                    })();
                    </script>
                    """, height=280)
                    st.success("\U0001F389 Thank you for sharing your story! Our team will verify and publish it on the Bandhan portal soon.")
                    st.markdown(f"<p style='color:gray; font-size:0.85rem;'>{wedding_district}, {wedding_state} \u2022 {venue_name or 'Venue not specified'}</p>", unsafe_allow_html=True)
                    st.markdown("#### \U0001F3AC Your Photo \u2014 Full HD Cinematic Preview")
                    st.markdown("<div class='cinematic-frame'>", unsafe_allow_html=True)
                    st.image(processed_bytes, use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: AI COMPATIBILITY SCORE
# =====================================================================
def page_ai_compatibility():
    render_global_css(bg_color="#F8F9FA", page_css=""".forecast-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.big-score { font-size: 5rem; font-weight: 900; color: #27AE60; text-align: center; margin: 10px 0; }
.factor-card { background: white; padding: 18px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #D4AF37; margin-bottom: 12px; }""")

    st.markdown("""
    <div class="forecast-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F9E0 AI Relationship Forecast</h1>
        <p style="color:#FBF5B7; margin-top:8px;">One unified score combining Kundli, Quiz answers, and profile compatibility — not just astrology, not just filters.</p>
    </div>
    """, unsafe_allow_html=True)

    profile_pick = st.selectbox("Select a match to analyze", ["Ritu Deshmukh (96% filter match)", "Sneha Patil (92% filter match)", "Ananya Rao (89% filter match)"])

    if st.button("\U0001F52E Generate Unified Forecast", type="primary", use_container_width=True):
        with st.spinner("Combining Kundli Guna score, quiz answers, and lifestyle data..."):
            pass
        st.markdown("<div class='big-score'>91%</div>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#27AE60; font-weight:bold; font-size:1.1rem;'>Excellent Long-Term Compatibility</p>", unsafe_allow_html=True)

        st.markdown("### How this score was calculated")
        factors = [
            ("\U0001F549\uFE0F Kundli Guna Milan", "28.5 / 36", "Strong astrological alignment, no major dosha."),
            ("\U0001F9E9 Values & Lifestyle Quiz", "94% match", "Both prioritize family, similar social energy levels."),
            ("\U0001F3E1 Family Background", "Aligned", "Similar community, comparable family values."),
            ("\U0001F4BC Career & Ambition", "88% match", "Both career-focused with balanced approach to family time."),
        ]
        for title, score, note in factors:
            st.markdown(f"""
            <div class="factor-card">
                <b>{title}</b> — <span style="color:#27AE60; font-weight:bold;">{score}</span><br>
                <span style="color:gray; font-size:0.9rem;">{note}</span>
            </div>
            """, unsafe_allow_html=True)

        st.info("\U0001F4A1 This forecast is a data-driven suggestion, not a guarantee. Use it alongside conversations and family input.")


# =====================================================================
# PAGE: AI ICEBREAKER
# =====================================================================
def page_ai_icebreaker():
    render_global_css(bg_color="#F8F9FA", page_css=""".ice-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.ice-suggestion { background: white; padding: 16px 20px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #2563EB; margin-bottom: 12px; }""")

    st.markdown("""
    <div class="ice-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F9CA AI Icebreaker Suggestions</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Stuck on what to say first? Let AI suggest openers based on shared interests.</p>
    </div>
    """, unsafe_allow_html=True)

    match_pick = st.selectbox("Generate icebreakers for", ["Priya Sharma", "Aisha Khan", "Ritu Deshmukh"])

    if st.button("\u2728 Generate Icebreakers", type="primary", use_container_width=True):
        st.markdown(f"### Suggested openers for {match_pick}")
        suggestions = [
            "I noticed we both love weekend treks — what's the best trail you've done so far?",
            "Your profile mentioned you're into classical music too! Any favorite artists or ragas?",
            "We both listed 'family-oriented' as a top value — curious what that looks like day-to-day for you.",
            "Saw you're a Chartered Accountant — I'd love to hear what got you into that field.",
        ]
        for s in suggestions:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"<div class='ice-suggestion'>\U0001F4AC {s}</div>", unsafe_allow_html=True)
            c2.button("Use This", key=f"use_{s[:15]}")

        st.caption("Suggestions are generated based on shared profile interests, not personal messages.")


# =====================================================================
# PAGE: BOOST VISIBILITY
# =====================================================================
def page_boost_visibility():
    render_global_css(bg_color="#F8F9FA", page_css=""".boost-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.boost-plan-card { background: white; padding: 26px; border-radius: 16px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; border-top: 5px solid #D4AF37; text-align: center; }
.boost-active-badge { background: #DCFCE7; color: #166534; padding: 12px 20px; border-radius: 10px; font-weight: 700; text-align: center; margin-top: 15px; }""")

    st.markdown("""
    <div class="boost-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F680 Boost Visibility</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Get seen first. Boost your profile or your vendor listing to the top of search results.</p>
    </div>
    """, unsafe_allow_html=True)

    if not render_tnc_gate("payment", "\U0001F4C4 Please Accept Our Terms & Conditions to Continue", "Before purchasing any Boost plan, please read and accept our Terms & Conditions — especially Section 3 (Payment & No-Refund Policy)."):
        return

    if "client_boost_active" not in st.session_state:
        st.session_state.client_boost_active = None
    if "vendor_boost_active" not in st.session_state:
        st.session_state.vendor_boost_active = None

    tab1, tab2 = st.tabs(["\U0001F464 Boost My Profile (Client)", "\U0001F3EA Boost My Vendor Listing"])

    with tab1:
        st.write("Boosted profiles appear at the top of Search Partner and Recommended Matches results, with a highlighted border.")
        st.markdown("<br>", unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        plans = [
            {"label": "24 Hours", "price": "\u20b9 99", "reach": "Up to 5x more views"},
            {"label": "3 Days", "price": "\u20b9 249", "reach": "Up to 8x more views"},
            {"label": "7 Days", "price": "\u20b9 499", "reach": "Up to 12x more views"},
        ]
        cols = [c1, c2, c3]
        for col, plan in zip(cols, plans):
            with col:
                st.markdown(f"""
                <div class="boost-plan-card">
                    <h3>{plan['label']}</h3>
                    <div style="font-size:1.8rem; color:#27AE60; font-weight:900; margin:10px 0;">{plan['price']}</div>
                    <p style="color:gray; font-size:0.9rem;">{plan['reach']}</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Activate {plan['label']} Boost", key=f"client_boost_{plan['label']}", use_container_width=True):
                    st.session_state.client_boost_active = plan['label']

        if st.session_state.client_boost_active:
            render_html(f"<div class='boost-active-badge'>\u2705 Your profile boost is active for {st.session_state.client_boost_active}. You'll appear at the top of search results.</div>")
            st.caption("Demo mode: this simulates activation. Real payment integration requires a payment gateway (Razorpay/Stripe).")

    with tab2:
        st.write("Boosted vendors appear at the top of the Verified Vendors Directory in their category.")
        st.markdown("<br>", unsafe_allow_html=True)

        vendor_name = st.text_input("Your Registered Business Name", placeholder="e.g., Royal Events & Management Co.")

        v1, v2, v3 = st.columns(3)
        vplans = [
            {"label": "3 Days", "price": "\u20b9 499", "reach": "Top of category listing"},
            {"label": "7 Days", "price": "\u20b9 999", "reach": "Top of category + Home page feature"},
            {"label": "30 Days", "price": "\u20b9 2,999", "reach": "Top placement + Featured badge everywhere"},
        ]
        vcols = [v1, v2, v3]
        for col, plan in zip(vcols, vplans):
            with col:
                st.markdown(f"""
                <div class="boost-plan-card">
                    <h3>{plan['label']}</h3>
                    <div style="font-size:1.8rem; color:#27AE60; font-weight:900; margin:10px 0;">{plan['price']}</div>
                    <p style="color:gray; font-size:0.9rem;">{plan['reach']}</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Activate {plan['label']} Vendor Boost", key=f"vendor_boost_{plan['label']}", use_container_width=True):
                    if vendor_name:
                        st.session_state.vendor_boost_active = (vendor_name, plan['label'])
                    else:
                        st.warning("Please enter your registered business name first.")

        if st.session_state.vendor_boost_active:
            vname, vlabel = st.session_state.vendor_boost_active
            render_html(f"<div class='boost-active-badge'>\u2705 {vname}'s listing is boosted for {vlabel}. It will now appear at the top of its category.</div>")
            st.caption("Demo mode: this simulates activation. Real payment integration requires a payment gateway (Razorpay/Stripe).")


# =====================================================================
# PAGE: REFERRAL PROGRAM
# =====================================================================
def page_referral_program():
    render_global_css(bg_color="#F8F9FA", page_css=""".referral-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); padding: 35px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.referral-code-box { background: white; border: 2px dashed #D4AF37; border-radius: 12px; padding: 20px; text-align: center; font-size: 1.6rem; font-weight: 900; color: #1A365D; letter-spacing: 3px; margin-bottom: 20px; }
.reward-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border-top: 4px solid #D4AF37; text-align: center; }""")

    st.markdown("""
    <div class="referral-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F381 Refer & Earn</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Invite friends to Bandhan. Both of you get rewarded when they join!</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1.3, 1], gap="large")

    with col1:
        st.markdown("### Your Unique Referral Code")
        st.markdown("<div class='referral-code-box'>BND-PRIYA24X</div>", unsafe_allow_html=True)

        share_col1, share_col2, share_col3 = st.columns(3)
        share_col1.button("\U0001F4F1 Share on WhatsApp", use_container_width=True)
        share_col2.button("\U0001F4E7 Share via Email", use_container_width=True)
        share_col3.button("\U0001F517 Copy Link", use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### How it Works")
        st.markdown("""
        1. Share your referral code with friends or family looking for a match.
        2. They sign up and complete registration using your code.
        3. Once they verify KYC, you both receive rewards instantly.
        """)

    with col2:
        st.markdown("### \U0001F3C6 Your Rewards")
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("<div class='reward-card'><h2 style='color:#27AE60; margin:0;'>4</h2><p style='margin:0; color:gray;'>Successful Referrals</p></div>", unsafe_allow_html=True)
        with r2:
            st.markdown("<div class='reward-card'><h2 style='color:#D4AF37; margin:0;'>\u20b91,200</h2><p style='margin:0; color:gray;'>Wallet Credit Earned</p></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.info("\U0001F4A1 Every successful referral gives you \u20b9300 wallet credit, redeemable against any VIP plan upgrade.")

    st.markdown("---")
    st.markdown("### \U0001F465 Your Referral History")
    history = [
        ("Rohan Mehta", "Joined \u2705", "\u20b9300 credited"),
        ("Ananya Rao", "Joined \u2705", "\u20b9300 credited"),
        ("Vikram Joshi", "Pending KYC \u23F3", "Reward on verification"),
    ]
    for name, status, reward in history:
        st.markdown(f"**{name}** — {status} — {reward}")


# =====================================================================
# PAGE: BLOG & TIPS
# =====================================================================
def page_blog_tips():
    render_global_css(bg_color="#FCFBF9", page_css=""".blog-header { font-family: 'Georgia', serif; font-size: 2.6rem; font-weight: 900; text-align: center; color: #1A365D; margin-bottom: 5px; }
.blog-card { background: white; border-radius: 15px; overflow: hidden; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 25px; transition: transform 0.3s ease; }
.blog-card:hover { transform: translateY(-5px); }
.blog-tag { background: #D4AF37; color: white; padding: 3px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; }
.full-article-box { background: #FFFDF5; border-left: 5px solid #D4AF37; border-radius: 10px; padding: 18px 20px; margin: 0 18px 18px 18px; }""")

    st.markdown("<h1 class='blog-header'>\U0001F4DD Matrimonial Tips & Guides</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:gray;'>Expert advice on matchmaking, wedding planning, and building a strong relationship.</p>", unsafe_allow_html=True)
    st.markdown("---")

    articles = [
        {"title": "10 Questions to Ask Before Saying Yes", "tag": "Matchmaking",
         "img": "https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?auto=format&fit=crop&w=600&q=80",
         "excerpt": "Beyond horoscope matching, here are the practical conversations every couple should have before getting engaged.",
         "full": "Compatibility is about more than a good Guna Milan score. Before saying yes, have honest conversations about: daily routines and career expectations, how you'll handle finances jointly or separately, where you plan to live after marriage, views on having children and timing, relationships with in-laws and boundaries, health history that might affect family planning, and how each of you handles conflict. These conversations feel awkward at first, but couples who have them early report far fewer surprises after the wedding. Use your Bandhan chat and family meet scheduler to have these talks at a comfortable pace, ideally before your families finalize anything."},
        {"title": "How to Spot a Fake Profile", "tag": "Safety",
         "img": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=600&q=80",
         "excerpt": "Red flags to watch for — inconsistent photos, reluctance to video call, and urgent money requests.",
         "full": "Fake or fraudulent profiles usually share common patterns: photos that look professionally shot or inconsistent across posts (reverse image search can help), a profile that avoids specific questions about family, work, or location, reluctance or excuses to avoid a live video call, a story that moves unusually fast toward marriage within days, and any request for money, gifts, or financial details, however small or urgent-sounding. On Bandhan, always prefer KYC-verified profiles (look for the blue tick), use in-app chat and calling instead of moving to unverified channels immediately, and use the Report & Block feature the moment something feels off. Trust your instincts — genuine matches are never in a rush to bypass safety steps."},
        {"title": "Budget-Friendly Wedding Ideas for 2026", "tag": "Wedding Planning",
         "img": "https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=600&q=80",
         "excerpt": "Royal weddings don't need a royal budget. Smart ways to save without compromising on the magic.",
         "full": "A memorable wedding doesn't require a massive budget. Some practical ways to save: choose an off-peak wedding date or weekday, which can cut venue costs significantly; combine mehendi and sangeet into a single evening event; opt for a seasonal, local flower palette instead of imported blooms; negotiate package deals with vendors who offer catering + decoration together (check the Verified Vendors on our Wedding Services page); keep the guest list intentional rather than maximal, which reduces catering and venue costs proportionally; and use Bandhan's Collaborative Budget Split tool so both families track contributions transparently from day one, avoiding last-minute financial stress."},
        {"title": "Understanding Guna Milan: A Simple Guide", "tag": "Astrology",
         "img": "https://images.unsplash.com/photo-1470813740244-df37b8c1edcb?auto=format&fit=crop&w=600&q=80",
         "excerpt": "What the 36 Gunas actually mean, and how much weight you should really give them.",
         "full": "Guna Milan (Ashtakoota) compares eight aspects of both birth charts — Varna, Vashya, Tara, Yoni, Graha Maitri, Gana, Bhakoot, and Nadi — scored out of 36 total points. A score above 18 is traditionally considered acceptable, and above 28 is seen as excellent. However, most astrologers agree the score is a guideline, not a verdict: Nadi and Bhakoot doshas deserve closer attention since they relate to health and long-term harmony, but a lower total score with strong compatibility elsewhere can still make a great match. Use our AI Kundali & Guna Milan tool for an instant, detailed breakdown, and treat the result as one input among many — shared values and open communication matter just as much as planetary alignment."},
    ]

    if "expanded_article" not in st.session_state:
        st.session_state.expanded_article = None

    col1, col2 = st.columns(2, gap="large")
    for i, art in enumerate(articles):
        target = col1 if i % 2 == 0 else col2
        with target:
            st.markdown("<div class='blog-card'>", unsafe_allow_html=True)
            st.image(art["img"], use_container_width=True)
            st.markdown(f"""
            <div style="padding:18px;">
                <span class="blog-tag">{art['tag']}</span>
                <h3 style="color:#1A365D; margin:10px 0 8px 0;">{art['title']}</h3>
                <p style="color:#555; font-size:0.95rem;">{art['excerpt']}</p>
            </div>
            """, unsafe_allow_html=True)

            is_open = st.session_state.expanded_article == i
            btn_label = "\u2716 Close Article" if is_open else "\U0001F4D6 Read Full Article \u2192"
            st.markdown("<div style='padding:0 18px 14px 18px;'>", unsafe_allow_html=True)
            if st.button(btn_label, key=f"read_{i}", type="primary", use_container_width=True):
                st.session_state.expanded_article = None if is_open else i
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            if is_open:
                st.markdown(f"<div class='full-article-box'>{art['full']}</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: DAILY HOROSCOPE
# =====================================================================
def page_daily_horoscope():
    render_global_css(bg_color="#FFFDF8", page_css=""".horo-header { background: linear-gradient(135deg, #4A00E0 0%, #8E2DE2 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; margin-bottom: 25px; }
.horo-card { background: white; padding: 22px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border-top: 4px solid #8E2DE2; text-align: center; }""")

    st.markdown("""
    <div class="horo-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F52E Today's Horoscope</h1>
        <p style="color:#EDE7F6; margin-top:8px;">Daily insights for love, career, and compatibility — personalized just for you.</p>
    </div>
    """, unsafe_allow_html=True)

    logged_in_name = st.session_state.get("user_name", "You")

    ZODIAC_SIGNS = [
        "Aries \u2648", "Taurus \u2649", "Gemini \u264A", "Cancer \u264B", "Leo \u264C", "Virgo \u264D",
        "Libra \u264E", "Scorpio \u264F", "Sagittarius \u2650", "Capricorn \u2651", "Aquarius \u2652", "Pisces \u2653"
    ]

    def zodiac_from_dob(dob):
        m, d = dob.month, dob.day
        boundaries = [
            (1, 20, "Capricorn \u2651"), (2, 19, "Aquarius \u2652"), (3, 21, "Pisces \u2653"),
            (4, 20, "Aries \u2648"), (5, 21, "Taurus \u2649"), (6, 21, "Gemini \u264A"),
            (7, 23, "Cancer \u264B"), (8, 23, "Leo \u264C"), (9, 23, "Virgo \u264D"),
            (10, 23, "Libra \u264E"), (11, 22, "Scorpio \u264F"), (12, 22, "Sagittarius \u2650"),
        ]
        for cm, cd, name in boundaries:
            if (m, d) <= (cm, cd):
                return name
        return "Capricorn \u2651"

    stored_dob = st.session_state.get("user_dob")
    if stored_dob:
        sign = zodiac_from_dob(stored_dob)
    else:
        seed = st.session_state.get("user_email") or logged_in_name
        sign = ZODIAC_SIGNS[abs(hash(seed)) % 12]

    render_html(f"""
    <div style="background:#F3E8FF; border-left:4px solid #8E2DE2; border-radius:8px; padding:10px 16px; margin-bottom:16px;">
        <span style="color:gray; font-size:0.85rem;">Showing horoscope for</span><br>
        <b style="color:#4A00E0; font-size:1.1rem;">{logged_in_name}</b> &mdash; <span style="color:#8E2DE2; font-weight:700;">{sign}</span>
    </div>
    """)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("<div class='horo-card'><h3>\U0001F495 Love</h3><p style=\'color:#555;\'>A meaningful conversation with a match could deepen your connection today. Stay open and honest.</p></div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='horo-card'><h3>\U0001F4BC Career</h3><p style=\'color:#555;\'>Focus and patience will help you make progress on a pending decision at work.</p></div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<div class='horo-card'><h3>\U0001F31F Lucky</h3><p style=\'color:#555;\'>Lucky Color: Gold &nbsp;|&nbsp; Lucky Number: 7</p></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.info(f"\u2728 {logged_in_name}, as a **{sign.split()[0]}**, your compatibility with Earth signs is especially strong this week — check your Recommended Matches for aligned profiles.")


# =====================================================================
# PAGE: SECOND MARRIAGE SUPPORT
# =====================================================================
SECOND_MARRIAGE_STATE_DISTRICTS = KUNDLI_STATE_DISTRICTS
SECOND_MARRIAGE_ALL_STATES = KUNDLI_ALL_STATES


def page_second_marriage():
    render_global_css(bg_color="#F8F9FA", page_css=""".second-header { background: linear-gradient(135deg, #6B46C1 0%, #1A365D 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; margin-bottom: 25px; }
.second-card { background: white; padding: 22px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 18px; }
.profile-result-card { background: white; padding: 20px; border-radius: 12px; margin-top: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 6px solid #6B46C1; }""")

    st.markdown("""
    <div class="second-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F91D Second Marriage & Divorcee Support</h1>
        <p style="color:#EDE7F6; margin-top:8px;">A dedicated, judgment-free space with filters and resources built for your situation.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='second-card'>", unsafe_allow_html=True)
    st.markdown("### Tailored Search Filters")

    st.markdown("#### Who are you searching for?")
    w1, w2 = st.columns(2)
    searching_as = w1.selectbox("I am a...", ["Male (Divorced/Widowed)", "Female (Divorced/Widowed)"])
    searching_for = w2.selectbox("Looking for a...", ["Male", "Female"])

    age_range = st.slider("Preferred Age Range", 25, 65, (32, 42))

    loc1, loc2, loc3 = st.columns(3)
    with loc1:
        pref_city = st.text_input("City", placeholder="Type any city")
    with loc2:
        pref_state = st.selectbox("State", SECOND_MARRIAGE_ALL_STATES)
    with loc3:
        pref_district = st.selectbox("District", SECOND_MARRIAGE_STATE_DISTRICTS[pref_state])

    c1, c2 = st.columns(2)
    with c1:
        marital_history = st.selectbox("Marital History", ["Divorced", "Widowed", "Separated", "Annulled"])
        has_children = st.selectbox("Children", ["No children", "Have children (living with me)", "Have children (not living with me)", "Open either way"])
    with c2:
        open_to_children = st.selectbox("Open to a partner with children?", ["Yes", "No", "Depends on situation"])
        custody_pref = st.selectbox("Co-parenting comfort", ["Very comfortable", "Somewhat comfortable", "Need to discuss further"])

    family_status = st.radio("Looking to settle:", ["Single (independent household)", "With Family"], horizontal=True)

    if st.button("\U0001F50D Search With These Filters", type="primary", use_container_width=True):
        st.success(f"\u2705 Showing {searching_for.lower()} profiles ({age_range[0]}-{age_range[1]} yrs) in {pref_district}, {pref_state}{f' near {pref_city}' if pref_city else ''} — matched on second-marriage compatibility factors.")

        results = [
            {"name": "Anjali Deshmukh", "age": 34, "city": pref_city or "Nagpur", "district": pref_district, "state": pref_state,
             "history": "Divorced, 2 years ago", "children": "1 child, living with me", "family": "Single household"},
            {"name": "Vikas Rathore", "age": 38, "city": pref_city or "Nagpur", "district": pref_district, "state": pref_state,
             "history": "Widowed, 3 years ago", "children": "No children", "family": "With family"},
        ]
        for r in results:
            st.markdown(f"""
            <div class="profile-result-card">
                <h3 style="color:#1A365D; margin-top:0;">{r['name']} ({r['age']} yrs)</h3>
                <p><b>Location:</b> {r['district']}, {r['state']} {f"({r['city']})" if r['city'] else ''}</p>
                <p><b>Marital History:</b> {r['history']} | <b>Children:</b> {r['children']} | <b>Household:</b> {r['family']}</p>
            </div>
            """, unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            b1.button("\U0001F49B Send Interest", key=f"int_{r['name']}", use_container_width=True)
            b2.button("\U0001F4AC Message", key=f"msg_{r['name']}", use_container_width=True)
            b3.button("\U0001F46A Family Meet", key=f"meet_{r['name']}", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='second-card'>", unsafe_allow_html=True)
    st.markdown("### \U0001F4DE Confidential Counseling Support")
    st.write("Free first session with a relationship counselor experienced in second-marriage and blended-family conversations.")
    if st.button("\U0001F4C5 Book a Confidential Session"):
        st.success("\u2705 A counselor will reach out privately within 48 hours. This is completely confidential.")
    st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: POST-MARRIAGE RESOURCES
# =====================================================================
def page_post_marriage():
    render_global_css(bg_color="#FCFBF9", page_css=""".post-header { font-family: 'Georgia', serif; font-size: 2.4rem; font-weight: 900; text-align: center; color: #1A365D; margin-bottom: 5px; }
.resource-card { background: white; border-radius: 15px; padding: 22px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 20px; }
.full-guide-box { background: #FFFDF5; border-left: 5px solid #D4AF37; border-radius: 10px; padding: 18px 20px; margin-top: 14px; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; flex-wrap: wrap; }
.stTabs [data-baseweb="tab"] { height: 48px; background: linear-gradient(135deg, #F1F5F9, #E2E8F0); border-radius: 10px 10px 0 0; padding: 8px 16px; font-weight: 800; font-size: 0.92rem; border: 2px solid transparent; transition: all 0.25s ease; }
.stTabs [aria-selected="true"] { background: linear-gradient(90deg, #FF416C, #FF4B2B, #D4AF37, #1A365D, #2C5364) !important; background-size: 300% 300%; animation: gradientShift 5s ease infinite; border: 2px solid #D4AF37 !important; box-shadow: 0 4px 14px rgba(212,175,55,0.45); }
.stTabs [aria-selected="true"] p { color: white !important; font-weight: 900 !important; }
.tier-chip-platinum { background: linear-gradient(90deg, #6D6D6D, #C0C0C0, #6D6D6D); color: white; padding: 2px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: 800; }
.tier-chip-gold { background: #D4AF37; color: white; padding: 2px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: 800; }
.tier-chip-free { background: #CBD5E1; color: #334155; padding: 2px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: 800; }""")

    st.markdown("<h1 class='post-header'>\U0001F495 Life After the Wedding</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:gray;'>Resources for newly married couples — because the journey doesn't end at the wedding.</p>", unsafe_allow_html=True)
    st.markdown("---")

    PROPERTY_APP_URL = "#"  # TODO: replace this with the real link once the Property Investment app is launched

    if "expanded_guide" not in st.session_state:
        st.session_state.expanded_guide = None

    def read_guide_button(key, full_text):
        is_open = st.session_state.expanded_guide == key
        label = "\u2716 Close Guide" if is_open else "\U0001F4D6 Read Full Guide \u2192"
        if st.button(label, key=f"btn_{key}", type="primary", use_container_width=True):
            st.session_state.expanded_guide = None if is_open else key
            st.rerun()
        if is_open:
            st.markdown(f"<div class='full-guide-box'>{full_text}</div>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["\U0001F4B0 Joint Finances", "\U0001F49E Relationship Tips", "\U0001F3E1 Settling In", "\u2708\uFE0F Tours & Travel", "\U0001F3E0 Property Investment"])

    with tab1:
        st.markdown("<div class='resource-card'>", unsafe_allow_html=True)
        st.markdown("### Managing Money as a Couple")
        st.write("Practical guidance on joint bank accounts, splitting expenses fairly, and setting shared financial goals for your first year of marriage.")
        read_guide_button("fin_guide", """
        Start with an honest conversation about income, existing debt, and spending habits — surprises here cause more friction than the numbers themselves.
        Many couples find a hybrid approach works best: keep individual accounts for personal spending, and open one joint account for shared expenses like rent, groceries, and bills.
        Agree on a contribution ratio (50/50, or proportional to income) and revisit it if circumstances change.
        Set a simple monthly check-in — 15 minutes to review spending and upcoming expenses — rather than letting money talk happen only during arguments.
        Build an emergency fund together before big joint purchases; aim for 3-6 months of essential expenses.
        Finally, agree on a few "no-questions-asked" spending limits — small individual purchases below a set amount don't need discussion, which keeps the relationship from feeling like a constant negotiation.
        """)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("<div class='resource-card'>", unsafe_allow_html=True)
        st.markdown("### Communication in the First Year")
        st.write("Common friction points newlyweds face, and simple habits (like a weekly check-in) that keep communication strong.")
        read_guide_button("rel_guide", """
        The first year of marriage often surfaces small differences that dating didn't reveal — different sleep schedules, tidiness standards, or how each of you was raised to handle stress.
        A weekly "check-in" — 20 minutes, no distractions — where you each share one thing that went well and one thing that's bothering you, prevents small issues from becoming resentments.
        Learn each other's stress responses: some people want to talk immediately, others need space first. Naming this explicitly avoids misreading silence as anger.
        Keep celebrating small wins together, not just anniversaries — it reinforces that you're a team, not just co-managing a household.
        """)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='resource-card'>", unsafe_allow_html=True)
        st.markdown("### Handling Disagreements Without Damage")
        st.write("Simple ground rules — no raised voices, no bringing up old fights, always circle back within 24 hours — that keep small disagreements from becoming big ones.")
        read_guide_button("rel_guide2", """
        Set a few ground rules early, while you're both calm: no raised voices, no bringing up unrelated old arguments, and no walking away without agreeing on a time to continue the conversation.
        If a disagreement is getting heated, it's okay to pause — but always name a specific time to return to it (e.g., "let's continue after dinner"), so a pause doesn't feel like avoidance.
        Focus on the specific issue, not character attacks — "I felt hurt when..." lands very differently from "you always...".
        Aim to resolve or at least de-escalate within 24 hours; letting tension carry into the next day tends to compound rather than fade.
        Remember you're on the same team solving a problem together, not opponents trying to "win" the argument.
        """)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("### \U0001F4AC Real Couple Experiences")
        stories = [
            {"couple": "Aarav & Isha, married 2 years", "story": "We were strangers eight months before our wedding. What helped most was a weekly 'no-phones' dinner where we just talked — even about small things. That habit carried us through the tough first year."},
            {"couple": "Rohit & Sneha, married 4 years", "story": "Moving in with in-laws was hard at first. We agreed on one rule: any disagreement about the house gets discussed privately between us first, then we approach the family together."},
        ]
        for s in stories:
            st.markdown(f"""
            <div style="background:white; padding:16px 20px; border-radius:12px; box-shadow:0 4px 10px rgba(0,0,0,0.05); border-left:4px solid #D4AF37; margin-bottom:12px;">
                <p style="font-style:italic; color:#334155;">"{s['story']}"</p>
                <p style="color:gray; font-size:0.85rem; margin:0;">— {s['couple']}</p>
            </div>
            """, unsafe_allow_html=True)

    with tab3:
        st.markdown("<div class='resource-card'>", unsafe_allow_html=True)
        st.markdown("### Balancing In-Laws & New Home Life")
        st.write("Tips for setting healthy boundaries while maintaining strong family relationships after moving in together.")
        read_guide_button("settle_guide", """
        Agree with your spouse on your shared boundaries first, privately, before discussing them with either family — presenting a united front avoids one partner feeling caught in the middle.
        Set clear but respectful boundaries around privacy (like knocking before entering your room) and decision-making (which household choices you make together vs. involve parents in).
        Make time for one-on-one bonding with your in-laws outside of group settings — it builds a real relationship, not just a polite one.
        If tension arises, address it early and calmly rather than letting resentment build — most friction comes from unspoken expectations on both sides.
        Remember that adjusting to a new household rhythm takes months, not days — be patient with yourself and your new family.
        """)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        st.markdown("<div class='resource-card'>", unsafe_allow_html=True)
        st.markdown("### \u2708\uFE0F Plan Your Honeymoon or Anniversary Trip")
        st.write("Browse verified travel partners for honeymoon packages, anniversary getaways, and family trips.")

        if "show_travel_vendors" not in st.session_state:
            st.session_state.show_travel_vendors = False

        if st.button("\u2708\uFE0F Browse Tours & Travel Vendors", type="primary", use_container_width=True):
            st.session_state.show_travel_vendors = True

        if st.session_state.show_travel_vendors:
            travel_vendors = [
                {"name": "Bandhan Honeymoon Escapes", "specialty": "Bali, Maldives & Thailand Packages", "rating": 4.8, "phone": "+91-98XXXXXX31", "tier": "platinum"},
                {"name": "Wanderlust Honeymoons", "specialty": "Europe & International Tours", "rating": 4.7, "phone": "+91-98XXXXXX33", "tier": "platinum"},
                {"name": "Skyline Travel Circle", "specialty": "Kashmir & Northeast Getaways", "rating": 4.5, "phone": "+91-98XXXXXX34", "tier": "gold"},
                {"name": "Royal Voyage Travel Co.", "specialty": "Domestic Hill Station & Beach Packages", "rating": 4.6, "phone": "+91-98XXXXXX32", "tier": "gold"},
                {"name": "Budget Trails Travel", "specialty": "Local Weekend Getaways", "rating": 4.0, "phone": "+91-98XXXXXX35", "tier": "free"},
            ]
            tier_order = {"platinum": 0, "gold": 1, "free": 2}
            tier_label = {"platinum": "\U0001F48E Platinum", "gold": "\U0001F947 Gold", "free": "Free Listing"}
            sorted_vendors = sorted(travel_vendors, key=lambda v: (tier_order[v["tier"]], -v["rating"]))

            st.caption("Sorted by plan: 1-Year (Platinum) partners first, then Half-Yearly (Gold), then Free — highest rated within each tier shown first.")
            st.markdown("<br>", unsafe_allow_html=True)
            for v in sorted_vendors:
                vc1, vc2, vc3 = st.columns([3, 1, 2])
                vc1.markdown(f"**{v['name']}** <span class='tier-chip-{v['tier']}'>{tier_label[v['tier']]}</span><br><span style='color:gray; font-size:0.85rem;'>{v['specialty']}</span>", unsafe_allow_html=True)
                vc2.markdown(f"\u2B50 {v['rating']}")
                b1, b2 = vc3.columns(2)
                b1.button("\U0001F4DE Call", key=f"tcall_{v['name']}", use_container_width=True)
                b2.button("\U0001F4AC Message", key=f"tmsg_{v['name']}", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab5:
        st.markdown("<div class='resource-card'>", unsafe_allow_html=True)
        st.markdown("### \U0001F3E0 Property Investment")
        st.write("Looking to buy your first home together? Search verified property listings tailored to your budget and location on our dedicated Property app.")
        render_html(f"""
        <a href="{PROPERTY_APP_URL}" target="_blank" style="display:inline-block; background:linear-gradient(135deg,#1A365D,#0F2027); color:#D4AF37; padding:14px 30px; border-radius:50px; text-decoration:none; font-weight:800; border:2px solid #D4AF37;">\U0001F3E0 Explore Properties (Opens Bandhan Property App)</a>
        """)
        st.caption("\U0001F6A7 Coming Soon — this button will open our dedicated Property Investment app once it launches.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.info("\U0001F48D This section stays with your account even after your profile moves to 'Married' status — Bandhan supports you beyond matchmaking.")


# =====================================================================
# PAGE: NRI VISA ASSISTANT
# =====================================================================
def page_nri_visa():
    render_global_css(bg_color="#F8F9FA", page_css=""".nri-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.nri-card { background: white; padding: 22px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 18px; }
.doc-chip { display: inline-block; background: #E2E8F0; color: #1A365D; padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; margin: 4px; font-weight: 600; }""")

    st.markdown("""
    <div class="nri-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\u2708\uFE0F NRI & Overseas Marriage Assistance</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Special support for NRI profiles and cross-border marriage documentation.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='nri-card'>", unsafe_allow_html=True)
    st.markdown("### \U0001F3AF NRI Profile Preferences")
    col1, col2 = st.columns(2)
    with col1:
        current_country = st.selectbox("Currently Residing In", ["USA", "UK", "Canada", "Australia", "UAE", "Singapore", "Germany", "New Zealand", "Other"])
        visa_status = st.selectbox("Visa / Residency Status", ["Citizen", "Permanent Resident", "Work Visa", "Student Visa", "Other"])
    with col2:
        willing_to_relocate = st.selectbox("Willing to relocate partner abroad?", ["Yes, partner will relocate", "No, I will relocate to India", "Open to discussion"])
        marriage_location = st.selectbox("Preferred Marriage Location", ["India", "Country of residence", "Either, flexible"])
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='nri-card'>", unsafe_allow_html=True)
    st.markdown("### \U0001F4CB Required Documentation Checklist")
    st.write("Cross-border marriages typically require the following. We help you track and prepare each one:")
    docs = ["Valid Passport (both parties)", "Visa / Residency Proof", "No Objection Certificate (NOC)",
            "Marriage Registration Certificate", "Single Status Affidavit", "Police Clearance Certificate (PCC)",
            "Embassy Attestation", "Apostille of documents"]
    chips = "".join(f"<span class='doc-chip'>\U0001F4C4 {d}</span>" for d in docs)
    st.markdown(chips, unsafe_allow_html=True)

    if "nri_doc_status" not in st.session_state:
        st.session_state.nri_doc_status = {d: False for d in docs}

    st.markdown("<br>", unsafe_allow_html=True)
    st.write("Track your document readiness:")
    for d in docs:
        st.session_state.nri_doc_status[d] = st.checkbox(d, value=st.session_state.nri_doc_status[d], key=f"nridoc_{d}")

    ready_count = sum(st.session_state.nri_doc_status.values())
    st.progress(ready_count / len(docs))
    st.caption(f"{ready_count} of {len(docs)} documents ready")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='nri-card'>", unsafe_allow_html=True)
    st.markdown("### \U0001F4DE Talk to an NRI Marriage Consultant")
    st.write("Our specialists can guide you through visa sponsorship, embassy processes, and cross-border legal requirements.")
    if st.button("\U0001F4C5 Request a Consultation Call", type="primary", use_container_width=True):
        st.success("\u2705 Request received! Our NRI marriage consultant will contact you within 24 hours.")
    st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: ANNIVERSARY & BIRTHDAY REMINDERS
# =====================================================================
def page_anniversary_birthday():
    render_global_css(bg_color="#FFF8F0", page_css=""".rem-header { background: linear-gradient(135deg, #D4AF37 0%, #AA771C 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; margin-bottom: 25px; }
.rem-card { background: white; padding: 18px 20px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #D4AF37; margin-bottom: 12px; }
.rem-urgent { border-left: 5px solid #E53E3E; background: #FFF5F5; }
.wish-box { background: linear-gradient(135deg, #FFF3E0, #FFE8CC); border: 2px dashed #D4AF37; border-radius: 10px; padding: 14px 18px; margin-top: 8px; font-style: italic; color: #7A4A00; }""")

    st.markdown("""
    <div class="rem-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F382 Anniversary \U0001F48D & Birthday Reminders</h1>
        <p style="margin-top:8px;">Save your couple details once — Bandhan.com automatically remembers both birthdays and your anniversary, and sends a wish on the day.</p>
    </div>
    """, unsafe_allow_html=True)

    if "couples" not in st.session_state:
        today0 = datetime.date.today()
        st.session_state.couples = [
            {
                "spouse1_name": "Rahul Sharma", "spouse1_dob": today0 + datetime.timedelta(days=40), "spouse1_whatsapp": "+91 98450 30001",
                "spouse2_name": "Priya Sharma", "spouse2_dob": today0 + datetime.timedelta(days=18), "spouse2_whatsapp": "+91 98450 30002",
                "marriage_date": today0 + datetime.timedelta(days=5),
            },
        ]

    with st.form("add_couple_form"):
        st.markdown("#### \U0001F491 Add a Couple")
        p1, p2 = st.columns(2)
        with p1:
            st.markdown("##### \U0001F935 Spouse 1")
            spouse1_name = st.text_input("Full Name", key="s1_name")
            spouse1_dob = st.date_input("Date of Birth", key="s1_dob", value=datetime.date(1995, 1, 1))
            spouse1_whatsapp = st.text_input("WhatsApp Number", key="s1_whatsapp", placeholder="+91...")
        with p2:
            st.markdown("##### \U0001F470 Spouse 2")
            spouse2_name = st.text_input("Full Name", key="s2_name")
            spouse2_dob = st.date_input("Date of Birth", key="s2_dob", value=datetime.date(1995, 1, 1))
            spouse2_whatsapp = st.text_input("WhatsApp Number", key="s2_whatsapp", placeholder="+91...")

        marriage_date = st.date_input("Marriage (Anniversary) Date", key="marriage_date", value=datetime.date.today())

        add_couple = st.form_submit_button("\U0001F4CC Save Couple & Enable Reminders", type="primary")
        if add_couple:
            if not spouse1_name or not spouse2_name:
                st.warning("Please enter both names before saving.")
            else:
                st.session_state.couples.append({
                    "spouse1_name": spouse1_name, "spouse1_dob": spouse1_dob, "spouse1_whatsapp": spouse1_whatsapp,
                    "spouse2_name": spouse2_name, "spouse2_dob": spouse2_dob, "spouse2_whatsapp": spouse2_whatsapp,
                    "marriage_date": marriage_date,
                })
                st.success(f"\u2705 Saved! We'll now remind {spouse1_name} & {spouse2_name} of both birthdays and their anniversary.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4C6 Upcoming Reminders")

    today = datetime.date.today()

    def next_occurrence(date_value):
        this_year = date_value.replace(year=today.year)
        if this_year < today:
            this_year = this_year.replace(year=today.year + 1)
        return this_year

    events = []
    for c in st.session_state.couples:
        events.append({
            "kind": "birthday", "person": c["spouse1_name"], "date": next_occurrence(c["spouse1_dob"]),
            "recipients": [(c["spouse1_name"], c["spouse1_whatsapp"])],
            "wish": f"\U0001F382 Wish you a very happy birthday, {c['spouse1_name']}! From Bandhan.com",
        })
        events.append({
            "kind": "birthday", "person": c["spouse2_name"], "date": next_occurrence(c["spouse2_dob"]),
            "recipients": [(c["spouse2_name"], c["spouse2_whatsapp"])],
            "wish": f"\U0001F382 Wish you a very happy birthday, {c['spouse2_name']}! From Bandhan.com",
        })
        events.append({
            "kind": "anniversary", "person": f"{c['spouse1_name']} & {c['spouse2_name']}", "date": next_occurrence(c["marriage_date"]),
            "recipients": [(c["spouse1_name"], c["spouse1_whatsapp"]), (c["spouse2_name"], c["spouse2_whatsapp"])],
            "wish": f"\U0001F38A Congratulations & Happy Marriage Anniversary, {c['spouse1_name']} & {c['spouse2_name']}! From Bandhan.com",
        })

    events.sort(key=lambda e: (e["date"] - today).days)

    if not events:
        st.info("No couples added yet.")
    else:
        for e in events:
            days_left = (e["date"] - today).days
            urgent = days_left <= 7
            is_today = days_left == 0
            icon = "\U0001F38A" if e["kind"] == "anniversary" else "\U0001F382"
            label = "Anniversary" if e["kind"] == "anniversary" else "Birthday"
            css_class = "rem-card rem-urgent" if urgent else "rem-card"

            st.markdown(f"""
            <div class="{css_class}">
                {icon} <b>{e['person']}</b> &mdash; {label}<br>
                <span style="color:gray; font-size:0.9rem;">{e['date'].strftime('%d %B %Y')} &nbsp;|&nbsp; <b>{'Today!' if is_today else f"{days_left} days left"}</b></span>
            </div>
            """, unsafe_allow_html=True)

            recipients_text = ", ".join(f"{name} ({num or 'no number saved'})" for name, num in e["recipients"])

            if is_today:
                st.markdown(f"<div class='wish-box'>\U0001F4E9 Auto-sent WhatsApp wish to {recipients_text}:<br>\u201C{e['wish']}\u201D</div>", unsafe_allow_html=True)
            elif urgent:
                if st.button(f"\U0001F4AC Preview & Send WhatsApp Wish \u2014 {e['person']}", key=f"wa_{e['kind']}_{e['person']}"):
                    st.info(f"\U0001F4E9 Demo: this WhatsApp message will be queued for {recipients_text} on the day: \u201C{e['wish']}\u201D. Configure real credentials on the WhatsApp Notifications page to send it for real.")

    st.caption("\U0001F4A1 On the exact day, Bandhan.com automatically sends the wish above via WhatsApp — a birthday message goes only to the person whose birthday it is, while the anniversary message goes to both spouses together.")


# =====================================================================
# PAGE: COLLABORATIVE BUDGET SPLIT
# =====================================================================
def page_budget_split():
    render_global_css(bg_color="#fdfbfb", page_css=""".split-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.split-card { background: white; padding: 22px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border-top: 4px solid #D4AF37; text-align: center; }
.tracker-header { background: linear-gradient(135deg, #1A365D 0%, #2C5364 50%, #0F2027 100%); padding: 22px 26px; border-radius: 16px; color: white; margin-top: 10px; border-left: 6px solid #D4AF37; box-shadow: 0 8px 20px rgba(0,0,0,0.15); }
.balance-card { background: white; padding: 20px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border-top: 4px solid #E67E22; text-align: center; }
.balance-card.settled { border-top: 4px solid #27AE60; }""")

    st.markdown("""
    <div class="split-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F91D Collaborative Wedding Budget Split</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Both families contribute and track the wedding budget together, live.</p>
    </div>
    """, unsafe_allow_html=True)

    total_budget = st.number_input("Total Wedding Budget (\u20b9)", min_value=100000, max_value=50000000, value=2500000, step=50000, key="split_total_budget")
    split_ratio = st.slider("Split Ratio: Groom's Family % vs Bride's Family %", 0, 100, 50)

    groom_share = int(total_budget * split_ratio / 100)
    bride_share = total_budget - groom_share

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<div class='split-card'><h3>\U0001F935 Groom's Family</h3><h2 style='color:#27AE60;'>\u20b9 {groom_share:,.0f}</h2><p style='color:gray;'>{split_ratio}% of total</p></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='split-card'><h3>\U0001F470 Bride's Family</h3><h2 style='color:#27AE60;'>\u20b9 {bride_share:,.0f}</h2><p style='color:gray;'>{100-split_ratio}% of total</p></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="tracker-header">
        <h3 style="margin:0; font-family:'Georgia', serif;">\U0001F4B8 Contribution Tracker</h3>
        <p style="color:#D4E4EE; margin-top:6px; margin-bottom:0;">Log every payment as it happens — see the remaining balance for each family update live.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    if "contributions" not in st.session_state:
        st.session_state.contributions = []

    with st.form("contribution_form"):
        c1, c2, c3 = st.columns(3)
        contributor = c1.selectbox("Contributed by", ["Groom's Family", "Bride's Family"])
        amount = c2.number_input("Amount (\u20b9)", min_value=0, step=5000)
        note = c3.text_input("For (e.g. Venue advance)")
        add_contribution = st.form_submit_button("\u2795 Log Contribution")
        if add_contribution and amount > 0:
            st.session_state.contributions.append({"by": contributor, "amount": amount, "note": note})
            st.success("\u2705 Contribution logged.")

    if st.session_state.contributions:
        st.markdown("#### Contribution History")
        groom_paid = 0
        bride_paid = 0
        for c in st.session_state.contributions:
            st.markdown(f"**{c['by']}** paid \u20b9{c['amount']:,} \u2014 {c['note'] or 'General'}")
            if c["by"] == "Groom's Family":
                groom_paid += c["amount"]
            else:
                bride_paid += c["amount"]

        total_paid = groom_paid + bride_paid
        st.markdown(f"**Total Contributed: \u20b9{total_paid:,} / \u20b9{total_budget:,}**")
        st.progress(min(total_paid / total_budget, 1.0))

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### \u2696\uFE0F Remaining Balance (as per the agreed ratio)")
        groom_balance = groom_share - groom_paid
        bride_balance = bride_share - bride_paid

        bal_col1, bal_col2 = st.columns(2)
        with bal_col1:
            settled_class = " settled" if groom_balance <= 0 else ""
            balance_text = f"\u20b9 {groom_balance:,.0f} remaining" if groom_balance > 0 else ("\u2705 Fully Paid" if groom_balance == 0 else f"\u20b9 {abs(groom_balance):,.0f} paid extra")
            st.markdown(f"<div class='balance-card{settled_class}'><h4>\U0001F935 Groom's Family</h4><p style='color:gray; margin-bottom:4px;'>Share: \u20b9{groom_share:,.0f} \u2014 Paid: \u20b9{groom_paid:,.0f}</p><h3>{balance_text}</h3></div>", unsafe_allow_html=True)
        with bal_col2:
            settled_class = " settled" if bride_balance <= 0 else ""
            balance_text = f"\u20b9 {bride_balance:,.0f} remaining" if bride_balance > 0 else ("\u2705 Fully Paid" if bride_balance == 0 else f"\u20b9 {abs(bride_balance):,.0f} paid extra")
            st.markdown(f"<div class='balance-card{settled_class}'><h4>\U0001F470 Bride's Family</h4><p style='color:gray; margin-bottom:4px;'>Share: \u20b9{bride_share:,.0f} \u2014 Paid: \u20b9{bride_paid:,.0f}</p><h3>{balance_text}</h3></div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: LEGAL & TRUST CENTER
# =====================================================================
def page_legal_pages():
    render_global_css(bg_color="#F8F9FA", page_css=""".legal-header { color: #1A365D; font-family: 'Georgia', serif; font-size: 2.3rem; font-weight: 800; margin-bottom: 5px; }
.legal-card { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; }
.legal-card h4 { color: #1A365D; margin-top: 20px; }
.grievance-box { background: #FFF8E1; border-left: 5px solid #D4AF37; padding: 18px; border-radius: 8px; margin-top: 15px; }""")

    st.markdown("<h1 class='legal-header'>\u2696\uFE0F Legal & Trust Center</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:gray;'>Terms, privacy, grievance redressal, and your data rights — all in one place.</p>", unsafe_allow_html=True)
    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "\U0001F4C4 Terms & Conditions", "\U0001F512 Privacy Policy", "\U0001F4DE Grievance Officer", "\U0001F5D1\uFE0F Delete My Data",
        "\U0001F4B0 Refund & Cancellation", "\U0001F91D Community Guidelines", "\U0001F36A Cookie Policy"
    ])

    with tab1:
        st.markdown("<div class='legal-card'>", unsafe_allow_html=True)
        st.markdown(FULL_TERMS_TEXT)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("<div class='legal-card'>", unsafe_allow_html=True)
        st.markdown("### Privacy Policy")
        st.write("We collect only the information necessary to provide matchmaking services — your profile details, preferences, and verification documents (Aadhaar/PAN/Passport) for KYC purposes.")
        st.markdown("#### How We Use Your Data")
        st.write("Your data is used to generate matches, verify identity, and improve recommendations. We do not sell your personal data to third parties.")
        st.markdown("#### Data Security")
        st.write("All sensitive documents are encrypted at rest and in transit. Access to your contact details is controlled entirely by your Privacy Shield settings.")
        st.markdown("#### Cookies")
        st.write("We use essential cookies for login sessions and analytics cookies to improve the app experience. You can manage preferences in your browser settings.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.markdown("<div class='legal-card'>", unsafe_allow_html=True)
        st.markdown("### Grievance Redressal")
        st.write("As per the Information Technology (Intermediary Guidelines) Rules, 2021, the following Grievance Officer is designated for this platform:")
        st.markdown("""
        <div class="grievance-box">
            <b>Grievance Officer:</b> [Name to be filled by site owner]<br>
            <b>Email:</b> grievance@bandhan.com<br>
            <b>Phone:</b> +91-XXXXXXXXXX<br>
            <b>Address:</b> [Registered Office Address]<br>
            <b>Response Time:</b> Acknowledged within 24 hours, resolved within 15 days.
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        with st.form("grievance_form"):
            g_name = st.text_input("Your Name")
            g_email = st.text_input("Registered Email")
            g_issue = st.text_area("Describe your complaint")
            g_submit = st.form_submit_button("Submit Complaint", type="primary")
            if g_submit:
                if g_name and g_issue:
                    st.success("\u2705 Your complaint has been logged. Our Grievance Officer will respond within 24 hours.")
                else:
                    st.warning("Please fill in your name and complaint details.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        st.markdown("<div class='legal-card'>", unsafe_allow_html=True)
        st.markdown("### Delete My Data")
        st.write("In accordance with the Digital Personal Data Protection Act (DPDP), 2023, you have the right to request complete deletion of your personal data from our platform.")
        st.warning("\u26A0\uFE0F This action is permanent and will remove your profile, photos, chat history, and documents. This cannot be undone.")
        confirm_email = st.text_input("Confirm your registered Email / Mobile Number")
        confirm_check = st.checkbox("I understand this will permanently delete my account and data.")
        if st.button("\U0001F5D1\uFE0F Request Permanent Data Deletion", type="primary"):
            if confirm_email and confirm_check:
                st.success("\u2705 Your data deletion request has been received. It will be processed within 30 days as per policy, and you will receive a confirmation email.")
            else:
                st.warning("Please confirm your email and check the acknowledgement box.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab5:
        st.markdown("<div class='legal-card'>", unsafe_allow_html=True)
        st.markdown("### Refund & Cancellation Policy")
        st.write("This policy covers VIP Membership plans (Silver, Gold, Platinum) and Boost Visibility purchases made on Bandhan.com.")
        st.markdown("#### VIP Membership Plans")
        st.write("Once a VIP plan is activated, it is **non-refundable** except in the following cases: a technical error resulted in duplicate charges, or the plan was never activated despite successful payment. Refund requests for these cases must be raised within 7 days of purchase via the Grievance Officer tab.")
        st.markdown("#### Boost Visibility Purchases")
        st.write("Boost purchases (24-hour, 3-day, 7-day, etc.) are **non-refundable** once activated, since visibility benefits begin immediately and cannot be reversed.")
        st.markdown("#### Cancellation")
        st.write("You may cancel auto-renewal (where applicable) anytime from your account settings before the next billing cycle. Cancelling does not entitle you to a refund for the current active period — your plan benefits continue until the paid period ends.")
        st.markdown("#### Vendor & Finance Partner Listings")
        st.write("Vendor listing plans (Gold/Platinum tier) follow the same non-refundable policy once the listing is live and visible in search results.")
        st.markdown("#### How to Request an Eligible Refund")
        st.write("Use the **Grievance Officer** tab in this Legal & Trust Center, or write to refunds@bandhan.com with your payment ID (visible in your Razorpay payment confirmation email). Eligible refunds are processed within 7-10 business days to the original payment method.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab6:
        st.markdown("<div class='legal-card'>", unsafe_allow_html=True)
        st.markdown("### Community Guidelines & Code of Conduct")
        st.write("Bandhan.com exists to help people find genuine, respectful relationships. Every member agrees to the following when using the platform:")
        st.markdown("#### Be Honest")
        st.write("Your profile photos, age, marital status, profession, and family details must be accurate. Misrepresentation is grounds for immediate suspension.")
        st.markdown("#### Be Respectful")
        st.write("Harassment, abusive language, unwanted explicit content, or repeated unwanted contact after a clear 'not interested' response will not be tolerated.")
        st.markdown("#### No Solicitation")
        st.write("Using Bandhan to sell products/services, promote other platforms, or solicit money or investments from other members is strictly prohibited.")
        st.markdown("#### Protect Your Own Safety")
        st.write("Always use in-app chat and calling before sharing personal contact details. Prefer public places for first meetings, and inform a family member or friend of your plans. Use the **Report & Safety Center** immediately if something feels wrong.")
        st.markdown("#### One Profile, One Person")
        st.write("Creating multiple profiles for the same individual, or creating a profile on someone else's behalf without their knowledge and consent (except declared Family-Assisted profiles), is not allowed.")
        st.markdown("#### Enforcement")
        st.write("Violations may result in warnings, temporary suspension, or permanent account termination at Bandhan.com's discretion, depending on severity. Serious violations (fraud, harassment, impersonation) may also be reported to law enforcement.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab7:
        st.markdown("<div class='legal-card'>", unsafe_allow_html=True)
        st.markdown("### Cookie Policy")
        st.write("Bandhan.com uses cookies and similar technologies to keep the platform secure and to improve your experience.")
        st.markdown("#### Essential Cookies")
        st.write("Required for core functionality like keeping you logged in during your session. The platform cannot function without these.")
        st.markdown("#### Analytics Cookies")
        st.write("Help us understand how members use the platform (e.g. which features are most used) so we can improve matchmaking and planning tools. These do not identify you personally to advertisers.")
        st.markdown("#### Preference Cookies")
        st.write("Remember settings like your selected theme or last-used filters, so you don't have to reset them every visit.")
        st.markdown("#### Managing Cookies")
        st.write("You can control or delete cookies through your browser settings at any time. Disabling essential cookies may prevent login and core features from working correctly.")
        st.markdown("#### Third-Party Cookies")
        st.write("Payment processing (Razorpay) and WhatsApp notification services may set their own cookies/identifiers as part of completing those specific actions, governed by their respective privacy policies.")
        st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: VENDOR BOOKING DASHBOARD
# =====================================================================
def page_vendor_bookings():
    render_global_css(bg_color="#F4F6F9", page_css=""".vbd-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.booking-card { background: white; padding: 18px 20px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #D4AF37; margin-bottom: 12px; }
.status-pending { color: #D97706; font-weight: 700; }
.status-accepted { color: #166534; font-weight: 700; }
.status-declined { color: #B91C1C; font-weight: 700; }""")

    if st.session_state.user_role not in ("boss", "vendor"):
        st.error("\U0001F6AB Your account doesn't have permission to view this page.")
        if st.button("\u2190 Back to Home"):
            go_to("home")
        return

    st.markdown("""
    <div class="vbd-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F4C5 Vendor Booking Dashboard</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Manage incoming booking requests from couples. Track status in one place.</p>
    </div>
    """, unsafe_allow_html=True)

    st.info("\U0001F4AC **Note:** Bandhan only connects you with clients here. All booking confirmations and payments happen directly between you and the client — we don't process payments, to keep both sides safe from platform-related risk.")

    if "vendor_bookings" not in st.session_state:
        st.session_state.vendor_bookings = [
            {"client": "Rahul & Anjali", "service": "Photography & Videography", "date": "2026-11-14", "phone": "+91-98XXXXXX51", "status": "Pending"},
            {"client": "Vikram & Pooja", "service": "Photography & Videography", "date": "2026-12-02", "phone": "+91-98XXXXXX52", "status": "Accepted"},
            {"client": "Rohan & Sneha", "service": "Photography & Videography", "date": "2027-01-18", "phone": "+91-98XXXXXX53", "status": "Pending"},
        ]

    total = len(st.session_state.vendor_bookings)
    pending = sum(1 for b in st.session_state.vendor_bookings if b["status"] == "Pending")
    accepted = sum(1 for b in st.session_state.vendor_bookings if b["status"] == "Accepted")
    declined = sum(1 for b in st.session_state.vendor_bookings if b["status"] == "Declined")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("\U0001F4CB Total Requests", total)
    m2.metric("\u23F3 Pending", pending)
    m3.metric("\u2705 Accepted", accepted)
    m4.metric("\u274C Declined", declined)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4E5 Booking Requests")

    for i, b in enumerate(st.session_state.vendor_bookings):
        status_class = {"Pending": "status-pending", "Accepted": "status-accepted", "Declined": "status-declined"}[b["status"]]
        st.markdown(f"""
        <div class="booking-card">
            <b>{b['client']}</b> &mdash; {b['service']}<br>
            <span style="color:gray; font-size:0.9rem;">\U0001F4C5 {b['date']} &nbsp;|&nbsp; \U0001F4DE {b['phone']}</span><br>
            Status: <span class="{status_class}">{b['status']}</span>
        </div>
        """, unsafe_allow_html=True)

        if b["status"] == "Pending":
            bc1, bc2 = st.columns(2)
            if bc1.button("\u2705 Accept", key=f"accept_{i}", use_container_width=True):
                st.session_state.vendor_bookings[i]["status"] = "Accepted"
                st.rerun()
            if bc2.button("\u274C Decline", key=f"decline_{i}", use_container_width=True):
                st.session_state.vendor_bookings[i]["status"] = "Declined"
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("Not seeing your bookings? Make sure you've completed Vendor Registration and OTP verification.")


# =====================================================================
# PAGE: VENDOR INSIGHTS
# =====================================================================
def page_vendor_insights():
    render_global_css(bg_color="#F4F6F9", page_css=""".vi-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.vi-metric-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.06); border-top: 4px solid #D4AF37; text-align: center; }""")

    if st.session_state.user_role not in ("boss", "vendor"):
        st.error("\U0001F6AB Your account doesn't have permission to view this page.")
        if st.button("\u2190 Back to Home"):
            go_to("home")
        return

    st.markdown("""
    <div class="vi-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F4C8 Platform Insights</h1>
        <p style="color:#FBF5B7; margin-top:8px;">See how active Bandhan is — enough to help you decide if it's worth registering as a vendor here.</p>
    </div>
    """, unsafe_allow_html=True)

    st.caption("\u2139\uFE0F These are aggregate, non-personal numbers only. Revenue, profit, and individual client data are not shown here.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("\U0001F465 Total Registered Users", "12,543", "+324 this week")
    m2.metric("\U0001F7E2 Active This Month", "8,920")
    m3.metric("\U0001F48D Successful Matches", "1,204")
    m4.metric("\U0001F3EA Registered Vendors", "186", "+9 this week")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4CD Active Registrations by City")
    city_data = pd.DataFrame({
        "Active Users": [2450, 1890, 1620, 1340, 980, 760, 540],
    }, index=["Nagpur", "Mumbai", "Pune", "Bangalore", "Delhi", "Hyderabad", "Kolkata"])
    st.bar_chart(city_data)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F6CD\uFE0F Demand by Service Category (Client Interest Signals)")
    demand_data = pd.DataFrame({
        "Inquiries This Month": [340, 290, 260, 210, 180, 150],
    }, index=["Photography", "Catering", "Banquet Halls", "Decoration", "Apparel", "Transportation"])
    st.bar_chart(demand_data)

    st.markdown("<br>", unsafe_allow_html=True)
    render_html("""
    <div style="text-align:center; background:linear-gradient(135deg,#1A365D,#0F2027); padding:24px; border-radius:14px;">
        <p style="color:#E2E8F0; margin-bottom:12px;">Ready to reach these active users?</p>
    </div>
    """)
    if st.button("\U0001F9D1\u200d\U0001F4BC Register as a Vendor"):
        go_to("vendor_registration")


# =====================================================================
# PAGE: COMPANY DASHBOARD (BOSS ONLY)
# =====================================================================
def page_company_dashboard():
    render_global_css(bg_color="#F4F6F9", page_css="""
.admin-header { color: #1A365D; font-family: 'Helvetica Neue', sans-serif; font-weight: 900; font-size: 2.5rem; margin-bottom: 0px; }
.boss-badge { background: linear-gradient(135deg, #D4AF37, #AA771C); color: #0F2027; padding: 6px 16px; border-radius: 20px; font-weight: 800; font-size: 0.85rem; display: inline-block; }
.metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 4px solid #D4AF37; }
""")

    if st.session_state.user_role != "boss":
        st.error("\U0001F6AB Your account doesn't have permission to view this page.")
        if st.button("\u2190 Back to Home"):
            go_to("home")
        return

    st.markdown("<span class='boss-badge'>\U0001F451 BOSS-ONLY VIEW</span>", unsafe_allow_html=True)
    st.markdown("<h1 class='admin-header'>Company Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #666;'>Full company-level overview — registrations, users, revenue, and platform health. Not visible to clients or vendors.</p>", unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("### \U0001F4CB Registration Overview")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("\u2705 Total Registered", "12,543", "+324 this week")
    r2.metric("\U0001F6AA Started but Not Completed", "3,812", "-45 this week")
    r3.metric("\U0001F194 Profile IDs Created", "12,101", "+298 this week")
    r4.metric("\U0001F4DD Vendor Registrations", "186", "+9 this week")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F7E2 Activity Status")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("\U0001F7E2 Active Users (30 days)", "8,920", "71% of total")
    a2.metric("\U0001F534 Inactive Users", "3,623", "29% of total")
    a3.metric("\U0001F7E2 Active Vendors", "142", "76% of vendors")
    a4.metric("\U0001F534 Inactive Vendors", "44", "24% of vendors")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4B3 Paid vs Unpaid")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("\U0001F48E Paid (VIP) Members", "3,210", "25.6% of users")
    p2.metric("\U0001F193 Unpaid (Free) Members", "9,333", "74.4% of users")
    p3.metric("\u2B50 Boosted Profiles/Vendors", "417", "+31 this week")
    p4.metric("\U0001F501 Renewed This Month", "612")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4B0 Revenue by Date Range")
    d1, d2 = st.columns(2)
    start_date = d1.date_input("From Date", value=datetime.date.today() - datetime.timedelta(days=30), key="cd_start")
    end_date = d2.date_input("To Date", value=datetime.date.today(), key="cd_end")

    if start_date > end_date:
        st.error("\u26A0\uFE0F 'From Date' must be before 'To Date'.")
    else:
        days_selected = (end_date - start_date).days + 1
        np.random.seed(days_selected)
        daily_revenue = np.random.randint(8000, 25000, size=days_selected)
        total_revenue = int(daily_revenue.sum())
        vip_revenue = int(total_revenue * 0.55)
        boost_revenue = int(total_revenue * 0.25)
        vendor_revenue = int(total_revenue * 0.20)

        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric("\U0001F4B0 Total Revenue", f"\u20b9 {total_revenue:,}")
        rc2.metric("\U0001F48E From VIP Plans", f"\u20b9 {vip_revenue:,}")
        rc3.metric("\U0001F680 From Boost Purchases", f"\u20b9 {boost_revenue:,}")
        rc4.metric("\U0001F3EA From Vendor Plans", f"\u20b9 {vendor_revenue:,}")

        date_index = pd.date_range(start=start_date, periods=days_selected)
        revenue_chart = pd.DataFrame({"Revenue (\u20b9)": daily_revenue}, index=date_index)
        st.line_chart(revenue_chart)

    st.markdown("---")
    chart_col1, chart_col2 = st.columns(2, gap="large")
    with chart_col1:
        st.markdown("### \U0001F4C8 User Growth (Last 7 Days)")
        chart_data = pd.DataFrame(
            np.random.randint(150, 300, size=(7, 1)),
            columns=["New Registrations"],
            index=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        )
        st.line_chart(chart_data)
    with chart_col2:
        st.markdown("### \U0001F6CD\uFE0F Top Ecosystem Bookings")
        services_data = pd.DataFrame({
            "Bookings": [120, 95, 150, 80]
        }, index=["Venues", "Luxury Rides", "Apparel", "Honeymoons"])
        st.bar_chart(services_data)

    st.markdown("---")
    st.markdown("### \U0001F4CB Recent User Registrations")
    recent_users = pd.DataFrame({
        "User ID": ["#BND-1042", "#BND-1043", "#BND-1044", "#BND-1045", "#BND-1046"],
        "Name": ["Aarav Patel", "Priya Sharma", "Rohan Desai", "Neha Singh", "Vikram Rao"],
        "Age": [28, 26, 30, 27, 29],
        "Location": ["Mumbai, IN", "Delhi, IN", "London, UK", "Dubai, UAE", "New York, USA"],
        "Plan": ["Premium", "Free", "Free", "Premium", "Premium"],
        "Status": ["Verified \u2705", "Pending \u23F3", "Verified \u2705", "Verified \u2705", "Pending \u23F3"]
    })
    st.dataframe(recent_users, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.button("\U0001F4E5 Download Full Report (CSV)", type="primary")
    st.caption("\u26A0\uFE0F Numbers on this page are demo/mock data — connect a real database (MongoDB) to make these live and accurate.")


# =====================================================================
# PAGE: WHATSAPP NOTIFICATIONS (BOSS ONLY)
# =====================================================================
def wa_get_whatsapp_credentials():
    try:
        token = st.secrets["WHATSAPP_ACCESS_TOKEN"]
        phone_id = st.secrets["WHATSAPP_PHONE_NUMBER_ID"]
        return token, phone_id
    except Exception:
        return None, None


def wa_send_whatsapp_message(to_number, message, token, phone_id):
    try:
        url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message},
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            return True, "Message sent successfully."
        return False, f"API error ({resp.status_code}): {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


def page_whatsapp_notifications():
    render_global_css(bg_color="#F0FDF4", page_css=""".wa-header { background: linear-gradient(135deg, #075E54 0%, #128C7E 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; margin-bottom: 25px; }
.wa-card { background: white; padding: 26px; border-radius: 16px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; }
.wa-setup-box { background: #E8F5E9; border-left: 5px solid #128C7E; padding: 16px 20px; border-radius: 10px; margin-bottom: 15px; }""")

    if st.session_state.user_role != "boss":
        st.error("\U0001F6AB Your account doesn't have permission to view this page.")
        if st.button("\u2190 Back to Home"):
            go_to("home")
        return

    st.markdown("""
    <div class="wa-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F4AC WhatsApp Business Notifications</h1>
        <p style="margin-top:8px;">Send OTPs, match alerts, and reminders directly to WhatsApp via Meta's official Business API.</p>
    </div>
    """, unsafe_allow_html=True)

    token, phone_id = wa_get_whatsapp_credentials()

    st.markdown("<div class='wa-card'>", unsafe_allow_html=True)
    if not token or not phone_id:
        render_html("""
        <div class="wa-setup-box">
        \U0001F511 <b>Setup needed:</b> To send real WhatsApp messages, create a Meta Business account, set up the
        <a href="https://developers.facebook.com/docs/whatsapp/cloud-api/get-started" target="_blank">WhatsApp Cloud API</a>,
        and add these two values in Streamlit Cloud &rarr; App Settings &rarr; Secrets:
        <br><code>WHATSAPP_ACCESS_TOKEN = "your-permanent-token"</code><br>
        <code>WHATSAPP_PHONE_NUMBER_ID = "your-phone-number-id"</code><br>
        Until then, this page runs in <b>Demo Mode</b> — messages are simulated, not actually sent.
        </div>
        """)
    else:
        st.success("\u2705 WhatsApp Business API is connected and ready to send real messages.")

    st.markdown("### \U0001F9EA Test Send a Message")
    test_number = st.text_input("Recipient WhatsApp Number (with country code)", placeholder="e.g., 919876543210")
    test_message = st.text_area("Message", value="Hi! This is a test notification from Bandhan.com \U0001F495")

    if st.button("\U0001F4E4 Send", type="primary", use_container_width=True):
        if not test_number:
            st.warning("Please enter a recipient number.")
        elif token and phone_id:
            with st.spinner("Sending via WhatsApp Business API..."):
                success, detail = wa_send_whatsapp_message(test_number, test_message, token, phone_id)
            if success:
                st.success(f"\u2705 {detail}")
            else:
                st.error(f"\u274C Failed: {detail}")
        else:
            st.info(f"\U0001F4E9 **Demo Mode:** Would send to **{test_number}**:\n\n> {test_message}\n\n(Add real credentials above to actually send this.)")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4CB Where WhatsApp notifications are used across Bandhan")
    st.write("""
    - OTP delivery during Vendor Registration
    - New match & message alerts (Chat & Alerts)
    - Family Meet request notifications
    - Anniversary & Birthday reminders
    - Booking status updates for vendors
    """)
    st.caption("Each of these pages can call the same send_whatsapp_message() function shown here once real credentials are configured.")


# =====================================================================
# PLACEHOLDER — for pages not yet ported in this batch
# =====================================================================
def page_placeholder(title):
    render_global_css(bg_color="#F8F9FA")
    st.title(f"\U0001F6A7 {title}")
    st.info("This page hasn't been ported into the single-page version yet — it's coming in the next batch, with every feature identical to the current live app.")
    if st.button("\u2190 Back to Home"):
        go_to("home")


# =====================================================================
# MAIN DISPATCH
# =====================================================================
def main():
    init_demo_store()

    if not st.session_state.logged_in:
        render_global_css(bg_color="#FAFAFA")
        render_html("<style>[data-testid='stSidebar'] { display: none !important; }</style>")
        render_html(f"""
        <div style="text-align:center; margin-top:20px; margin-bottom:10px;">
        <div style="background: rgba(255,255,255,0.96); border-radius: 18px; padding: 14px 10px; display: inline-block; box-shadow: 0 4px 10px rgba(0,0,0,0.15);"><img src="data:image/png;base64,{MAIN_LOGO_B64}" style="max-width: 220px; height: auto;"></div>
        </div>
        """)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            render_login_signup()
        return

    allowed_roles = ["boss", "client"]
    if st.session_state.user_role == "vendor":
        allowed_roles = ["vendor"]

    ok = require_login_and_role(allowed_roles + (["vendor"] if st.session_state.user_role == "vendor" else []))

    render_sidebar()

    view = st.session_state.current_view
    view_titles = {}

    if view == "home":
        page_home()
    elif view == "registration":
        page_registration()
    elif view == "search_partner":
        page_search_partner()
    elif view == "my_matches":
        page_my_matches()
    elif view == "chat_alerts":
        page_chat_alerts()
    elif view == "family_meet":
        page_family_meet()
    elif view == "vip_membership":
        page_vip_membership()
    elif view == "report_safety":
        page_report_safety()
    elif view == "wedding_services":
        page_wedding_services()
    elif view == "wedding_budget":
        page_wedding_budget()
    elif view == "wedding_finance":
        page_wedding_finance()
    elif view == "kundli_match":
        page_kundli_match()
    elif view == "digital_invites":
        page_digital_invites()
    elif view == "wedding_countdown":
        page_wedding_countdown()
    elif view == "vendor_registration":
        page_vendor_registration()
    elif view == "success_stories":
        page_success_stories()
    elif view == "ai_compatibility":
        page_ai_compatibility()
    elif view == "ai_icebreaker":
        page_ai_icebreaker()
    elif view == "boost_visibility":
        page_boost_visibility()
    elif view == "referral_program":
        page_referral_program()
    elif view == "blog_tips":
        page_blog_tips()
    elif view == "daily_horoscope":
        page_daily_horoscope()
    elif view == "second_marriage":
        page_second_marriage()
    elif view == "post_marriage":
        page_post_marriage()
    elif view == "nri_visa":
        page_nri_visa()
    elif view == "anniversary_birthday":
        page_anniversary_birthday()
    elif view == "budget_split":
        page_budget_split()
    elif view == "legal_pages":
        page_legal_pages()
    elif view == "vendor_bookings":
        page_vendor_bookings()
    elif view == "vendor_insights":
        page_vendor_insights()
    elif view == "company_dashboard":
        page_company_dashboard()
    elif view == "whatsapp_notifications":
        page_whatsapp_notifications()
    elif view in view_titles:
        page_placeholder(view_titles[view])
    else:
        page_home()


main()
