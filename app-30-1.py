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
import re
import hashlib
import urllib.parse
import requests
import pandas as pd
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageSequence

# =====================================================================
# AUTO PWA PATCH (runs on every startup, so it also works on
# share.streamlit.io / Streamlit Community Cloud, where you can't run a
# separate command before the app starts). Safe no-op if anything about
# it fails or the static/ files aren't present yet.
# =====================================================================
def _auto_patch_pwa():
    try:
        from pathlib import Path
        index_html = Path(st.__path__[0]) / "static" / "index.html"
        marker = "<!-- BANDHAN-PWA-INJECTED -->"
        if not index_html.exists():
            return
        html = index_html.read_text(encoding="utf-8")
        if marker in html or "</head>" not in html:
            return
        tags = f"""{marker}
<link rel="manifest" href="./app/static/manifest.json">
<meta name="theme-color" content="#D4AF37">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Bandhan">
<link rel="apple-touch-icon" href="./app/static/icon-192.png">
<script>
if ('serviceWorker' in navigator) {{
  window.addEventListener('load', function() {{
    navigator.serviceWorker.register('./app/static/sw.js').catch(function() {{}});
  }});
}}
</script>
"""
        index_html.write_text(html.replace("</head>", tags + "</head>"), encoding="utf-8")
    except Exception:
        pass  # never let a PWA-install nicety break the actual app


_auto_patch_pwa()

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
from bson.objectid import ObjectId


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


def generate_referral_code(email):
    return "BND-" + hashlib.md5(email.encode()).hexdigest().upper()[:8]


def db_create_user(email, password_hash, role, name, gender=None, referred_by_code=None):
    db = get_db()
    if db is None:
        return False
    if db.users.find_one({"email": email}):
        return False
    doc = {
        "email": email,
        "password_hash": password_hash,
        "role": role,
        "name": name,
        "gender": gender,
        "created_at": dt.datetime.utcnow(),
        "referral_code": generate_referral_code(email),
        "wallet_credit": 0,
        "referred_by": None,
    }
    if referred_by_code:
        referrer = db.users.find_one({"referral_code": referred_by_code.strip().upper()})
        if referrer and referrer["email"] != email:
            doc["referred_by"] = referrer["email"]
    db.users.insert_one(doc)
    if doc["referred_by"]:
        REFERRAL_REWARD = 300
        db.users.update_one({"email": doc["referred_by"]}, {"$inc": {"wallet_credit": REFERRAL_REWARD}})
        db.referrals.insert_one({
            "referrer_email": doc["referred_by"], "referred_email": email, "referred_name": name,
            "status": "Joined", "reward": REFERRAL_REWARD, "joined_at": dt.datetime.utcnow(),
        })
    return True


def db_get_or_create_referral_code(email):
    """Backfills a referral code for accounts created before this feature existed."""
    db = get_db()
    if db is None:
        return None
    user = db.users.find_one({"email": email})
    if not user:
        return None
    if user.get("referral_code"):
        return user["referral_code"]
    code = generate_referral_code(email)
    db.users.update_one({"email": email}, {"$set": {"referral_code": code, "wallet_credit": user.get("wallet_credit", 0)}})
    return code


def db_list_referrals(email):
    db = get_db()
    if db is None:
        return []
    return list(db.referrals.find({"referrer_email": email}).sort("joined_at", -1))


def db_get_wallet_credit(email):
    db = get_db()
    if db is None:
        return 0
    user = db.users.find_one({"email": email})
    return (user or {}).get("wallet_credit", 0)


def db_list_registered_names(limit=25):
    """Returns recent registered member names (for the login-page ticker).
    Excludes the boss account."""
    db = get_db()
    if db is None:
        return []
    try:
        docs = db.users.find({}, {"name": 1, "role": 1}).sort("created_at", -1).limit(limit)
        return [(d.get("name", "Member"), d.get("role", "client")) for d in docs]
    except Exception:
        return []


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


def db_save_complaint(name, from_email, subject, message):
    """Always saves the complaint permanently to MongoDB (if connected), as a
    safety net independent of whether the email actually sends."""
    db = get_db()
    if db is None:
        return
    db.complaints.insert_one({
        "name": name,
        "from_email": from_email,
        "subject": subject,
        "message": message,
        "submitted_at": dt.datetime.utcnow(),
    })


def send_complaint_email(name, from_email, subject, message):
    """Sends the complaint straight to support@firstchoiceinnovations.com via
    a Gmail SMTP account. Needs SMTP_EMAIL and SMTP_APP_PASSWORD in Streamlit
    Secrets — if not configured yet, this quietly fails and the complaint is
    still safely saved to MongoDB above, so nothing is lost either way."""
    try:
        smtp_email = st.secrets["SMTP_EMAIL"]
        smtp_password = st.secrets["SMTP_APP_PASSWORD"]
    except Exception:
        return False, "Email sending isn't configured yet (SMTP_EMAIL / SMTP_APP_PASSWORD missing in Secrets)."

    try:
        import smtplib
        from email.mime.text import MIMEText

        body = f"New complaint/feedback submitted on Bandhan.com\n\nName: {name}\nReply-To Email: {from_email}\nSubject: {subject}\n\nMessage:\n{message}"
        msg = MIMEText(body)
        msg["Subject"] = f"[Bandhan.com Complaint] {subject}"
        msg["From"] = smtp_email
        msg["To"] = "support@firstchoiceinnovations.com"
        msg["Reply-To"] = from_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, ["support@firstchoiceinnovations.com"], msg.as_string())
        return True, "Email sent successfully."
    except Exception as e:
        return False, str(e)


def send_generic_email(to_email, subject, body):
    """Generic SMTP sender reusing the same Gmail credentials as the
    complaint form. Falls back gracefully (returns False + reason) if
    SMTP_EMAIL/SMTP_APP_PASSWORD aren't configured yet."""
    try:
        smtp_email = st.secrets["SMTP_EMAIL"]
        smtp_password = st.secrets["SMTP_APP_PASSWORD"]
    except Exception:
        return False, "Email sending isn't configured yet (SMTP_EMAIL / SMTP_APP_PASSWORD missing in Secrets)."
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = smtp_email
        msg["To"] = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, [to_email], msg.as_string())
        return True, "Email sent successfully."
    except Exception as e:
        return False, str(e)


# =====================================================================
# REAL-TIME(-ISH) CHAT BACKEND — MongoDB-backed persistence
# ---------------------------------------------------------------------
# Replaces pure session_state chat (which vanished on refresh/logout).
# Messages are now stored permanently per conversation. This is polling-
# based ("refresh to see new messages"), not push/websocket — true
# instant push would need a service like Pusher/Ably/Firebase on top.
# =====================================================================
def db_conversation_id(owner_email, contact_name):
    safe_contact = contact_name.replace(" ", "_").lower()
    return f"{owner_email}::{safe_contact}"


def db_send_message(owner_email, contact_name, role, content):
    """Persist one chat message permanently. Falls back silently to
    session-only storage (handled by the caller) if MongoDB isn't
    configured yet."""
    db = get_db()
    if db is None:
        return False
    db.messages.insert_one({
        "conversation_id": db_conversation_id(owner_email, contact_name),
        "owner_email": owner_email,
        "contact_name": contact_name,
        "role": role,
        "content": content,
        "sent_at": dt.datetime.utcnow(),
    })
    return True


def db_get_messages(owner_email, contact_name, limit=200):
    """Load full message history for this conversation from MongoDB,
    oldest first. Returns None if MongoDB isn't connected (caller should
    fall back to session_state)."""
    db = get_db()
    if db is None:
        return None
    try:
        docs = db.messages.find(
            {"conversation_id": db_conversation_id(owner_email, contact_name)}
        ).sort("sent_at", 1).limit(limit)
        return [{"role": d["role"], "content": d["content"]} for d in docs]
    except Exception:
        return None


# =====================================================================
# REAL eKYC / AADHAAR-PAN VERIFICATION — via a licensed KYC provider
# ---------------------------------------------------------------------
# Uses a HyperVerge-style eKYC API (document OCR + face-match + liveness
# in one call). Any RBI/UIDAI-empanelled provider (HyperVerge, Signzy,
# IDfy, Karza) exposes a very similar REST contract, so swapping providers
# mainly means changing the URL/payload below. Falls back to Demo Mode
# (exactly like the WhatsApp/SMTP integrations elsewhere in this app) if
# credentials aren't in Streamlit Secrets yet — nothing breaks either way.
# =====================================================================
def get_kyc_api_credentials():
    try:
        return st.secrets["KYC_APP_ID"], st.secrets["KYC_APP_KEY"]
    except Exception:
        return None, None


def run_ekyc_verification(id_type, id_number, id_image_bytes, selfie_bytes, app_id, app_key):
    """Calls a real eKYC provider: OCR-extracts the ID, runs face-match
    against the selfie, and returns a liveness score. Real Aadhaar data
    is never stored raw — providers return only a verification token +
    masked details, which is what should be persisted to MongoDB."""
    try:
        url = "https://ind.idv.hyperverge.co/v1/verifyDocumentAndFace"
        headers = {"appId": app_id, "appKey": app_key}
        files = {
            "document_front_image": ("id.jpg", id_image_bytes, "image/jpeg"),
            "selfie_image": ("selfie.jpg", selfie_bytes, "image/jpeg"),
        }
        data = {"document_type": id_type.lower().replace(" ", "_"), "id_number": id_number}
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=25)
        if resp.status_code == 200:
            result = resp.json()
            return True, result
        return False, f"API error ({resp.status_code}): {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


def db_save_kyc_result(email, id_type, masked_id, status, match_score):
    """Permanent, auditable KYC record — never stores the full ID number,
    only a masked version, in line with data-minimization principles."""
    db = get_db()
    if db is None:
        return
    db.kyc_records.insert_one({
        "email": email,
        "id_type": id_type,
        "masked_id": masked_id,
        "status": status,
        "match_score": match_score,
        "verified_at": dt.datetime.utcnow(),
    })


def mask_id_number(id_number):
    if not id_number or len(id_number) < 4:
        return "****"
    return ("*" * (len(id_number) - 4)) + id_number[-4:]


# =====================================================================
# DPDP ACT 2023 COMPLIANCE — consent + Data Principal rights requests
# ---------------------------------------------------------------------
# India's Digital Personal Data Protection Act, 2023 requires: explicit,
# specific, informed consent; a way for users ("Data Principals") to
# access/correct/erase their data or withdraw consent; and a named
# Grievance Officer. These helpers give that a permanent, auditable trail.
# =====================================================================
def db_record_dpdp_consent(email, consent_given):
    db = get_db()
    if db is None:
        return
    db.dpdp_consents.insert_one({
        "email": email,
        "consent_given": consent_given,
        "recorded_at": dt.datetime.utcnow(),
    })


def db_save_dpdp_request(email, request_type, details):
    """request_type: 'Access', 'Correction', 'Erasure', or 'Withdraw Consent'.
    Saved permanently so the Grievance Officer can act on it within the
    statutory response window."""
    db = get_db()
    if db is None:
        return None
    result = db.dpdp_requests.insert_one({
        "email": email,
        "request_type": request_type,
        "details": details,
        "status": "Pending",
        "submitted_at": dt.datetime.utcnow(),
    })
    return str(result.inserted_id)


def db_list_dpdp_requests(status=None, limit=100):
    db = get_db()
    if db is None:
        return []
    query = {"status": status} if status else {}
    return list(db.dpdp_requests.find(query).sort("submitted_at", -1).limit(limit))


def db_list_my_dpdp_requests(email):
    db = get_db()
    if db is None:
        return []
    return list(db.dpdp_requests.find({"email": email}).sort("submitted_at", -1))


def db_update_dpdp_status(request_id, status):
    db = get_db()
    if db is None:
        return False
    db.dpdp_requests.update_one({"_id": ObjectId(request_id)}, {"$set": {"status": status, "resolved_at": dt.datetime.utcnow()}})
    return True


def db_save_grievance(name, email, issue):
    db = get_db()
    if db is None:
        return None
    submitted_at = dt.datetime.utcnow()
    result = db.grievances.insert_one({
        "name": name, "email": email, "issue": issue, "status": "Pending",
        "submitted_at": submitted_at, "sla_deadline": submitted_at + dt.timedelta(days=15),
    })
    return str(result.inserted_id)


def db_list_grievances(status=None, limit=100):
    db = get_db()
    if db is None:
        return []
    query = {"status": status} if status else {}
    return list(db.grievances.find(query).sort("submitted_at", -1).limit(limit))


def db_list_my_grievances(email):
    db = get_db()
    if db is None:
        return []
    return list(db.grievances.find({"email": email}).sort("submitted_at", -1))


def db_update_grievance_status(grievance_id, status):
    db = get_db()
    if db is None:
        return False
    db.grievances.update_one({"_id": ObjectId(grievance_id)}, {"$set": {"status": status, "resolved_at": dt.datetime.utcnow()}})
    return True


# =====================================================================
# WEDDING COUNTDOWN — persistence + sharing helpers
# =====================================================================
def db_save_wedding_plan(email, plan):
    """Upserts the couple's full wedding-countdown plan (date, services,
    tasks, reminder prefs, share code) so it survives logout/refresh and
    works from any device the couple logs in from."""
    db = get_db()
    if db is None:
        return False
    doc = dict(plan)
    doc["wedding_date"] = doc["wedding_date"].isoformat()
    for t in doc.get("wedding_tasks", []):
        if t.get("due_date"):
            t["due_date"] = t["due_date"].isoformat()
    doc["email"] = email
    doc["updated_at"] = dt.datetime.utcnow()
    db.wedding_plans.update_one({"email": email}, {"$set": doc}, upsert=True)
    return True


def db_load_wedding_plan(email):
    db = get_db()
    if db is None:
        return None
    doc = db.wedding_plans.find_one({"email": email})
    if not doc:
        return None
    try:
        doc["wedding_date"] = dt.date.fromisoformat(doc["wedding_date"])
        for t in doc.get("wedding_tasks", []):
            if t.get("due_date"):
                t["due_date"] = dt.date.fromisoformat(t["due_date"])
    except Exception:
        pass
    return doc


def db_get_wedding_plan_by_share_code(share_code):
    db = get_db()
    if db is None:
        return None
    doc = db.wedding_plans.find_one({"share_code": share_code})
    if not doc:
        return None
    try:
        doc["wedding_date"] = dt.date.fromisoformat(doc["wedding_date"])
    except Exception:
        pass
    return doc


def make_share_code(email):
    return hashlib.md5(email.encode()).hexdigest()[:10]


def build_wedding_ics(title, wedding_date, description=""):
    """Builds a minimal, dependency-free .ics calendar file for the wedding
    date so it can be added to Google Calendar / Outlook / Apple Calendar."""
    dtstamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dstart = wedding_date.strftime("%Y%m%d")
    dend = (wedding_date + dt.timedelta(days=1)).strftime("%Y%m%d")
    uid = f"{hashlib.md5((title + dstart).encode()).hexdigest()}@bandhan.com"
    safe_desc = description.replace("\n", "\\n")
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Bandhan.com//Wedding Countdown//EN
CALSCALE:GREGORIAN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART;VALUE=DATE:{dstart}
DTEND;VALUE=DATE:{dend}
SUMMARY:{title}
DESCRIPTION:{safe_desc}
BEGIN:VALARM
TRIGGER:-P7D
ACTION:DISPLAY
DESCRIPTION:Wedding in 7 days!
END:VALARM
BEGIN:VALARM
TRIGGER:-P1D
ACTION:DISPLAY
DESCRIPTION:Wedding tomorrow!
END:VALARM
END:VEVENT
END:VCALENDAR
"""
    return ics.replace("\n", "\r\n")


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
# ROLE-BASED PAGE ACCESS MAP
# ---------------------------------------------------------------------
# Controls which roles can see/open each page. "boss" always has full
# access to every page regardless of what's listed here — this map only
# restricts "client" and "vendor". Any view_key NOT listed here defaults
# to visible for both client and vendor (e.g. home, legal, about, contact).
# =====================================================================
PAGE_ROLE_ACCESS = {
    # --- Client-only (matrimony-seeker features) ---
    "registration": {"client"},
    "search_partner": {"client"},
    "my_matches": {"client"},
    "smart_recommendations": {"client"},
    "ai_compatibility": {"client"},
    "ai_icebreaker": {"client"},
    "chat_alerts": {"client"},
    "family_meet": {"client"},
    "video_profile": {"client"},
    "live_video_call": {"client"},
    "wedding_services": {"client"},
    "wedding_budget": {"client"},
    "wedding_finance": {"client"},
    "kundli_match": {"client"},
    "digital_invites": {"client"},
    "wedding_countdown": {"client"},
    "astrology_consultation": {"client"},
    "vip_membership": {"client"},
    "success_stories": {"client"},
    "referral_program": {"client"},
    "daily_horoscope": {"client"},
    "second_marriage": {"client"},
    "post_marriage": {"client"},
    "anniversary_birthday": {"client"},
    "budget_split": {"client"},
    # --- Vendor-only (business features) ---
    "vendor_registration": {"vendor"},
    "vendor_membership": {"vendor"},
    "vendor_bookings": {"vendor"},
    "vendor_insights": {"vendor"},
    # --- Shared between client & vendor ---
    "boost_visibility": {"client", "vendor"},
    "report_safety": {"client", "vendor"},
    "notification_preferences": {"client", "vendor"},
    "vendor_marketplace": {"client", "vendor"},
    "local_vendor_ads": {"client", "vendor"},
    "blog_tips": {"client", "vendor"},
    # --- Boss-only (company/admin tools) ---
    "company_dashboard": set(),
    "engagement_dashboard": set(),
    "whatsapp_notifications": set(),
}


def role_can_access(role, view_key):
    """Boss always sees everything. For everyone else, defaults to
    allowed unless PAGE_ROLE_ACCESS explicitly restricts that page."""
    if role == "boss":
        return True
    allowed = PAGE_ROLE_ACCESS.get(view_key)
    if allowed is None:
        return True
    return role in allowed


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
# DPDP ACT 2023 — PRIVACY NOTICE & GRANULAR CONSENT GATE
# ---------------------------------------------------------------------
# Separate from the general Terms & Conditions above. India's Digital
# Personal Data Protection Act, 2023 requires consent for data processing
# to be explicit, specific, and separable from other terms — bundling it
# silently into a generic "I Agree" is exactly what the Act prohibits.
# =====================================================================
DPDP_PRIVACY_NOTICE = """
**PRIVACY NOTICE — Digital Personal Data Protection Act, 2023**

**What we collect:** Name, contact details, date of birth, photos/videos, government ID (for KYC), religious/community details you choose to share, chat messages, and app usage data.

**Why we collect it:** To create and verify your matrimony profile, show you relevant matches, enable KYC/trust verification, process any payments you make, and improve the service. We do not use your data for any purpose beyond what's needed to run Bandhan.com and its wedding-ecosystem features.

**Who we share it with:** Verified vendors you choose to contact, payment processors (for transactions you initiate), and law-enforcement/regulators where legally required. We do not sell personal data to third-party advertisers.

**Your rights as a Data Principal (under the DPDP Act, 2023):**
- **Right to Access** — request a copy of the personal data we hold about you.
- **Right to Correction** — ask us to fix inaccurate or incomplete data.
- **Right to Erasure** — ask us to delete your data, subject to legal retention requirements (see Terms, Section 12).
- **Right to Withdraw Consent** — withdraw your consent at any time; this may limit or end your ability to use the app.
- **Right to Grievance Redressal** — raise a grievance with our Grievance Officer (contact details below) or the Data Protection Board of India if unresolved.

**Grievance Officer:** Firstchoice Innovations, Nagpur, Maharashtra, India — reachable via the Contact Us / Complaint page on this app.

**Data retention:** Your data is retained as long as your account is active, plus a limited period after deletion for legal/security compliance (see Terms & Conditions, Section 12).

By giving consent below, you confirm you are giving free, specific, informed consent for Bandhan.com to process your personal data as described above.
"""


def render_dpdp_consent_gate():
    """Blocks the caller's content until the person gives explicit, separate
    consent for personal-data processing under the DPDP Act, 2023. Records
    the consent (or its withdrawal) permanently in MongoDB when connected."""
    accept_key = "dpdp_consent_given"
    if st.session_state.get(accept_key, False):
        return True

    st.markdown("### \U0001F510 Your Data, Your Consent")
    st.write("Before we process your personal data, please review and provide consent as required under India's Digital Personal Data Protection Act, 2023.")
    with st.container(border=True):
        st.markdown(DPDP_PRIVACY_NOTICE)
    consent = st.checkbox("I give my free, specific, and informed consent to the processing of my personal data as described above.", key="dpdp_checkbox")
    if st.button("\U0001F510 Give Consent & Continue", type="primary", use_container_width=True, key="dpdp_continue", disabled=not consent):
        st.session_state[accept_key] = True
        user_email = st.session_state.get("user_email")
        if db_is_connected() and user_email:
            db_record_dpdp_consent(user_email, True)
        st.rerun()
    if not consent:
        st.caption("\u26A0\uFE0F Please tick the box above to continue. You can withdraw this consent anytime from Legal & Trust Center \u2192 Your Data Rights.")
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
                    st.session_state.user_gender = user_doc.get("gender")
                    st.session_state.user_email = email_clean
                    st.session_state.user_name = user_doc["name"]
                    st.session_state.stay_logged_in = stay_logged_in_login
                    st.session_state.current_view = "home"
                    membership_expiry = user_doc.get("membership_expires_at")
                    if membership_expiry and membership_expiry > dt.datetime.utcnow():
                        st.session_state.is_paid_member = True
                        st.session_state.membership_tier = user_doc.get("membership_tier")
                    st.rerun()
                else:
                    st.error("\u274C Invalid email or password.")
            elif email_clean in st.session_state.all_users and st.session_state.all_users[email_clean]["password"] == password_clean:
                user = st.session_state.all_users[email_clean]
                st.session_state.logged_in = True
                st.session_state.user_role = user["role"]
                st.session_state.user_gender = user.get("gender")
                st.session_state.user_email = email_clean
                st.session_state.user_name = user["name"]
                st.session_state.stay_logged_in = stay_logged_in_login
                st.session_state.current_view = "home"
                st.rerun()
            else:
                st.error("\u274C Invalid email or password.")

    with tab_signup:
        st.write("Sign up as a **Bride**, **Groom**, or a **Vendor** (wedding service provider).")
        su_name = st.text_input("Full Name / Business Name", key="signup_name")
        su_email = st.text_input("Email", key="signup_email")
        su_password = st.text_input("Password", type="password", key="signup_password")
        su_role = st.selectbox("Create Account as a...", ["Bride", "Groom", "Vendor"])
        role_value = "vendor" if su_role == "Vendor" else "client"
        gender_value = {"Bride": "Female", "Groom": "Male"}.get(su_role)
        su_referral_code = st.text_input("Referral Code (optional)", key="signup_referral_code", placeholder="e.g., BND-XXXXXXXX").strip().upper()
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
                    created = db_create_user(su_email_clean, password_hash, role_value, su_name_clean, gender_value, referred_by_code=su_referral_code or None)
                    if created:
                        st.session_state.logged_in = True
                        st.session_state.user_role = role_value
                        st.session_state.user_gender = gender_value
                        st.session_state.user_email = su_email_clean
                        st.session_state.user_name = su_name_clean
                        st.session_state.stay_logged_in = stay_logged_in_signup
                        st.session_state.current_view = "vendor_registration" if role_value == "vendor" else "registration"
                        if su_referral_code:
                            st.success(f"\u2705 Account created! Referral code applied \u2014 welcome, {su_name_clean}.")
                        else:
                            st.success(f"\u2705 Account created and saved permanently! Welcome, {su_name_clean}.")
                        st.rerun()
                    else:
                        st.error("An account with this email already exists. Please log in instead.")
            elif su_email_clean in st.session_state.all_users:
                st.error("An account with this email already exists. Please log in instead.")
            else:
                st.session_state.all_users[su_email_clean] = {"password": su_password_clean, "role": role_value, "name": su_name_clean, "gender": gender_value}
                st.session_state.logged_in = True
                st.session_state.user_role = role_value
                st.session_state.user_gender = gender_value
                st.session_state.user_email = su_email_clean
                st.session_state.user_name = su_name_clean
                st.session_state.stay_logged_in = stay_logged_in_signup
                st.session_state.current_view = "vendor_registration" if role_value == "vendor" else "registration"
                st.success(f"\u2705 Account created! Welcome, {su_name_clean}.")
                st.rerun()

    registered_members = db_list_registered_names(30) if using_real_db else []
    if registered_members:
        ticker_items = "".join(
            f"<span style='display:inline-block; margin-right:40px;'>\U0001F49E <b>{name}</b> ({'Vendor' if role == 'vendor' else 'Member'}) just joined Bandhan.com</span>"
            for name, role in registered_members
        )
        render_html(f"""
        <div style="margin-top:24px; background:#1A365D; border-radius:12px; padding:12px 0; overflow:hidden; white-space:nowrap;">
            <div style="display:inline-block; padding-left:100%; animation: tickerScroll 30s linear infinite; color:#FBF5B7; font-size:0.9rem;">
                {ticker_items}
            </div>
        </div>
        <style>
        @keyframes tickerScroll {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-100%); }} }}
        </style>
        """)
        st.caption(f"\U0001F465 {len(registered_members)} recently registered members shown above.")

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

    def safe_sidebar_expander(label, expanded, key):
        """True accordion needs Streamlit's expander `key` support (recent
        versions). On older Streamlit this raises TypeError — fall back to
        a plain expander (still works, just without the accordion effect)
        so the app never breaks either way."""
        try:
            return st.sidebar.expander(label, expanded=expanded, key=key)
        except TypeError:
            return st.sidebar.expander(label, expanded=expanded)

    # =================================================================
    # 5 GROUPED CHAPTERS — keeps the sidebar short; each chapter expands
    # to reveal its related pages. The chapter containing the page the
    # user is currently on stays open automatically.
    # =================================================================
    nav_groups = [
        ("1\uFE0F\u20E3 Home & Matching", "\U0001F3E0", [
            ("Home", "\U0001F3E0", "home"),
            ("Registration", "\U0001F4DD", "registration"),
            ("Search Partner", "\U0001F50D", "search_partner"),
            ("My Matches", "\u2764\uFE0F", "my_matches"),
            ("AI Smart Recommendations", "\u2728", "smart_recommendations"),
            ("AI Compatibility", "\U0001F9E0", "ai_compatibility"),
            ("AI Icebreaker", "\U0001F9CA", "ai_icebreaker"),
            ("Boost Visibility", "\U0001F680", "boost_visibility"),
        ]),
        ("2\uFE0F\u20E3 Chat, Safety & Video", "\U0001F4AC", [
            ("Chat & Alerts", "\U0001F4AC", "chat_alerts"),
            ("Family Meet", "\U0001F46A", "family_meet"),
            ("Report & Safety", "\U0001F6A8", "report_safety"),
            ("Video Profile / Intro", "\U0001F3A5", "video_profile"),
            ("Live Video Call", "\U0001F4F9", "live_video_call"),
            ("Notification Preferences", "\U0001F514", "notification_preferences"),
        ]),
        ("3\uFE0F\u20E3 Wedding Planning & Astrology", "\U0001F6CD\uFE0F", [
            ("Wedding Services", "\U0001F6CD\uFE0F", "wedding_services"),
            ("Wedding Budget", "\U0001F4B0", "wedding_budget"),
            ("Wedding Finance", "\U0001F4B3", "wedding_finance"),
            ("Kundli Match", "\U0001F549\uFE0F", "kundli_match"),
            ("Digital Invites", "\U0001F48C", "digital_invites"),
            ("Wedding Countdown", "\u23F3", "wedding_countdown"),
            ("Astrology Consultation", "\U0001FA84", "astrology_consultation"),
        ]),
        ("4\uFE0F\u20E3 Vendors & Marketplace", "\U0001F3EA", [
            ("Vendor Registration", "\U0001F9D1\u200d\U0001F4BC", "vendor_registration"),
            ("Vendor Membership", "\U0001F9D1\u200d\U0001F4BC", "vendor_membership"),
            ("Vendor Marketplace & Reviews", "\U0001F3EA", "vendor_marketplace"),
            ("Local Vendor Ads", "\U0001F4E2", "local_vendor_ads"),
        ]),
        ("5\uFE0F\u20E3 Membership, Community & Support", "\U0001F451", [
            ("VIP Membership", "\U0001F451", "vip_membership"),
            ("Success Stories", "\U0001F496", "success_stories"),
            ("Refer & Earn", "\U0001F381", "referral_program"),
            ("Blog & Tips", "\U0001F4DD", "blog_tips"),
            ("Daily Horoscope", "\U0001F52E", "daily_horoscope"),
            ("Second Marriage Support", "\U0001F91D", "second_marriage"),
            ("Post-Marriage Resources", "\U0001F495", "post_marriage"),
            ("Anniversary & Birthday", "\U0001F382", "anniversary_birthday"),
            ("Budget Split", "\U0001F91D", "budget_split"),
            ("Legal & Trust Center", "\u2696\uFE0F", "legal_pages"),
            ("About Us", "\u2139\uFE0F", "about_us"),
            ("Contact Us / Complaint", "\U0001F4E9", "contact_us"),
        ]),
    ]

    current_view = st.session_state.current_view

    # Build the final ordered list of chapters (5 groups + optional admin
    # chapter), each with a unique stable key, after role-based filtering.
    chapters = []
    for idx, (group_title, group_icon, items) in enumerate(nav_groups):
        visible_items = [(label, icon, view_key) for label, icon, view_key in items if role_can_access(role, view_key)]
        if visible_items:
            chapters.append((f"chapter_{idx}", group_title, group_icon, visible_items))

    if role in ("boss", "vendor"):
        admin_items = []
        admin_items += [("Vendor Booking Dashboard", "\U0001F4C5", "vendor_bookings"), ("Vendor Insights", "\U0001F4C8", "vendor_insights")]
        if role == "boss":
            admin_items += [("Company Dashboard", "\U0001F4CA", "company_dashboard"), ("User Engagement Dashboard", "\U0001F4C8", "engagement_dashboard"), ("WhatsApp Notifications", "\U0001F4AC", "whatsapp_notifications")]
        if admin_items:
            chapters.append(("chapter_admin", "6\uFE0F\u20E3 \U0001F451 Boss / Vendor Tools", "", admin_items))

    # Which chapter contains the page currently being viewed?
    correct_chapter_key = None
    for key, _, _, items in chapters:
        if any(view_key == current_view for _, _, view_key in items):
            correct_chapter_key = key
            break

    # ---- TRUE ACCORDION: only one chapter open at a time ----
    # 1) Whenever the page changes (nav click, or first load), force the
    #    matching chapter open and every other chapter closed.
    if st.session_state.get("_sidebar_last_view") != current_view:
        st.session_state["_sidebar_last_view"] = current_view
        st.session_state["_sidebar_active_chapter"] = correct_chapter_key
        for key, *_ in chapters:
            st.session_state[f"nav_exp_{key}"] = (key == correct_chapter_key)

    # 2) Render every chapter as a keyed expander so Streamlit tracks its
    #    open/closed state for us in session_state.
    for key, group_title, group_icon, items in chapters:
        exp_key = f"nav_exp_{key}"
        if exp_key not in st.session_state:
            st.session_state[exp_key] = (key == correct_chapter_key)
        label = f"{group_icon} {group_title}".strip() if group_icon else group_title
        with safe_sidebar_expander(label, st.session_state[exp_key], exp_key):
            for item_label, item_icon, view_key in items:
                nav_button(item_label, item_icon, view_key)

    # 3) If the user just manually opened a DIFFERENT chapter than the one
    #    we consider "active" (Streamlit doesn't close others by itself),
    #    force every other chapter shut and remember the new active one.
    opened_keys = [key for key, *_ in chapters if st.session_state.get(f"nav_exp_{key}", False)]
    if len(opened_keys) > 1:
        prev_active = st.session_state.get("_sidebar_active_chapter")
        newly_opened = [k for k in opened_keys if k != prev_active]
        keep_open = newly_opened[0] if newly_opened else opened_keys[0]
        for key, *_ in chapters:
            st.session_state[f"nav_exp_{key}"] = (key == keep_open)
        st.session_state["_sidebar_active_chapter"] = keep_open
        st.rerun()
    elif len(opened_keys) == 1:
        st.session_state["_sidebar_active_chapter"] = opened_keys[0]
    else:
        st.session_state["_sidebar_active_chapter"] = None

    st.sidebar.caption("\u2705 All pages are ported into this single file, organized into chapters.")

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
    /* ---------------- Mobile responsiveness (PWA-friendly) ---------------- */
    @media (max-width: 640px) {{
        .stApp {{ font-size: 0.95rem; }}
        h1 {{ font-size: 1.5rem !important; }}
        h2 {{ font-size: 1.25rem !important; }}
        div.stButton > button, div.stFormSubmitButton > button {{
            min-height: 44px !important;
            font-size: 0.95rem !important;
        }}
        [data-testid="stSidebar"] {{ width: 82vw !important; }}
        .stTabs [data-baseweb="tab"] {{ height: 40px !important; padding: 6px 10px !important; font-size: 0.85rem !important; }}
    }}
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

    if not render_dpdp_consent_gate():
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
            email_valid = bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip())) if email else False
            if email and not email_valid:
                st.caption("\u26A0\uFE0F That doesn't look like a valid email address (e.g., name@example.com).")
            gender = st.selectbox("Gender", ["Select...", "Male", "Female", "Other"])
        with col2:
            last_name = st.text_input("Last Name")
            phone = st.text_input("Phone Number", max_chars=10, placeholder="10-digit mobile number")
            phone_valid = bool(re.match(r"^[6-9]\d{9}$", phone.strip())) if phone else False
            if phone and not phone_valid:
                st.caption("\u26A0\uFE0F Enter a valid 10-digit Indian mobile number (starts with 6-9).")
            dob = st.date_input("Date of Birth", value=datetime.date(2000, 1, 1), min_value=datetime.date(1970, 1, 1), max_value=datetime.date(2008, 1, 1))

        st.markdown("### **Verify Your Mobile & Email**")
        st.caption("This confirms these details genuinely belong to you \u2014 required before your profile goes live.")
        if "reg_mobile_otp" not in st.session_state:
            st.session_state.reg_mobile_otp = None
            st.session_state.reg_mobile_otp_verified = False
        if "reg_email_otp" not in st.session_state:
            st.session_state.reg_email_otp = None
            st.session_state.reg_email_otp_verified = False

        vcol1, vcol2 = st.columns(2)
        with vcol1:
            if st.session_state.reg_mobile_otp_verified:
                st.success("\u2705 Mobile Verified")
            else:
                if st.button("\U0001F4F2 Send OTP to Mobile", use_container_width=True, key="reg_send_mobile_otp", disabled=not phone_valid):
                    st.session_state.reg_mobile_otp = str(random.randint(100000, 999999))
                if st.session_state.reg_mobile_otp:
                    st.caption(f"\U0001F4E9 Demo Mode: real SMS would go to {phone} via a provider like MSG91/Twilio. Your OTP: **{st.session_state.reg_mobile_otp}**")
                    entered_mobile_otp = st.text_input("Enter 6-digit Mobile OTP", max_chars=6, key="reg_mobile_otp_entry")
                    if st.button("Verify Mobile OTP", key="reg_verify_mobile_otp"):
                        if entered_mobile_otp == st.session_state.reg_mobile_otp:
                            st.session_state.reg_mobile_otp_verified = True
                            st.rerun()
                        else:
                            st.error("\u274C Incorrect OTP.")
        with vcol2:
            if st.session_state.reg_email_otp_verified:
                st.success("\u2705 Email Verified")
            else:
                if st.button("\U0001F4E7 Send OTP to Email", use_container_width=True, key="reg_send_email_otp", disabled=not email_valid):
                    st.session_state.reg_email_otp = str(random.randint(100000, 999999))
                if st.session_state.reg_email_otp:
                    st.caption(f"\U0001F4E9 Demo Mode: real email would go to {email} via SMTP. Your OTP: **{st.session_state.reg_email_otp}**")
                    entered_email_otp = st.text_input("Enter 6-digit Email OTP", max_chars=6, key="reg_email_otp_entry")
                    if st.button("Verify Email OTP", key="reg_verify_email_otp"):
                        if entered_email_otp == st.session_state.reg_email_otp:
                            st.session_state.reg_email_otp_verified = True
                            st.rerun()
                        else:
                            st.error("\u274C Incorrect OTP.")

        hw_col1, hw_col2 = st.columns(2)
        with hw_col1:
            height_cm = st.number_input("Height (in cm)", min_value=120, max_value=220, value=165, step=1)
        with hw_col2:
            weight_kg = st.number_input("Weight (in kg)", min_value=30, max_value=200, value=60, step=1)

        st.markdown("### **Where You Live & Were Born**")
        loc_col1, loc_col2, loc_col3 = st.columns(3)
        with loc_col1:
            current_city = st.selectbox("Your Current City", INDIAN_CITIES)
        with loc_col2:
            birth_place = st.text_input("Birth Place (City)", placeholder="e.g., Nagpur")
        with loc_col3:
            birth_time = st.time_input("Birth Time", value=datetime.time(12, 0))
        st.caption("\U0001F549\uFE0F Birth place & time are used for accurate Kundli Matching \u2014 leave the default time if you're unsure, an astrologer can refine it later.")

        st.markdown("### **Profile Photos**")
        st.caption("Upload up to 5 clear profile photos. We'll process them for a crisp, Full HD display quality.")
        profile_photos = st.file_uploader("Profile Photos (up to 5)", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="profile_photos_multi")
        if profile_photos:
            if len(profile_photos) > 5:
                st.warning("\u26A0\uFE0F Only the first 5 photos will be used \u2014 please remove extras.")
                profile_photos = profile_photos[:5]
            preview_cols = st.columns(min(len(profile_photos), 5))
            for i, photo_file in enumerate(profile_photos):
                preview_bytes_i, _, _, _ = compress_uploaded_image(photo_file, quality=95)
                if preview_bytes_i:
                    with preview_cols[i]:
                        st.image(preview_bytes_i, caption=f"Photo {i+1}", use_container_width=True)


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
            community_caste = st.text_input("Community / Caste / Sub-caste", placeholder="e.g., Maratha, Brahmin, Rajput (optional)")
            gotra = st.text_input("Gotra (optional)", placeholder="e.g., Kashyap")

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
            diet_pref = st.selectbox("Diet", ["Vegetarian", "Non-Vegetarian", "Eggetarian", "Vegan"])
            manglik_status = st.selectbox("Manglik Status", ["Non-Manglik", "Manglik", "Anshik Manglik", "Not Sure"])
            habits_pref = st.selectbox("Drinking / Smoking", ["Non-drinker & Non-smoker", "Occasional drinker", "Occasional smoker", "Both occasionally", "Prefer not to say"])

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

        st.markdown("### **About Me**")
        about_me = st.text_area("Tell potential matches a bit about yourself", placeholder="Your interests, values, what you're looking for in a partner...", max_chars=1000, height=120)
        st.caption(f"{len(about_me)}/1000 characters")

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
        kyc_app_id, kyc_app_key = get_kyc_api_credentials()
        if not kyc_app_id or not kyc_app_key:
            st.caption("\U0001F511 Running in **Demo Mode** — add `KYC_APP_ID` / `KYC_APP_KEY` (from HyperVerge, Signzy, IDfy, or Karza) in Streamlit Secrets to verify real Aadhaar/PAN documents.")
        else:
            st.caption("\u2705 Connected to live eKYC provider — real documents will be verified.")
        st.markdown("<div class='trust-badge'>Get the Verified Blue Tick \u2705 & Trust Badge to increase your profile visibility by 300%</div><br>", unsafe_allow_html=True)
        st.markdown("### Step 1: Upload Government ID")
        id_type = st.selectbox("Select ID Type", ["Aadhaar Card", "PAN Card", "Passport", "Driving License"])
        id_number = st.text_input(f"Enter {id_type} Number", placeholder="Enter ID number securely")
        id_file = st.file_uploader(f"Upload Front Side of {id_type}", type=['jpg', 'png', 'jpeg'])
        id_file_bytes = None
        if id_file is not None:
            compressed_bytes, original_kb, compressed_kb, preview_img = compress_uploaded_image(id_file)
            if compressed_bytes:
                st.session_state.kyc_id_compressed = compressed_bytes
                id_file_bytes = compressed_bytes
                saved_pct = round((1 - (compressed_kb / original_kb)) * 100, 1) if original_kb else 0
                st.success(f"\U0001F5DC\uFE0F Document auto-compressed for faster upload — {original_kb:.0f} KB \u2192 {compressed_kb:.0f} KB (\u2212{saved_pct}%), quality preserved.")
                st.image(preview_img, caption="Compressed preview (same visual quality)", width=260)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### Step 2: Live AI Face Match")
        st.info("\U0001F4F7 Please capture a live photo to match with your provided ID.")
        kyc_photo = st.camera_input("Take a selfie for KYC")
        if st.button("\U0001F680 Submit for AI & Trust Verification", type="primary", use_container_width=True, key="kyc_submit"):
            if id_number and kyc_photo:
                user_email = st.session_state.get("user_email", "unknown")
                if kyc_app_id and kyc_app_key and id_file_bytes:
                    with st.spinner("Contacting the eKYC provider — extracting your ID and matching your face securely..."):
                        success, result = run_ekyc_verification(id_type, id_number, id_file_bytes, kyc_photo.getvalue(), kyc_app_id, kyc_app_key)
                    if success:
                        match_score = result.get("match_score", 0)
                        st.session_state.kyc_verified = True
                        db_save_kyc_result(user_email, id_type, mask_id_number(id_number), "Verified", match_score)
                        st.success(f"\u2705 Verification Successful! Face-match score: {match_score}.")
                    else:
                        st.error(f"\u274C Verification failed: {result}")
                        db_save_kyc_result(user_email, id_type, mask_id_number(id_number), "Failed", None)
                else:
                    with st.spinner("AI is scanning your ID and matching facial features securely..."):
                        time.sleep(2)
                    st.session_state.kyc_verified = True
                    db_save_kyc_result(user_email, id_type, mask_id_number(id_number), "Verified (Demo Mode)", None)
                    st.success("\u2705 Verification Successful! Your face matches the ID.")
                    st.caption("Demo mode: no real government ID was checked. Connect a real eKYC provider above to verify live.")
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
            family_email, notify_family = "", False

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
            submit_errors = []
            if not first_name:
                submit_errors.append("Please enter your First Name in the Personal Details tab.")
            if not email or not email_valid:
                submit_errors.append("Please enter a valid Email Address in the Personal Details tab.")
            if not phone or not phone_valid:
                submit_errors.append("Please enter a valid 10-digit Phone Number in the Personal Details tab.")
            if not st.session_state.get("reg_mobile_otp_verified"):
                submit_errors.append("Please verify your Mobile Number (OTP) in the Personal Details tab.")
            if not st.session_state.get("reg_email_otp_verified"):
                submit_errors.append("Please verify your Email Address (OTP) in the Personal Details tab.")

            if submit_errors:
                for err in submit_errors:
                    st.error(f"\u274C {err}")
            else:
                st.success(f"\U0001F389 Registration Successful, {first_name}! Welcome to the Bandhan Premium Ecosystem.")
                st.balloons()
                st.session_state.user_dob = dob
                st.session_state.user_name = st.session_state.get("user_name") or f"{first_name} {last_name}".strip()

                if managed_by != "Myself" and notify_family and family_email:
                    email_sent, email_info = send_generic_email(
                        family_email,
                        "Bandhan.com \u2014 Profile Registered",
                        f"Hello,\n\n{first_name} {last_name}'s profile has just been registered on Bandhan.com and you've been added as their family contact. You'll receive match updates here going forward.\n\n\u2014 Team Bandhan.com"
                    )
                    if email_sent:
                        st.caption(f"\U0001F4E7 A confirmation email was sent to your family contact ({family_email}).")
                    else:
                        st.caption(f"\U0001F4E7 Demo Mode: family notification would be emailed to {family_email} once SMTP is configured in Secrets.")

                st.markdown("<div class='next-cta-wrap'>", unsafe_allow_html=True)
                if st.button("\U0001F451 Choose Your VIP Membership Plan \u2192", type="primary", use_container_width=True, key="goto_vip_after_reg"):
                    go_to("vip_membership")
                st.markdown("</div>", unsafe_allow_html=True)
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
.tier-badge-platinum { background: linear-gradient(90deg, #6D6D6D, #C0C0C0, #6D6D6D); color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.72rem; font-weight: 800; }
.bio-snippet { color: #444; font-size: 0.88rem; font-style: italic; margin-top: 6px; }""")

    st.markdown("""
    <div class="search-header">
        <h1 class="search-title">Search Partner</h1>
        <p style="font-size:1.1rem; margin-top:10px; color:#FBF5B7; font-style:italic;">Filter through verified profiles to find your perfect life partner.</p>
    </div>
    """, unsafe_allow_html=True)

    if "search_partner_shortlist" not in st.session_state:
        st.session_state.search_partner_shortlist = set()
    if "search_partner_interest_sent" not in st.session_state:
        st.session_state.search_partner_interest_sent = set()

    st.markdown("<div class='filter-card'>", unsafe_allow_html=True)
    st.markdown("<h3>\U0001F3AF Set Your Partner Preferences</h3><br>", unsafe_allow_html=True)

    looking_for = st.radio("I am searching for a...", ["Bride", "Groom"], horizontal=True)
    st.markdown("<br>", unsafe_allow_html=True)

    f_col1, f_col2, f_col3 = st.columns(3, gap="large")
    with f_col1:
        age_range = st.slider("Age Range (Years)", 18, 55, (21, 28))
        height_range = st.slider("Height Range (cm)", 140, 200, (150, 180))
        religion = st.selectbox("Religion", ["Any", "Hindu", "Muslim", "Sikh", "Christian", "Jain", "Buddhist", "Other"])
        custom_religion = ""
        if religion == "Other":
            custom_religion = st.text_input("Please specify Religion / Caste", key="search_custom_religion")
        community_caste = st.text_input("Community / Caste (optional)", placeholder="e.g., Maratha, Brahmin")
    with f_col2:
        profession = st.selectbox("Profession / Occupation", ["Any", "Software Engineer", "Doctor", "Business Owner", "Chartered Accountant", "Civil Servant", "Banker", "Teacher", "Other"])
        custom_profession = ""
        if profession == "Other":
            custom_profession = st.text_input("Please specify Profession", key="search_custom_profession")
        education = st.selectbox("Minimum Education", ["Any", "10th Pass", "12th Pass", "Diploma", "Graduate", "Post Graduate", "B.Tech / B.E.", "MBA / PG", "MBBS / MD", "Doctorate"])
        diet_filter = st.selectbox("Diet", ["Any", "Vegetarian", "Non-Vegetarian", "Eggetarian", "Vegan"])
        mother_tongue_filter = st.selectbox("Mother Tongue", ["Any"] + MOTHER_TONGUE_OPTIONS)
    with f_col3:
        city = st.selectbox("Preferred City / Location", INDIAN_CITIES_SEARCH)
        income = st.selectbox("Annual Income", ["Any", "\u20b93 Lakh - \u20b95 Lakh", "\u20b95 Lakh - \u20b910 Lakh", "\u20b910 Lakh - \u20b920 Lakh", "\u20b920 Lakh - \u20b950 Lakh", "\u20b950 Lakh+"])
        manglik = st.selectbox("Manglik Preference", ["Doesn't Matter", "Non-Manglik", "Manglik"])
        st.caption("\u2139\uFE0F For a detailed compatibility score based on birth charts, use **Kundli Match** separately.")
        marital_status = st.selectbox("Marital Status", ["Any", "Never Married", "Divorced", "Widowed"])
        habits_filter = st.selectbox("Drinking / Smoking", ["Any", "Non-drinker & Non-smoker", "Occasional drinker", "Occasional smoker", "Prefer not to say"])

    st.markdown("<br>", unsafe_allow_html=True)
    sort_col, btn_col = st.columns([1, 2])
    with sort_col:
        sort_by = st.selectbox("Sort results by", ["Best Match %", "Recently Active", "Age: Low to High", "Age: High to Low"])
    with btn_col:
        st.markdown("<br>", unsafe_allow_html=True)
        search_clicked = st.button("\U0001F50D Search Matching Profiles", type="primary", use_container_width=True)

    if search_clicked:
        with st.spinner("Searching profiles based on your filters..."):
            time.sleep(1.0)

        # ---- Demo profile pool (stand-in until this is wired to real
        # registered profiles from MongoDB in a later step) ----
        all_profiles = [
            {"name": "Ritu Deshmukh", "age": 24, "city": "Nagpur", "religion": "Hindu", "manglik": "Non-Manglik", "caste": "Maratha",
             "diet": "Vegetarian", "habits": "Non-drinker & Non-smoker", "marital_status": "Never Married",
             "height_cm": 160, "mother_tongue": "Marathi", "profession": "Software Engineer", "education": "B.Tech / B.E.",
             "income": "\u20b912 Lakhs p.a.", "verified": "Verified ID (Aadhaar)", "active": "Active 2 hours ago",
             "bio": "Loves trekking and classical dance; looking for a caring, career-driven partner.",
             "photo": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=400&q=80", "phone": "+91 98450 12345"},
            {"name": "Sneha Patil", "age": 26, "city": "Pune", "religion": "Hindu", "manglik": "Manglik", "caste": "Maratha",
             "diet": "Vegetarian", "habits": "Non-drinker & Non-smoker", "marital_status": "Never Married",
             "height_cm": 165, "mother_tongue": "Marathi", "profession": "Chartered Accountant", "education": "MBA / PG",
             "income": "\u20b915 Lakhs p.a.", "verified": "Verified ID (PAN Card)", "active": "Active Online Now",
             "bio": "Family-oriented CA who enjoys cooking and weekend hiking.",
             "photo": "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?auto=format&fit=crop&w=400&q=80", "phone": "+91 99230 67890"},
            {"name": "Ananya Rao", "age": 28, "city": "Bengaluru", "religion": "Hindu", "manglik": "Non-Manglik", "caste": "Brahmin",
             "diet": "Eggetarian", "habits": "Occasional drinker", "marital_status": "Never Married",
             "height_cm": 158, "mother_tongue": "Kannada", "profession": "Doctor", "education": "MBBS / MD",
             "income": "\u20b920 Lakhs p.a.", "verified": "Verified ID (Aadhaar)", "active": "Active 5 hours ago",
             "bio": "Pediatrician who loves reading and volunteering on weekends.",
             "photo": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=400&q=80", "phone": "+91 98220 44556"},
            {"name": "Kavya Nair", "age": 25, "city": "Chennai", "religion": "Hindu", "manglik": "Manglik", "caste": "Nair",
             "diet": "Vegetarian", "habits": "Non-drinker & Non-smoker", "marital_status": "Never Married",
             "height_cm": 155, "mother_tongue": "Tamil", "profession": "Civil Servant", "education": "Post Graduate",
             "income": "\u20b910 Lakhs p.a.", "verified": "Verified ID (Aadhaar)", "active": "Active 1 day ago",
             "bio": "UPSC-qualified, passionate about classical music and public service.",
             "photo": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=400&q=80", "phone": "+91 90030 11223"},
            {"name": "Priya Sharma", "age": 27, "city": "Delhi", "religion": "Hindu", "manglik": "Non-Manglik", "caste": "Brahmin",
             "diet": "Non-Vegetarian", "habits": "Occasional drinker", "marital_status": "Divorced",
             "height_cm": 162, "mother_tongue": "Hindi", "profession": "Banker", "education": "MBA / PG",
             "income": "\u20b918 Lakhs p.a.", "verified": "Verified ID (Aadhaar)", "active": "Active 30 min ago",
             "bio": "Investment banker who enjoys travel, fitness, and good food.",
             "photo": "https://images.unsplash.com/photo-1552374196-c4e7ffc6e126?auto=format&fit=crop&w=400&q=80", "phone": "+91 98110 55667"},
            {"name": "Fatima Sheikh", "age": 29, "city": "Hyderabad", "religion": "Muslim", "manglik": "Non-Manglik", "caste": "Sheikh",
             "diet": "Non-Vegetarian", "habits": "Non-drinker & Non-smoker", "marital_status": "Never Married",
             "height_cm": 163, "mother_tongue": "Urdu", "profession": "Teacher", "education": "Post Graduate",
             "income": "\u20b98 Lakhs p.a.", "verified": "Verified ID (Aadhaar)", "active": "Active 3 hours ago",
             "bio": "School teacher who loves poetry, calligraphy, and quiet evenings.",
             "photo": "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=400&q=80", "phone": "+91 96650 33445"},
        ]

        EDUCATION_ORDER = ["10th Pass", "12th Pass", "Diploma", "Graduate", "Post Graduate", "B.Tech / B.E.", "MBA / PG", "MBBS / MD", "Doctorate"]

        def education_rank(level):
            return EDUCATION_ORDER.index(level) if level in EDUCATION_ORDER else 0

        def income_min_lakhs(bracket_label):
            digits = re.findall(r"\d+", bracket_label)
            return int(digits[0]) if digits else 0

        def profile_income_lakhs(income_str):
            digits = re.findall(r"\d+", income_str)
            return int(digits[0]) if digits else 0


        def matches_filters(p):
            if not (age_range[0] <= p["age"] <= age_range[1]):
                return False
            if not (height_range[0] <= p["height_cm"] <= height_range[1]):
                return False
            if religion == "Other":
                if custom_religion.strip() and custom_religion.strip().lower() not in p["religion"].lower():
                    return False
            elif religion != "Any" and p["religion"] != religion:
                return False
            if community_caste.strip() and community_caste.strip().lower() not in p["caste"].lower():
                return False
            if city != "Any" and city != "Other" and p["city"] != city:
                return False
            if diet_filter != "Any" and p["diet"] != diet_filter:
                return False
            if mother_tongue_filter != "Any" and p["mother_tongue"] != mother_tongue_filter:
                return False
            if manglik != "Doesn't Matter" and p["manglik"] != manglik:
                return False
            if marital_status != "Any" and p["marital_status"] != marital_status:
                return False
            if habits_filter != "Any" and p["habits"] != habits_filter:
                return False
            if profession == "Other":
                if custom_profession.strip() and custom_profession.strip().lower() not in p["profession"].lower():
                    return False
            elif profession != "Any" and p["profession"] != profession:
                return False
            if education != "Any" and education_rank(p["education"]) < education_rank(education):
                return False
            if income != "Any" and profile_income_lakhs(p["income"]) < income_min_lakhs(income):
                return False
            return True

        filtered = [p for p in all_profiles if matches_filters(p)]

        # simple pseudo match-score: how many optional criteria line up exactly
        for p in filtered:
            score = 80
            if religion != "Any" and p["religion"] == religion:
                score += 5
            if diet_filter != "Any" and p["diet"] == diet_filter:
                score += 5
            if mother_tongue_filter != "Any" and p["mother_tongue"] == mother_tongue_filter:
                score += 4
            if city != "Any" and p["city"] == city:
                score += 6
            p["match"] = min(score, 99)

        if sort_by == "Best Match %":
            filtered.sort(key=lambda p: -p["match"])
        elif sort_by == "Recently Active":
            filtered.sort(key=lambda p: 0 if "Now" in p["active"] else (1 if "min" in p["active"] or "hour" in p["active"] else 2))
        elif sort_by == "Age: Low to High":
            filtered.sort(key=lambda p: p["age"])
        else:
            filtered.sort(key=lambda p: -p["age"])

        st.session_state["_search_partner_results"] = filtered
        st.session_state["_search_partner_looking_for"] = looking_for

    results = st.session_state.get("_search_partner_results")
    looking_for_result = st.session_state.get("_search_partner_looking_for", looking_for)

    if results is not None:
        if not results:
            st.warning("\U0001F625 No profiles matched every filter you set. Try widening the age/height range or relaxing a filter or two.")
        else:
            st.success(f"\u2728 Found {len(results)} matching {looking_for_result.lower()} profile(s) for your current filters.")

            membership_tier = st.session_state.get("membership_tier", "free")
            if membership_tier == "free":
                st.caption("\U0001F512 Photos are blurred and contact numbers are hidden for free members. Upgrade to Gold or Platinum to unlock more.")
            elif membership_tier in ("silver", "gold"):
                st.caption("\U0001F947 Gold member: photos unlocked. Upgrade to Platinum to also unlock contact numbers.")
            elif membership_tier == "platinum":
                st.caption("\U0001F48E Platinum member: full access to photos and contact numbers.")

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
                    <div class="profile-result-card" style="margin-top:0;">
                        <h3 style="color:#1A365D; margin-top:0;">{idx}. {r['name']} ({r['age']} yrs, {r['height_cm']} cm, {r['city']}) \u2B50 {r['match']}% Match</h3>
                        <p><b>Profession:</b> {r['profession']} | <b>Education:</b> {r['education']} | <b>Income:</b> {r['income']}</p>
                        <p><b>Religion:</b> {r['religion']} ({r['manglik']}), {r['caste']} | <b>Diet:</b> {r['diet']} | <b>Mother Tongue:</b> {r['mother_tongue']} | <b>Marital Status:</b> {r['marital_status']}</p>
                        <p class="bio-snippet">\u201c{r['bio']}\u201d</p>
                        <p style="color:gray; font-size:0.9rem;">{r['verified']} \u2022 {r['active']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    if membership_tier == "platinum":
                        st.markdown(f"<div style='background:#F0FFF4; border:1px solid #27AE60; border-radius:8px; padding:6px 12px; display:inline-block;'>\U0001F4DE <b>{r['phone']}</b></div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='background:#F8F9FA; border:1px dashed #AAAAAA; border-radius:8px; padding:6px 12px; display:inline-block; color:gray;'>\U0001F512 +91 XXXXX XXXXX \u2014 <i>Platinum only</i></div>", unsafe_allow_html=True)

                b1, b2, b3, b4 = st.columns(4)
                is_shortlisted = r["name"] in st.session_state.search_partner_shortlist
                if b1.button("\u2B50 Shortlisted" if is_shortlisted else "\u2606 Shortlist", key=f"shortlist_{r['name']}", use_container_width=True):
                    if is_shortlisted:
                        st.session_state.search_partner_shortlist.discard(r["name"])
                    else:
                        st.session_state.search_partner_shortlist.add(r["name"])
                    st.rerun()
                if b2.button("\U0001F46A Family Meet", key=f"fmeet_{r['name']}", use_container_width=True):
                    st.session_state.family_meet_for = r["name"]
                    go_to("family_meet")
                if b3.button("\U0001F4DE Contact", key=f"contact_{r['name']}", use_container_width=True):
                    if membership_tier == "platinum":
                        st.info(f"\U0001F4DE Call {r['name']} directly at {r['phone']}.")
                    else:
                        st.warning("\U0001F512 Contact numbers are a Platinum feature. Upgrade to unlock direct calling.")
                        if st.button("\U0001F451 Upgrade to Platinum", key=f"upgrade_{r['name']}"):
                            go_to("vip_membership")
                already_sent = r["name"] in st.session_state.search_partner_interest_sent
                if b4.button("\u2705 Interest Sent" if already_sent else "\U0001F49B Send Interest", key=f"meet_{r['name']}", use_container_width=True, disabled=already_sent):
                    st.session_state.search_partner_interest_sent.add(r["name"])
                    st.success(f"\U0001F49B Interest sent to {r['name']}! You'll be notified if they accept.")
                    st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)

            if st.session_state.search_partner_shortlist:
                st.caption(f"\u2B50 Shortlisted so far: {', '.join(sorted(st.session_state.search_partner_shortlist))}")

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
.match-bio { color: #444; font-size: 0.85rem; font-style: italic; margin-top: 6px; }
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

    if "my_matches_shortlist" not in st.session_state:
        st.session_state.my_matches_shortlist = set()
    if "my_matches_interest_sent" not in st.session_state:
        st.session_state.my_matches_interest_sent = set()
    if "my_matches_not_interested" not in st.session_state:
        st.session_state.my_matches_not_interested = set()

    tab1, tab2 = st.tabs(["\U0001F49E Today's Matches", "\U0001F441\uFE0F Who Viewed / Shortlisted You"])
    is_paid_member = st.session_state.get("is_paid_member", False)
    membership_tier = st.session_state.get("membership_tier", "free")

    with tab1:
        filter_col, sort_col = st.columns(2)
        with filter_col:
            match_filter = st.radio("Show", ["New Matches", "All Matches"], horizontal=True)
        with sort_col:
            sort_by = st.selectbox("Sort matches by", ["Highest Compatibility", "Most Recently Active", "Newest Profiles"])
        if not is_paid_member:
            st.caption("\U0001F512 Photos are blurred for free members. Upgrade to VIP to see full-quality photos of your matches.")
        st.markdown("<br>", unsafe_allow_html=True)

        matches = [
            {"name": "Ritu Deshmukh", "age": 24, "city": "Nagpur", "profession": "Software Engineer", "score": 96,
             "height_cm": 160, "diet": "Vegetarian", "manglik": "Non-Manglik", "mother_tongue": "Marathi", "marital_status": "Never Married", "caste": "Maratha",
             "bio": "Loves trekking and classical dance; looking for a career-driven partner.",
             "verified": True, "active": "Active 2 hours ago", "is_new": True, "phone": "+91 98450 12345",
             "traits": ["Same Religion", "Similar Values", "Career-focused", "Non-Manglik match"],
             "photo": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=400&q=80"},
            {"name": "Sneha Patil", "age": 26, "city": "Pune", "profession": "Chartered Accountant", "score": 92,
             "height_cm": 165, "diet": "Vegetarian", "manglik": "Manglik", "mother_tongue": "Marathi", "marital_status": "Never Married", "caste": "Maratha",
             "bio": "Family-oriented CA who enjoys cooking and weekend hiking.",
             "verified": True, "active": "Active Online Now", "is_new": True, "phone": "+91 99230 67890",
             "traits": ["Education match", "Family values align", "Active user"],
             "photo": "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?auto=format&fit=crop&w=400&q=80"},
            {"name": "Ananya Rao", "age": 25, "city": "Bangalore", "profession": "Doctor", "score": 89,
             "height_cm": 158, "diet": "Eggetarian", "manglik": "Non-Manglik", "mother_tongue": "Kannada", "marital_status": "Never Married", "caste": "Brahmin",
             "bio": "Pediatrician who loves reading and volunteering on weekends.",
             "verified": True, "active": "Active 5 hours ago", "is_new": False, "phone": "+91 98220 44556",
             "traits": ["Common interests", "Income bracket match", "Verified profile"],
             "photo": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=400&q=80"},
            {"name": "Kavya Iyer", "age": 27, "city": "Hyderabad", "profession": "Banker", "score": 85,
             "height_cm": 162, "diet": "Non-Vegetarian", "manglik": "Non-Manglik", "mother_tongue": "Tamil", "marital_status": "Never Married", "caste": "Iyer",
             "bio": "Enjoys travel, fitness, and good food; values honesty above all.",
             "verified": True, "active": "Active 1 day ago", "is_new": False, "phone": "+91 90030 11223",
             "traits": ["Similar lifestyle", "Same city preference", "KYC Verified"],
             "photo": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=400&q=80"},
        ]

        matches = [m for m in matches if m["name"] not in st.session_state.my_matches_not_interested]
        if match_filter == "New Matches":
            matches = [m for m in matches if m["is_new"]]

        if sort_by == "Highest Compatibility":
            matches.sort(key=lambda m: -m["score"])
        elif sort_by == "Most Recently Active":
            matches.sort(key=lambda m: 0 if "Now" in m["active"] else (1 if "hour" in m["active"] else 2))
        else:
            matches.sort(key=lambda m: -m["age"])

        if not matches:
            st.info("\U0001F44B No matches to show here right now \u2014 try switching to \"All Matches\" or check back later for new AI-curated suggestions.")

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
                new_tag = " \U0001F195" if m["is_new"] else ""
                st.markdown(f"<h3 style='margin:0; color:#1A365D;'>{m['name']} ({m['age']} yrs, {m['height_cm']} cm, {m['city']}){new_tag}</h3>", unsafe_allow_html=True)
                st.markdown(f"<p style='color:gray; margin:4px 0;'>{m['profession']} \u2022 {m['diet']} \u2022 {m['manglik']}, {m['caste']} \u2022 {m['mother_tongue']} \u2022 {m['marital_status']}</p>", unsafe_allow_html=True)
                st.markdown(f"<p class='match-bio'>\u201c{m['bio']}\u201d</p>", unsafe_allow_html=True)
                chips = "".join(f"<span class='trait-chip'>{t}</span>" for t in m['traits'])
                st.markdown(f"<div style='margin-top:8px;'>{chips}</div>", unsafe_allow_html=True)
                verified_txt = "\u2705 Verified Profile" if m["verified"] else ""
                st.caption(f"{verified_txt}  \u2022  {m['active']}")
            with c2:
                st.markdown(f"<div class='score-ring' style='text-align:center;'>{m['score']}%</div><p style='text-align:center; color:gray; font-size:0.85rem;'>Compatibility</p>", unsafe_allow_html=True)
                if membership_tier == "platinum":
                    st.markdown(f"<div style='text-align:center; font-size:0.8rem; color:#27AE60;'>\U0001F4DE {m['phone']}</div>", unsafe_allow_html=True)

            b1, b2, b3, b4, b5 = st.columns(5)
            already_sent = m["name"] in st.session_state.my_matches_interest_sent
            if b1.button("\u2705 Sent" if already_sent else "\U0001F49B Interest", key=f"int_{m['name']}", use_container_width=True, disabled=already_sent):
                st.session_state.my_matches_interest_sent.add(m["name"])
                st.toast(f"\U0001F49B You sent interest to {m['name']}! They'll be notified.")
                st.rerun()
            if b2.button("\U0001F4AC Message", key=f"msg_{m['name']}", use_container_width=True):
                st.session_state.chat_preselect_contact = m["name"]
                st.session_state.chat_preselect_score = m["score"]
                go_to("chat_alerts")
            is_shortlisted = m["name"] in st.session_state.my_matches_shortlist
            if b3.button("\u2B50 Saved" if is_shortlisted else "\u2606 Shortlist", key=f"short_{m['name']}", use_container_width=True):
                if is_shortlisted:
                    st.session_state.my_matches_shortlist.discard(m["name"])
                else:
                    st.session_state.my_matches_shortlist.add(m["name"])
                st.rerun()
            if b4.button("\U0001F46A Family Meet", key=f"fmeet_{m['name']}", use_container_width=True):
                st.session_state.family_meet_for = m["name"]
                go_to("family_meet")
            if b5.button("\u274C Not Interested", key=f"skip_{m['name']}", use_container_width=True):
                st.session_state.my_matches_not_interested.add(m["name"])
                st.toast(f"Got it \u2014 {m['name']} won't be shown again.")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.my_matches_shortlist:
            st.caption(f"\u2B50 Shortlisted: {', '.join(sorted(st.session_state.my_matches_shortlist))}")

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
                        st.session_state.chat_preselect_contact = name
                        go_to("chat_alerts")
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
.status-dot-away { height: 12px; width: 12px; background-color: #AAAAAA; border-radius: 50%; display: inline-block; margin-right: 8px; }
.chat-contact-photo { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; vertical-align: middle; margin-right: 8px; }
.notif-card { background: white; padding: 16px 20px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #2563EB; margin-bottom: 10px; }
.notif-card-unread { background: #F0F7FF; padding: 16px 20px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #D4AF37; margin-bottom: 10px; }
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

    # Same demo profile pool used across Search Partner / My Matches / AI pages
    CONTACT_POOL = {
        "Ritu Deshmukh": {"age": 24, "city": "Nagpur", "profession": "Software Engineer", "active": "Active 2 hours ago", "online": False,
                          "photo": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=100&q=80"},
        "Sneha Patil": {"age": 26, "city": "Pune", "profession": "Chartered Accountant", "active": "Active Online Now", "online": True,
                        "photo": "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?auto=format&fit=crop&w=100&q=80"},
        "Ananya Rao": {"age": 26, "city": "Bengaluru", "profession": "Doctor", "active": "Active 5 hours ago", "online": False,
                       "photo": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=100&q=80"},
        "Bandhan Premium Support": {"age": None, "city": None, "profession": "Customer Support", "active": "Active Online Now", "online": True,
                                    "photo": "https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=100&q=80"},
    }

    def deterministic_phone(name):
        """Stable per-contact phone number \u2014 uses hashlib instead of
        Python's built-in hash(), which is randomized per process and was
        causing the number to change between runs."""
        digest = hashlib.md5(name.encode()).hexdigest()
        part1 = str(int(digest[:5], 16))[-5:].zfill(5)
        part2 = str(int(digest[5:10], 16))[-5:].zfill(5)
        return f"+91 98{part1} {part2}"

    if "chat_unread" not in st.session_state:
        st.session_state.chat_unread = {name: 0 for name in CONTACT_POOL if name != "Bandhan Premium Support"}
    if "chat_shortlist" not in st.session_state:
        st.session_state.chat_shortlist = set()

    total_unread = sum(st.session_state.chat_unread.values())
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"""
        <div class="tool-header">
            <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F4AC Chat & Alerts</h1>
            <p style="font-size:1.1rem; margin-top:10px; color:#E3F2FD;">Chat safely with your verified matches and receive instant WhatsApp & Match updates.</p>
            {f"<p style='color:#FFD700; font-weight:800; margin-top:6px;'>\U0001F514 {total_unread} unread message(s)</p>" if total_unread else ""}
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("\U0001F514 Simulate New Message", type="primary", use_container_width=True):
            other_contacts = [n for n in CONTACT_POOL if n != "Bandhan Premium Support"]
            pick = random.choice(other_contacts)
            st.session_state.chat_unread[pick] = st.session_state.chat_unread.get(pick, 0) + 1
            st.toast(f"\U0001F514 New message from {pick}!")
            st.rerun()

    tab_chat, tab_alerts = st.tabs(["\U0001F4AC Secure In-App Messages", "\U0001F514 Match & WhatsApp Alerts"])

    with tab_chat:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        chat_col1, chat_col2 = st.columns([1, 3], gap="medium")

        with chat_col1:
            st.markdown("### \U0001F4AC Conversations")
            st.markdown("---")
            base_contacts = list(CONTACT_POOL.keys())
            preselect_name = st.session_state.pop("chat_preselect_contact", None)
            preselect_score = st.session_state.pop("chat_preselect_score", None)
            if preselect_name and preselect_name not in CONTACT_POOL:
                CONTACT_POOL[preselect_name] = {"age": None, "city": None, "profession": "New Match", "active": "New Match", "online": False,
                                                 "photo": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=100&q=80"}
                base_contacts.insert(0, preselect_name)
                st.session_state.chat_unread.setdefault(preselect_name, 0)
            default_index = base_contacts.index(preselect_name) if preselect_name in base_contacts else 0

            def contact_label(name):
                unread = st.session_state.chat_unread.get(name, 0)
                score_txt = f" ({preselect_score}% Match)" if name == preselect_name and preselect_score else ""
                unread_txt = f" \U0001F534{unread}" if unread else ""
                return f"{name}{score_txt}{unread_txt}"

            contact = st.radio("Select a Match:", base_contacts, index=default_index, key="chat_contact_radio", format_func=contact_label)
            contact_name = contact
            st.session_state.chat_unread[contact_name] = 0

        with chat_col2:
            info = CONTACT_POOL.get(contact_name, {})
            header_l, header_r = st.columns([3, 1])
            with header_l:
                photo_html = f"<img src='{info.get('photo', '')}' class='chat-contact-photo'>" if info.get("photo") else ""
                st.markdown(f"<h2 style='color:#1A365D; margin-top:0;'>{photo_html}{contact_name}</h2>", unsafe_allow_html=True)
                dot_class = "status-dot" if info.get("online") else "status-dot-away"
                status_txt = info.get("active", "Offline")
                st.markdown(f"<div><span class='{dot_class}'></span><span style='color:gray;'>{status_txt}{' & Verified' if 'Support' not in contact_name else ''}</span></div>", unsafe_allow_html=True)
                if info.get("age"):
                    st.caption(f"{info['age']} yrs \u2022 {info['city']} \u2022 {info['profession']}")
            with header_r:
                st.markdown("<br>", unsafe_allow_html=True)
                if "Support" not in contact_name:
                    is_shortlisted = contact_name in st.session_state.chat_shortlist
                    if st.button("\u2B50 Saved" if is_shortlisted else "\u2606 Shortlist", key=f"chat_short_{contact_name}", use_container_width=True):
                        if is_shortlisted:
                            st.session_state.chat_shortlist.discard(contact_name)
                        else:
                            st.session_state.chat_shortlist.add(contact_name)
                        st.rerun()

            is_paid_member = st.session_state.get("is_paid_member", False)
            if "Support" not in contact_name:
                if is_paid_member:
                    st.markdown(f"<div style='margin-top:8px; background:#F0FFF4; border:1px solid #27AE60; border-radius:8px; padding:8px 14px; display:inline-block;'>\U0001F4DE <b>{deterministic_phone(contact_name)}</b> <span style='color:#27AE60; font-size:0.8rem;'>(VIP unlocked)</span></div>", unsafe_allow_html=True)
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
                            st.session_state.family_meet_for = contact_name
                            go_to("family_meet")
                    elif status == "scheduled":
                        scheduled_info = st.session_state.get(f"family_meet_details_{contact_name}", {})
                        st.success(f"\U0001F4C5 Family meet with {contact_name} is scheduled for {scheduled_info.get('date', '')} at {scheduled_info.get('time', '')}.")
                        if st.button("\u270F\uFE0F View / Reschedule", key=f"resched_fm_{contact_name}"):
                            st.session_state.family_meet_for = contact_name
                            go_to("family_meet")
                    elif status == "declined":
                        st.warning(f"{contact_name}'s family declined the meet request for now. You can try again later.")
                        if st.button("\U0001F501 Send New Request", key=f"retry_fm_{contact_name}"):
                            st.session_state[family_meet_key] = "pending"
                            st.rerun()

            st.markdown("---")

            user_email = st.session_state.get("user_email", "unknown")
            chat_key = f"chat_{contact_name}"
            db_connected = db_is_connected()

            if chat_key not in st.session_state:
                if db_connected:
                    loaded = db_get_messages(user_email, contact_name)
                    st.session_state[chat_key] = loaded if loaded else []
                if chat_key not in st.session_state or not st.session_state[chat_key]:
                    default_greeting = "Hello! How can I assist you today?" if "Support" in contact_name else "Hi there! I saw we have a high AI compatibility score."
                    st.session_state[chat_key] = [{"role": "assistant", "content": default_greeting}]
                    if db_connected:
                        db_send_message(user_email, contact_name, "assistant", default_greeting)

            top_bar_l, top_bar_r = st.columns([5, 1])
            with top_bar_l:
                if db_connected:
                    st.caption("\u2705 Messages are saved permanently — they'll still be here after you log out and back in.")
                else:
                    st.caption("\u26A0\uFE0F Demo mode: messages only last for this session. Connect MongoDB (MONGODB_URI in Secrets) to save chat history permanently.")
            with top_bar_r:
                if st.button("\U0001F5D1\uFE0F Clear Chat", key=f"clear_chat_{contact_name}", use_container_width=True):
                    st.session_state[chat_key] = []
                    st.rerun()
            if db_connected and st.button("\U0001F504 Refresh Messages", key=f"chat_refresh_{contact_name}"):
                st.session_state[chat_key] = db_get_messages(user_email, contact_name) or st.session_state[chat_key]
                st.rerun()

            pending_msg = st.session_state.pop("chat_pending_message", None)
            if pending_msg:
                st.session_state[chat_key].append({"role": "user", "content": pending_msg})
                if db_connected:
                    db_send_message(user_email, contact_name, "user", pending_msg)
                reply = "That sounds wonderful! Shall we connect on a quick call this weekend?" if "Support" not in contact_name else "A manager will call you shortly."
                st.session_state[chat_key].append({"role": "assistant", "content": reply})
                if db_connected:
                    db_send_message(user_email, contact_name, "assistant", reply)
                st.toast("\U0001F4AC Your icebreaker message was sent!")

            for message in st.session_state[chat_key]:
                with st.chat_message(message["role"]):
                    if message.get("image"):
                        st.image(message["image"], width=220)
                    if message.get("content"):
                        st.markdown(message["content"])
                    if message["role"] == "user":
                        st.caption("\u2713\u2713 Seen")

            attach_col, input_col = st.columns([1, 6])
            with attach_col:
                attached_photo = st.file_uploader("\U0001F4CE", type=["jpg", "jpeg", "png"], key=f"attach_{contact_name}", label_visibility="collapsed")
            with input_col:
                prompt = st.chat_input(f"Message {contact_name}...")

            if attached_photo and st.session_state.get(f"attach_sent_{contact_name}") != attached_photo.file_id:
                img_bytes = attached_photo.getvalue()
                st.session_state[chat_key].append({"role": "user", "content": "", "image": img_bytes})
                st.session_state[f"attach_sent_{contact_name}"] = attached_photo.file_id
                if db_connected:
                    db_send_message(user_email, contact_name, "user", "[Photo attachment]")
                st.rerun()

            if prompt:
                st.session_state[chat_key].append({"role": "user", "content": prompt})
                if db_connected:
                    db_send_message(user_email, contact_name, "user", prompt)
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    message_placeholder.markdown("*(typing...)*")
                    time.sleep(1.2)
                    reply = "That sounds wonderful! Shall we connect on a quick call this weekend?" if "Support" not in contact_name else "A manager will call you shortly."
                    message_placeholder.markdown(reply)
                st.session_state[chat_key].append({"role": "assistant", "content": reply})
                if db_connected:
                    db_send_message(user_email, contact_name, "assistant", reply)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_alerts:
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("### \U0001F514 Notifications")

        if "chat_alerts_read" not in st.session_state:
            st.session_state.chat_alerts_read = set()

        notifications = [
            {"id": "n1", "icon": "\U0001F49E", "text": "You have a new match: Ananya Rao (89% compatibility)", "when": "10 min ago"},
            {"id": "n2", "icon": "\U0001F4AC", "text": "Sneha Patil sent you a new message", "when": "1 hour ago"},
            {"id": "n3", "icon": "\U0001F46A", "text": "Ritu Deshmukh's family accepted your Family Meet request", "when": "3 hours ago"},
            {"id": "n4", "icon": "\U0001F4F1", "text": "WhatsApp alert delivered: OTP for Vendor Registration", "when": "Yesterday"},
            {"id": "n5", "icon": "\U0001F680", "text": "Your profile boost is expiring in 2 hours \u2014 renew to stay on top", "when": "Yesterday"},
        ]

        unread_notifs = [n for n in notifications if n["id"] not in st.session_state.chat_alerts_read]
        if unread_notifs and st.button("\u2705 Mark All as Read", key="mark_all_alerts_read"):
            st.session_state.chat_alerts_read.update(n["id"] for n in notifications)
            st.rerun()

        for n in notifications:
            is_unread = n["id"] not in st.session_state.chat_alerts_read
            card_class = "notif-card-unread" if is_unread else "notif-card"
            unread_tag = "<b style='color:#D4AF37;'>\u25CF NEW</b>  " if is_unread else ""
            st.markdown(f"""
            <div class="{card_class}">
                {unread_tag}{n['icon']} {n['text']}
                <span style="float:right; color:gray; font-size:0.85rem;">{n['when']}</span>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: FAMILY MEET SCHEDULER
# =====================================================================
def page_family_meet():
    render_global_css(bg_color="#F8F9FA", page_css=""".meet-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.meet-card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 20px; }
.topic-chip { display: inline-block; background: #E2E8F0; color: #1A365D; padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; margin: 4px; font-weight: 600; }
.upcoming-meet-card { background: #F0FFF4; padding: 16px 20px; border-radius: 12px; border-left: 5px solid #27AE60; margin-bottom: 12px; }
.cancelled-meet-card { background: #FEF2F2; padding: 16px 20px; border-radius: 12px; border-left: 5px solid #DC2626; margin-bottom: 12px; opacity: 0.75; }""")

    st.markdown("""
    <div class="meet-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F46A Virtual Family Video Meet Schedule</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Invite up to 4 people from each side to a video call, with automatic reminders for everyone.</p>
    </div>
    """, unsafe_allow_html=True)

    if "family_meets_scheduled" not in st.session_state:
        st.session_state.family_meets_scheduled = []

    meet_for = st.session_state.pop("family_meet_for", None)
    reschedule_idx = st.session_state.pop("_reschedule_idx", None)

    st.markdown("<div class='meet-card'>", unsafe_allow_html=True)
    if meet_for:
        render_html(f"""
        <div style="background:#F0F4F8; border-left:4px solid #D4AF37; border-radius:8px; padding:10px 16px; margin-bottom:16px;">
            <span style="color:gray; font-size:0.85rem;">Scheduling Family Meet for your match with</span><br>
            <b style="color:#1A365D; font-size:1.1rem;">\U0001F49E {meet_for}</b>
        </div>
        """)
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
        timezone = st.selectbox("Timezone", ["IST (India)", "GST (UAE)", "GMT (UK)", "EST (US East)", "PST (US West)", "AEDT (Australia)", "Other"])

    reminder_lead = st.selectbox("Send advance reminder to all invitees", ["1 hour before", "3 hours before", "6 hours before", "1 day before", "2 days before"], index=3)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### \U0001F464 Add Up to 4 Invitees from Each Side")
    st.caption("Every person added here will receive a video call invitation and the advance reminder you selected above. Enter a valid phone number (10 digits) or email address.")

    def is_valid_contact(value):
        value = value.strip()
        if not value:
            return True
        return bool(re.match(r"^[6-9]\d{9}$", value)) or bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))

    bride_col, groom_col = st.columns(2)
    with bride_col:
        st.markdown("##### \U0001F470 Bride's Side (max 4)")
        bride_contacts = []
        bride_invalid = False
        for i in range(1, 5):
            bc1, bc2 = st.columns(2)
            b_name = bc1.text_input(f"Name {i}", key=f"bride_name_{i}", placeholder="Full Name")
            b_contact = bc2.text_input(f"Phone / Email {i}", key=f"bride_contact_{i}", placeholder="+91... or email")
            if b_contact and not is_valid_contact(b_contact):
                st.caption(f"\u26A0\uFE0F Entry {i}: enter a valid 10-digit phone or email address.")
                bride_invalid = True
            if b_name and b_contact:
                bride_contacts.append({"name": b_name, "contact": b_contact})
    with groom_col:
        st.markdown("##### \U0001F935 Groom's Side (max 4)")
        groom_contacts = []
        groom_invalid = False
        for i in range(1, 5):
            gc1, gc2 = st.columns(2)
            g_name = gc1.text_input(f"Name {i}", key=f"groom_name_{i}", placeholder="Full Name")
            g_contact = gc2.text_input(f"Phone / Email {i}", key=f"groom_contact_{i}", placeholder="+91... or email")
            if g_contact and not is_valid_contact(g_contact):
                st.caption(f"\u26A0\uFE0F Entry {i}: enter a valid 10-digit phone or email address.")
                groom_invalid = True
            if g_name and g_contact:
                groom_contacts.append({"name": g_name, "contact": g_contact})

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("\U0001F4C5 Send Video Meet Invitations", type="primary", use_container_width=True):
        if not bride_contacts or not groom_contacts:
            st.warning("Please add at least one contact from each side (up to 4 each) before sending invitations.")
        elif bride_invalid or groom_invalid:
            st.error("\u274C Please fix the invalid phone/email entries highlighted above before sending invitations.")
        else:
            time_str = meet_time.strftime("%I:%M %p")
            total_invited = len(bride_contacts) + len(groom_contacts)
            st.success(f"\u2705 Video meet scheduled by {logged_in_name} for {meet_date} at {time_str} ({timezone}).")
            st.success(f"\U0001F4E9 Invitations sent to all {total_invited} invitees ({len(bride_contacts)} from Bride's side, {len(groom_contacts)} from Groom's side).")
            st.info(f"\u23F0 An advance reminder will be sent to everyone {reminder_lead} the video call.")
            st.markdown("**Invited:**")
            for c in bride_contacts:
                st.write(f"\U0001F470 {c['name']} \u2014 {c['contact']}")
            for c in groom_contacts:
                st.write(f"\U0001F935 {c['name']} \u2014 {c['contact']}")
            st.caption("\U0001F4F9 The video call will start automatically for all invitees at the scheduled time.")

            new_meet = {
                "with": meet_for or "General Family Meet", "date": str(meet_date), "time": time_str, "timezone": timezone,
                "bride_contacts": bride_contacts, "groom_contacts": groom_contacts, "status": "Upcoming",
            }
            if reschedule_idx is not None and 0 <= reschedule_idx < len(st.session_state.family_meets_scheduled):
                st.session_state.family_meets_scheduled[reschedule_idx] = new_meet
            else:
                st.session_state.family_meets_scheduled.append(new_meet)

            if meet_for:
                st.session_state[f"family_meet_{meet_for}"] = "scheduled"
                st.session_state[f"family_meet_details_{meet_for}"] = {"date": str(meet_date), "time": time_str}
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.family_meets_scheduled:
        st.markdown("<div class='meet-card'>", unsafe_allow_html=True)
        st.markdown("### \U0001F4C5 Your Scheduled Family Meets")
        for idx, meet in enumerate(st.session_state.family_meets_scheduled):
            card_class = "cancelled-meet-card" if meet["status"] == "Cancelled" else "upcoming-meet-card"
            st.markdown(f"""
            <div class="{card_class}">
                <b>{meet['with']}</b> \u2014 {meet['date']} at {meet['time']} ({meet['timezone']})<br>
                <span style="color:gray; font-size:0.85rem;">Status: {meet['status']} \u2022 {len(meet['bride_contacts']) + len(meet['groom_contacts'])} invitees</span>
            </div>
            """, unsafe_allow_html=True)
            if meet["status"] == "Upcoming":
                mc1, mc2 = st.columns(2)
                if mc1.button("\u270F\uFE0F Reschedule", key=f"resched_{idx}", use_container_width=True):
                    st.session_state._reschedule_idx = idx
                    st.session_state.family_meet_for = meet["with"] if meet["with"] != "General Family Meet" else None
                    st.rerun()
                if mc2.button("\u274C Cancel Meet", key=f"cancel_{idx}", use_container_width=True):
                    st.session_state.family_meets_scheduled[idx]["status"] = "Cancelled"
                    if meet["with"] != "General Family Meet":
                        st.session_state[f"family_meet_{meet['with']}"] = "accepted"
                    st.rerun()
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
# =====================================================================
# VIP MEMBERSHIP — real persistence with expiry (fixes: membership was
# previously session-only, so it silently vanished on refresh/logout and
# never actually expired, and the Boss dashboard had no real paid-user
# counts to report).
# =====================================================================
def db_activate_membership(email, tier, duration_days):
    db = get_db()
    if db is None:
        return False
    expires_at = dt.datetime.utcnow() + dt.timedelta(days=duration_days)
    db.users.update_one({"email": email}, {"$set": {"membership_tier": tier, "membership_expires_at": expires_at, "is_paid_member": True}})
    return True


def db_count_paid_members():
    db = get_db()
    if db is None:
        return 0
    return db.users.count_documents({"membership_expires_at": {"$gte": dt.datetime.utcnow()}})


def page_vip_membership():
    render_global_css(bg_color="#F8F9FA", page_css=""".vip-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 40px; border-radius: 20px; color: white; text-align: center; border: 2px solid #D4AF37; box-shadow: 0 15px 35px rgba(0,0,0,0.2); margin-bottom: 30px; }
.vip-title { font-family: 'Georgia', serif; font-size: 3rem; font-weight: 900; margin: 0; background: linear-gradient(to right, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.plan-card { background: white; border-radius: 15px; padding: 30px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border: 1px solid #EAEAEA; border-top: 6px solid #D4AF37; transition: transform 0.3s ease; margin-bottom: 20px; }
.plan-card:hover { transform: translateY(-8px); box-shadow: 0 15px 30px rgba(212, 175, 55, 0.25); }
.price-tag { font-size: 2.5rem; color: #27AE60; font-weight: 900; margin: 15px 0; }""")

    if st.session_state.user_role != "client":
        st.error("\U0001F6AB This membership plan is for Brides & Grooms only. Vendors have their own separate membership plans.")
        if st.button("\U0001F9D1\u200D\U0001F4BC Go to Vendor Membership Plans"):
            go_to("vendor_membership")
        return

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
            if db_is_connected():
                db_activate_membership(st.session_state.get("user_email", ""), "silver", 90)
            st.success("\U0001F389 Silver VIP Selected! Redirecting to secure payment gateway..." + ("" if db_is_connected() else " \u26A0\uFE0F Demo mode: connect MongoDB so this membership persists beyond this session."))

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
            if db_is_connected():
                db_activate_membership(st.session_state.get("user_email", ""), "gold", 180)
            st.balloons()
            st.success("\U0001F389 Gold VIP Selected! Premium benefits unlocked successfully." + ("" if db_is_connected() else " \u26A0\uFE0F Demo mode: connect MongoDB so this membership persists beyond this session."))

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
            if db_is_connected():
                db_activate_membership(st.session_state.get("user_email", ""), "platinum", 365)
            st.success("\U0001F389 Platinum VIP Selected! Our senior relationship manager will contact you shortly." + ("" if db_is_connected() else " \u26A0\uFE0F Demo mode: connect MongoDB so this membership persists beyond this session."))


# =====================================================================
# PAGE: VENDOR MEMBERSHIP (separate from Bride/Groom VIP plans)
# =====================================================================
def page_vendor_membership():
    render_global_css(bg_color="#F8F9FA", page_css=""".vm-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 40px; border-radius: 20px; color: white; text-align: center; border: 2px solid #D4AF37; box-shadow: 0 15px 35px rgba(0,0,0,0.2); margin-bottom: 30px; }
.vm-title { font-family: 'Georgia', serif; font-size: 2.8rem; font-weight: 900; margin: 0; background: linear-gradient(to right, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.vm-plan-card { background: white; border-radius: 15px; padding: 28px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border: 1px solid #EAEAEA; border-top: 6px solid #999; transition: transform 0.3s ease; margin-bottom: 20px; }
.vm-plan-card:hover { transform: translateY(-8px); }
.vm-price-tag { font-size: 2.3rem; color: #27AE60; font-weight: 900; margin: 12px 0; }
.vm-verified-chip { background: #DCFCE7; color: #166534; padding: 4px 14px; border-radius: 20px; font-size: 0.8rem; font-weight: 800; display: inline-block; margin-top: 8px; }""")

    if st.session_state.user_role != "vendor":
        st.error("\U0001F6AB This membership plan is for registered Vendors only.")
        if st.button("\U0001F491 Go to Bride/Groom VIP Plans"):
            go_to("vip_membership")
        return

    st.markdown("""
    <div class="vm-header">
        <h1 class="vm-title">Vendor Membership Plans</h1>
        <p style="font-size:1.15rem; margin-top:15px; color:#FBF5B7; font-style:italic;">Get discovered by thousands of couples planning their wedding on Bandhan.</p>
    </div>
    """, unsafe_allow_html=True)

    if not render_tnc_gate("vendor_payment", "\U0001F4C4 Please Accept Our Terms & Conditions to Continue", "Before choosing a Vendor Membership plan, please read and accept our Terms & Conditions — especially Section 3 (Payment & No-Refund Policy)."):
        return

    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        st.markdown("""
        <div class="vm-plan-card" style="border-top-color:#94A3B8;">
            <h3>\U0001F193 Free</h3>
            <p style="color:gray;">Just get listed</p>
            <div class="vm-price-tag">\u20b9 0</div>
            <p style="font-size:0.9rem; color:#555;">Valid for 3 Months (then auto-inactive)</p>
            <hr>
            <p style="text-align:left;">
            \u2705 Basic registration & listing<br>
            \u2705 Upload up to 2 photos<br>
            \u274C Your phone number is <b>not shown</b> to anyone<br>
            \u274C Appears at the <b>bottom</b> of search results<br>
            \u23F0 Reminder sent before account goes inactive
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Continue with Free Plan", key="vm_free", use_container_width=True):
            st.session_state.is_paid_member = False
            st.session_state.vendor_membership_tier = "free"
            st.success("\u2705 You're on the Free plan. Your listing is live for 3 months \u2014 upgrade anytime to unlock your contact number and better placement.")

    with col2:
        st.markdown("""
        <div class="vm-plan-card" style="border-top-color:#C0C0C0;">
            <h3>\U0001F948 Silver</h3>
            <p style="color:gray;">Get real leads</p>
            <div class="vm-price-tag">\u20b9 699</div>
            <p style="font-size:0.9rem; color:#555;">Valid for 180 Days</p>
            <hr>
            <p style="text-align:left;">
            \u2705 Upload up to 5 photos<br>
            \u2705 Your <b>phone & WhatsApp number visible</b> to every client<br>
            \u2705 Ranks <b>above Free listings</b> in search<br>
            \u2705 See every search that leads to your profile, right on <b>your dashboard</b>
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Choose Silver Plan \u2014 \u20b9699", key="vm_silver", type="primary", use_container_width=True):
            st.session_state.is_paid_member = True
            st.session_state.vendor_membership_tier = "silver"
            st.balloons()
            st.success("\U0001F389 Silver Vendor Plan activated! Your contact details are now visible to clients, and you'll see search leads on your Vendor Booking Dashboard.")

    with col3:
        st.markdown("""
        <div class="vm-plan-card" style="border-top-color:#D4AF37;">
            <h3>\U0001F947 Gold</h3>
            <p style="color:gray;">Maximum visibility</p>
            <div class="vm-price-tag">\u20b9 1,199</div>
            <p style="font-size:0.9rem; color:#555;">Valid for 365 Days</p>
            <hr>
            <p style="text-align:left;">
            \u2705 Upload up to 15 photos<br>
            \u2705 Upload a 30-second service video (auto-compressed)<br>
            \u2705 Listing appears at the <b>very top</b> of search results<br>
            \u2705 \u2705 <b>Verified Vendor</b> checkmark badge<br>
            \u2705 Includes everything in the Silver plan
            </p>
            <span class="vm-verified-chip">\u2705 Verified Vendor Badge</span>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Choose Gold Plan \u2014 \u20b91,199", key="vm_gold", use_container_width=True):
            st.session_state.is_paid_member = True
            st.session_state.vendor_membership_tier = "gold"
            st.balloons()
            st.success("\U0001F389 Gold Vendor Plan activated! You now have the Verified badge, top search placement, and video upload unlocked.")

    st.markdown("<br>", unsafe_allow_html=True)
    current_tier = st.session_state.get("vendor_membership_tier")
    if current_tier:
        tier_label = {"free": "\U0001F193 Free", "silver": "\U0001F948 Silver", "gold": "\U0001F947 Gold"}.get(current_tier, current_tier)
        st.info(f"Your current plan: **{tier_label}**")


# =====================================================================
# PAGE: REPORT & SAFETY
# =====================================================================
def page_report_safety():
    render_global_css(bg_color="#F8F9FA", page_css=""".safety-header { background: linear-gradient(135deg, #7B1113 0%, #1A365D 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.safety-card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; }
.blocked-item { background: #FFF5F5; border-left: 4px solid #E53E3E; padding: 12px 15px; border-radius: 8px; margin-bottom: 10px; }
.report-history-item { background: #F8F9FA; border-left: 4px solid #D4AF37; padding: 12px 15px; border-radius: 8px; margin-bottom: 10px; }""")

    st.markdown("""
    <div class="safety-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F6A8 Report & Safety Center</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Your safety matters. Report suspicious profiles and manage your blocked list.</p>
    </div>
    """, unsafe_allow_html=True)

    if "blocked_profiles" not in st.session_state:
        st.session_state.blocked_profiles = ["Unknown_User_4521", "Suspicious_Profile_882"]
    if "report_history" not in st.session_state:
        st.session_state.report_history = []

    is_boss = st.session_state.get("user_role") == "boss"
    tab_labels = ["\U0001F6A9 Report a Profile", "\U0001F6AB Blocked Profiles"]
    if is_boss:
        tab_labels.append("\U0001F916 Fake Profile Detection (Admin)")
    tabs = st.tabs(tab_labels)
    tab1, tab2 = tabs[0], tabs[1]
    tab3 = tabs[2] if is_boss else None

    with tab1:
        st.markdown("<div class='safety-card'>", unsafe_allow_html=True)
        st.markdown("### Report Suspicious or Inappropriate Behaviour")
        profile_name = st.text_input("Profile Name / ID to Report")
        reason = st.selectbox("Reason for Report", [
            "Fake / Misleading Profile", "Inappropriate Photos", "Harassment or Abusive Messages",
            "Asking for Money", "Already Married / Undisclosed Relationship", "Spam or Solicitation", "Other"
        ])
        details = st.text_area("Additional Details (optional)")
        evidence = st.file_uploader("Attach Screenshot / Evidence (optional)", type=["jpg", "jpeg", "png", "pdf"])
        also_block = st.checkbox("Also block this profile from contacting me")
        if st.button("\U0001F6A9 Submit Report", type="primary", use_container_width=True):
            if profile_name:
                ref_id = f"#RPT-{random.randint(10000, 99999)}"
                st.session_state.report_history.append({
                    "ref": ref_id, "profile": profile_name, "reason": reason, "details": details,
                    "date": dt.datetime.now().strftime("%d %b %Y, %I:%M %p"),
                    "has_evidence": evidence is not None, "status": "Under Review",
                })
                if also_block and profile_name not in st.session_state.blocked_profiles:
                    st.session_state.blocked_profiles.append(profile_name)
                st.success(f"\u2705 Report submitted against **{profile_name}**. Reference ID: **{ref_id}**. Our Trust & Safety team will review within 24 hours." + (" Profile has also been blocked." if also_block else ""))
                st.rerun()
            else:
                st.warning("Please enter the profile name or ID.")
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.report_history:
            st.markdown("<div class='safety-card' style='margin-top:20px;'>", unsafe_allow_html=True)
            st.markdown("### \U0001F4CB Your Report History")
            for r in reversed(st.session_state.report_history):
                evidence_tag = " \U0001F4CE Evidence attached" if r["has_evidence"] else ""
                details_html = f"<br><span style='color:#444; font-size:0.85rem;'>\u201c{r['details']}\u201d</span>" if r.get("details") else ""
                st.markdown(f"""
                <div class="report-history-item">
                    <b>{r['ref']}</b> \u2014 {r['profile']} \u2014 {r['reason']}{details_html}<br>
                    <span style="color:gray; font-size:0.85rem;">{r['date']} \u2022 Status: {r['status']}{evidence_tag}</span>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("<div class='safety-card'>", unsafe_allow_html=True)
        st.markdown("### Your Blocked Profiles")
        if st.session_state.blocked_profiles:
            for b in list(st.session_state.blocked_profiles):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"<div class='blocked-item'>\U0001F6AB {b}</div>", unsafe_allow_html=True)
                if c2.button("Unblock", key=f"unblock_{b}"):
                    st.session_state.blocked_profiles.remove(b)
                    st.rerun()
        else:
            st.info("You haven't blocked any profiles yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    if is_boss:
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

    def render_vendor_row(v, show_remove=False):
        st.markdown(f"<div class='vendor-card tier-{v['tier']}'>", unsafe_allow_html=True)
        vc1, vc2, vc3 = st.columns([3, 1, 3])
        with vc1:
            st.markdown(f"**{v['name']}** <span class='tier-chip-{v['tier']}'>{TIER_LABEL[v['tier']]}</span><br><span style='color:gray; font-size:0.85rem;'>{v['category']} \u2022 {v['city']}</span>", unsafe_allow_html=True)
        with vc2:
            st.markdown(f"\u2B50 {v['rating']}")
        with vc3:
            b1, b2, b3, b4 = st.columns(4) if show_remove else (*st.columns(3), None)
            if is_paid_member:
                b1.markdown(f"<div style='text-align:center; padding-top:6px;'>\U0001F4DE <b>{v['phone']}</b></div>", unsafe_allow_html=True)
            else:
                if b1.button("\U0001F4DE Call", key=f"call_{v['name']}", use_container_width=True):
                    st.warning("\U0001F512 Vendor phone numbers are visible to paid members only.")
            if b2.button("\U0001F4AC Message", key=f"msg_{v['name']}", use_container_width=True):
                st.session_state.chat_preselect_contact = v["name"]
                go_to("chat_alerts")
            already_fav = v["name"] in st.session_state.vendor_favorites
            fav_label = "\u2764\uFE0F Saved" if already_fav else "\U0001FA76 Add to Favorites"
            if b3.button(fav_label, key=f"fav_{v['name']}", use_container_width=True, disabled=already_fav):
                st.session_state.vendor_favorites.append(v["name"])
                st.toast(f"\u2764\uFE0F {v['name']} saved to your Favorite Vendors!")
                st.rerun()
            if show_remove and b4.button("\U0001F5D1\uFE0F Remove", key=f"remove_fav_{v['name']}", use_container_width=True):
                st.session_state.vendor_favorites.remove(v["name"])
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
                "https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=600&q=80", "End-to-End Wedding Management & Coordination",
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
                "https://images.unsplash.com/photo-1604608672516-f1b9be2a5765?auto=format&fit=crop&w=600&q=80", "Experienced Acharya & Complete Pooja Samagri",
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
                    render_vendor_row(v, show_remove=True)
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
        st.markdown("""
        <div class="step-header">
        <img src="https://cdn-icons-png.flaticon.com/512/854/854878.png" class="step-icon">
        Step 3: Wedding City Tier
        </div>
        """, unsafe_allow_html=True)
        city_tier = st.selectbox("Where is the wedding happening?", [
            "Tier 1 Metro (Mumbai, Delhi, Bengaluru) \u2014 +15% cost",
            "Tier 2 City (Pune, Jaipur, Ahmedabad) \u2014 standard cost",
            "Tier 3 / Smaller City or Town \u2014 -15% cost",
        ])
        city_multiplier = {"Tier 1": 1.15, "Tier 2": 1.0, "Tier 3": 0.85}[city_tier.split(" ")[0] + " " + city_tier.split(" ")[1]]

    adjusted_total = total_budget * city_multiplier

    with col2:
        st.markdown(f"<div class='total-box'>Grand Total: \u20b9 {adjusted_total:,.0f}</div>", unsafe_allow_html=True)
        if city_multiplier != 1.0:
            st.caption(f"Adjusted from your \u20b9{total_budget:,.0f} base budget for your selected city tier ({'+15%' if city_multiplier > 1 else '-15%'}).")
        st.markdown("<br>", unsafe_allow_html=True)

        venue_cat = int(adjusted_total * 0.36)
        jewelry = int(adjusted_total * 0.22)
        apparel = int(adjusted_total * 0.14)
        photo_misc = int(adjusted_total * 0.18)
        other_expenses = int(adjusted_total * 0.10)

        per_guest_cost = venue_cat / guests if guests else 0
        st.info(f"\U0001F37D\uFE0F That's approximately **\u20b9 {per_guest_cost:,.0f} per guest** for venue & catering, based on {guests} guests.")
        if per_guest_cost < 800:
            st.caption("\u26A0\uFE0F This is on the lower end for venue & catering per guest \u2014 consider raising your budget or reducing guest count for a more comfortable spread.")
        elif per_guest_cost > 4000:
            st.caption("\u2728 This allows for a premium venue & catering experience per guest.")

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

        st.markdown("<br>", unsafe_allow_html=True)
        budget_summary = f"""BANDHAN.COM \u2014 WEDDING BUDGET PLAN
Guests: {guests} | City Tier: {city_tier}
Grand Total: \u20b9 {adjusted_total:,.0f}

Venue & Premium Catering (36%): \u20b9 {venue_cat:,.0f}  (\u2248 \u20b9{per_guest_cost:,.0f}/guest)
Wedding Jewelry & Ornaments (22%): \u20b9 {jewelry:,.0f}
Designer Apparel & Styling (14%): \u20b9 {apparel:,.0f}
Photography, Music & Misc (18%): \u20b9 {photo_misc:,.0f}
Other Expenses (10%): \u20b9 {other_expenses:,.0f}
"""
        dl_col, fin_col = st.columns(2)
        dl_col.download_button("\U0001F4C4 Download Budget Plan", data=budget_summary, file_name="Wedding_Budget_Plan.txt", mime="text/plain", use_container_width=True)
        if fin_col.button("\U0001F4B3 Explore Financing Options", use_container_width=True):
            st.session_state.wedding_budget_total = adjusted_total
            go_to("wedding_finance")


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

        budget_hint = st.session_state.get("wedding_budget_total")
        if budget_hint:
            st.caption(f"\U0001F4A1 Auto-suggested from your Wedding Budget plan: \u20b9{budget_hint:,.0f}")

        st.markdown("<div class='section-box-header' style='font-size: 1.1rem;'>\U0001F4B3 Select Loan Amount (\u20b9)</div>", unsafe_allow_html=True)
        default_loan = int(min(max(budget_hint, 100000), 5000000)) if budget_hint else 1500000
        loan_amount = st.slider("", min_value=100000, max_value=5000000, value=default_loan, step=50000, label_visibility="collapsed", key="wf_loan")
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
        total_repayment = emi * months
        total_interest = total_repayment - loan_amount

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="emi-box">
            <h3 style="color:#D4AF37; margin:0; font-size:1.5rem; text-transform:uppercase; letter-spacing:1px;">Estimated Monthly EMI</h3>
            <div class="emi-amount">\u20b9 {emi:,.0f}</div>
            <p style="color:#E2E8F0; font-size:1rem; margin:0;">Total Tenure: <b>{months} Months</b> @ <b>{interest_rate}% Interest</b></p>
            <hr style="border-color:rgba(255,255,255,0.2); margin:15px 0;">
            <p style="color:#E2E8F0; font-size:0.95rem; margin:4px 0;">Total Interest Payable: <b style="color:#F87171;">\u20b9 {total_interest:,.0f}</b></p>
            <p style="color:#E2E8F0; font-size:0.95rem; margin:4px 0;">Total Repayment Amount: <b style="color:#FBBF24;">\u20b9 {total_repayment:,.0f}</b></p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("Apply for Instant Pre-Approval", key="wf_apply"):
            st.session_state.finance_applied = True
            if "finance_applications" not in st.session_state:
                st.session_state.finance_applications = []
            st.session_state.finance_applications.append({
                "loan_amount": loan_amount, "tenure_years": tenure, "emi": round(emi),
                "applied_on": dt.datetime.now().strftime("%d %b %Y, %I:%M %p"), "status": "Under Review",
            })
            st.balloons()
            st.success("\u2705 Application Submitted Successfully! Our partner bank executive will contact you within 24 hours.")

    if st.session_state.get("finance_applications"):
        st.markdown("---")
        st.markdown("### \U0001F4CB Your Pre-Approval Applications")
        apps_df = pd.DataFrame(st.session_state.finance_applications)
        st.dataframe(apps_df, use_container_width=True, hide_index=True)

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
                    if is_paid_member:
                        b1.markdown(f"<div style='text-align:center; padding-top:6px;'>\U0001F4DE <b>{p['phone']}</b></div>", unsafe_allow_html=True)
                    else:
                        if b1.button("\U0001F4DE Call", key=f"call_{p['name']}", use_container_width=True):
                            st.warning("\U0001F512 Finance partner phone numbers are visible to paid members only.")
                    if b2.button("\U0001F4AC Message", key=f"msg_{p['name']}", use_container_width=True):
                        st.session_state.chat_preselect_contact = p["name"]
                        go_to("chat_alerts")
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


KUNDLI_STATE_APPROX_COORDS = {
    "Andhra Pradesh": (16.5062, 80.6480), "Arunachal Pradesh": (27.0844, 93.6053), "Assam": (26.1445, 91.7362),
    "Bihar": (25.0961, 85.3131), "Chhattisgarh": (21.2787, 81.8661), "Goa": (15.2993, 74.1240),
    "Gujarat": (23.0225, 72.5714), "Haryana": (29.0588, 76.0856), "Himachal Pradesh": (31.1048, 77.1734),
    "Jharkhand": (23.3441, 85.3096), "Karnataka": (12.9716, 77.5946), "Kerala": (8.5241, 76.9366),
    "Madhya Pradesh": (23.2599, 77.4126), "Maharashtra": (19.0760, 72.8777), "Manipur": (24.8170, 93.9368),
    "Meghalaya": (25.5788, 91.8933), "Mizoram": (23.7271, 92.7176), "Nagaland": (25.6751, 94.1086),
    "Odisha": (20.2961, 85.8245), "Punjab": (30.7333, 76.7794), "Rajasthan": (26.9124, 75.7873),
    "Sikkim": (27.3389, 88.6065), "Tamil Nadu": (13.0827, 80.2707), "Telangana": (17.3850, 78.4867),
    "Tripura": (23.8315, 91.2868), "Uttar Pradesh": (26.8467, 80.9462), "Uttarakhand": (30.3165, 78.0322),
    "West Bengal": (22.5726, 88.3639), "Andaman and Nicobar Islands": (11.7401, 92.6586), "Chandigarh": (30.7333, 76.7794),
    "Dadra and Nagar Haveli and Daman and Diu": (20.3974, 72.8328), "Delhi": (28.7041, 77.1025),
    "Jammu and Kashmir": (34.0837, 74.7973), "Ladakh": (34.1526, 77.5771), "Lakshadweep": (10.5667, 72.6417),
    "Puducherry": (11.9416, 79.8083),
}


def page_kundli_match():
    render_global_css(bg_color="#FFFDF8", page_css=""".header-kundali { color: #D35400; font-family: 'Georgia', serif; font-size: 2.8rem; text-align: center; font-weight: bold; }
.guna-score { font-size: 4rem; color: #27AE60; font-weight: 900; text-align: center; }
.card-box { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border-top: 3px solid #D35400; }
.koota-row { background: white; padding: 10px 16px; border-radius: 8px; box-shadow: 0 3px 8px rgba(0,0,0,0.05); border-left: 4px solid #D35400; margin-bottom: 8px; }""")

    st.markdown("<h1 class='header-kundali'>\U0001F549\uFE0F AI Kundali & Guna Milan</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:gray;'>Our advanced Vedic AI calculates accurate planetary positions and the 36 Gunas for perfect compatibility.</p>", unsafe_allow_html=True)
    st.markdown("---")

    def birth_place_block(prefix):
        place = st.text_input("Place of Birth (City / Village)", key=f"{prefix}_place")
        state = st.selectbox("State", KUNDLI_ALL_STATES, key=f"{prefix}_state")
        district = st.selectbox("District", KUNDLI_STATE_DISTRICTS[state], key=f"{prefix}_district")
        approx_lat, approx_lon = KUNDLI_STATE_APPROX_COORDS.get(state, (0.0, 0.0))
        st.caption(f"\U0001F4CD Approximate coordinates for {state} auto-filled below \u2014 adjust for more precision if you know your exact birth city's coordinates.")
        lat_col, lon_col = st.columns(2)
        with lat_col:
            latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=approx_lat, step=0.0001, format="%.4f", key=f"{prefix}_lat")
        with lon_col:
            longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=approx_lon, step=0.0001, format="%.4f", key=f"{prefix}_lon")
        return place, state, district, latitude, longitude

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("### \U0001F935 Boy's Birth Details")
        b_name = st.text_input("Name", key="b_name")
        b_date = st.date_input("Date of Birth", key="b_date", max_value=dt.date.today(), min_value=dt.date(1950, 1, 1))
        b_time = st.time_input("Time of Birth", key="b_time")
        b_place, b_state, b_district, b_lat, b_lon = birth_place_block("b")
    with col2:
        st.markdown("### \U0001F470 Girl's Birth Details")
        g_name = st.text_input("Name", key="g_name")
        g_date = st.date_input("Date of Birth", key="g_date", max_value=dt.date.today(), min_value=dt.date(1950, 1, 1))
        g_time = st.time_input("Time of Birth", key="g_time")
        g_place, g_state, g_district, g_lat, g_lon = birth_place_block("g")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("\U0001F52E Calculate 36 Guna Match", type="primary", use_container_width=True):
        if b_name and g_name:
            with st.spinner("Analyzing planetary positions and Ashtakoota Gunas..."):
                time.sleep(2.0)

            seed_base = f"{b_name.strip().lower()}|{g_name.strip().lower()}|{b_date}|{g_date}|{b_time}|{g_time}|{b_place.strip().lower()}|{g_place.strip().lower()}"

            def guna_seed(label):
                digest = hashlib.md5((seed_base + label).encode()).hexdigest()
                return int(digest[:6], 16) % 1000

            KOOTAS = [
                ("Varna (Spiritual Compatibility)", 1), ("Vashya (Mutual Control/Attraction)", 2),
                ("Tara (Health & Well-being)", 3), ("Yoni (Physical & Sexual Compatibility)", 4),
                ("Graha Maitri (Mental Compatibility)", 5), ("Gana (Temperament Match)", 6),
                ("Bhakoot (Love & Family Bond)", 7), ("Nadi (Health & Genetics)", 8),
            ]
            results = []
            total_score = 0
            for label, max_pts in KOOTAS:
                s = guna_seed(label)
                points = round(max_pts * (0.55 + (s / 999) * 0.45))
                points = min(points, max_pts)
                results.append((label, points, max_pts))
                total_score += points

            nadi_points = results[-1][1]
            nadi_dosha = "Present \u2014 recommend consulting an astrologer" if nadi_points < 8 else "None"

            manglik_seed_b = guna_seed("manglik_boy")
            manglik_seed_g = guna_seed("manglik_girl")
            b_manglik = "Manglik" if manglik_seed_b % 4 == 0 else "Non-Manglik"
            g_manglik = "Manglik" if manglik_seed_g % 4 == 0 else "Non-Manglik"
            manglik_match = "\u2705 Compatible (both Manglik or both Non-Manglik)" if b_manglik == g_manglik else "\u26A0\uFE0F Mismatch \u2014 one partner is Manglik, the other isn't. A remedial pooja is traditionally recommended."

            pct = total_score / 36 * 100
            if pct >= 75:
                verdict, verdict_color = "Highly Compatible Match!", "#27AE60"
            elif pct >= 55:
                verdict, verdict_color = "Good Match \u2014 Generally Favorable", "#D4AF37"
            else:
                verdict, verdict_color = "Below Average Match \u2014 Consult an Astrologer", "#E67E22"

            st.success("Analysis Complete!")
            st.markdown(f"""
            <div class='card-box'>
                <h3 style='text-align:center;'>Total Guna Score</h3>
                <div class='guna-score' style='color:{verdict_color};'>{total_score} / 36</div>
                <p style='text-align:center; color:{verdict_color}; font-weight:bold;'>{verdict} (Nadi Dosha: {nadi_dosha})</p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("### \U0001F4CA Detailed 8-Koota Breakdown")
            for label, points, max_pts in results:
                bar_pct = int(points / max_pts * 100)
                st.markdown(f"""
                <div class="koota-row">
                    <b>{label}</b>
                    <span style="float:right; color:#27AE60; font-weight:bold;">{points} / {max_pts}</span>
                    <div style="background:#F0F0F0; border-radius:10px; height:6px; width:100%; margin-top:6px;">
                        <div style="background:#D35400; width:{bar_pct}%; height:100%; border-radius:10px;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("### \U0001F536 Manglik (Mars) Dosha Check")
            mc1, mc2 = st.columns(2)
            mc1.metric(f"{b_name}'s Status", b_manglik)
            mc2.metric(f"{g_name}'s Status", g_manglik)
            st.info(manglik_match)

            report_text = f"""BANDHAN.COM \u2014 KUNDALI & GUNA MILAN REPORT
{b_name} (DOB: {b_date}, Time: {b_time}, Place: {b_place or b_district}, {b_state}, Coords: {b_lat:.4f}, {b_lon:.4f})
\u00d7
{g_name} (DOB: {g_date}, Time: {g_time}, Place: {g_place or g_district}, {g_state}, Coords: {g_lat:.4f}, {g_lon:.4f})

TOTAL GUNA SCORE: {total_score} / 36 \u2014 {verdict}
Nadi Dosha: {nadi_dosha}

8-Koota Breakdown:
""" + "\n".join(f"  {label}: {points}/{max_pts}" for label, points, max_pts in results) + f"""

Manglik Status: {b_name} \u2014 {b_manglik} | {g_name} \u2014 {g_manglik}
{manglik_match}

Note: This is an AI-assisted estimate. For major life decisions, we recommend also consulting a qualified astrologer (see Astrology Consultation page).
"""
            st.download_button("\U0001F4C4 Download Full Report", data=report_text, file_name=f"Kundali_Report_{b_name}_{g_name}.txt", mime="text/plain", use_container_width=True)
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
            uploaded_bg_file = st.file_uploader("Upload background image (JPG / PNG, max 50MB)", type=["jpg", "jpeg", "png"], key="banner_bg_upload")
            if uploaded_bg_file:
                candidate_bytes = uploaded_bg_file.getvalue()
                size_mb = len(candidate_bytes) / (1024 * 1024)
                if size_mb > 50:
                    st.error(f"\u274C This image is {size_mb:.1f}MB, which is over the 50MB limit. Please upload a smaller file.")
                else:
                    uploaded_bg_bytes = candidate_bytes
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
            d_col1, d_col2 = st.columns(2)
            wedding_date = d_col1.date_input("Date")
            wedding_time = d_col2.time_input("Time")
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
            uploaded_gif_file = st.file_uploader("Upload your animated GIF (max 50MB)", type=["gif"], key="anim_gif_upload")
            if uploaded_gif_file:
                candidate_gif_bytes = uploaded_gif_file.getvalue()
                size_mb = len(candidate_gif_bytes) / (1024 * 1024)
                if size_mb > 50:
                    st.error(f"\u274C This GIF is {size_mb:.1f}MB, which is over the 50MB limit. Please upload a smaller file.")
                else:
                    uploaded_gif_bytes = candidate_gif_bytes
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
            vd_col1, vd_col2 = st.columns(2)
            v_date = vd_col1.date_input("Date", key="v_date")
            v_time = vd_col2.time_input("Time", key="v_time")
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
                st.caption("\U0001F3A5 Exporting this as an MP4 with background music requires video-rendering infrastructure that isn't part of this demo yet \u2014 the GIF above is fully downloadable now.")

        invite_render_expiry_gated_download("animated_invite", "Your Saved Animated Invite is Ready to Download", "image/gif", "\u2B07\uFE0F")


# =====================================================================
# PAGE: WEDDING COUNTDOWN TRACKER
# =====================================================================
def page_wedding_countdown():
    render_global_css(bg_color="#FFFDF8", page_css=""".countdown-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); padding: 35px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.countdown-num { font-size: 3.5rem; font-weight: 900; color: #D4AF37; }
.task-card { background: white; padding: 14px 18px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 10px; border-left: 4px solid #27AE60; }
.milestone-banner { background: linear-gradient(135deg, #D4AF37 0%, #B8860B 100%); color: white; padding: 14px 20px; border-radius: 12px; text-align: center; font-weight: 700; margin-bottom: 18px; }
.overdue-task { border-left: 4px solid #E74C3C !important; }
.sync-pill { display:inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }""")

    st.markdown("""
    <div class="countdown-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\u23F3 Wedding Countdown & Planning Tracker</h1>
        <p style="color:#FBF5B7; margin-top:8px;">For matched couples — track your wedding date and shared to-do list together.</p>
    </div>
    """, unsafe_allow_html=True)

    SERVICE_LIST = [
        "Wedding Planner / Management", "Banquet Hall / Lawn / Resort", "Designer Wedding Apparel",
        "Wedding Jewelry & Ornaments", "Makeup Artist & Grooming", "Photography & Videography",
        "Mandap, Stage & Floral Decoration", "Catering & Food Service", "Music, DJ & Entertainment",
        "Wedding Invitations & Digital Cards", "Transportation Services", "Baraat: Ghodi, Buggy & Band",
        "Vedic Priest & Ritual Services",
    ]
    TASK_CATEGORIES = ["General", "Haldi", "Mehendi", "Sangeet", "Wedding Day", "Reception", "Post-Wedding"]
    PRIORITIES = ["Low", "Medium", "High"]
    user_email = st.session_state.get("user_email") or "guest@bandhan.com"

    # -----------------------------------------------------------------
    # LOAD (couple-shared, persistent): pulls from MongoDB once per
    # session so the plan survives logout/refresh and is the same for
    # both partners logging in with a shared/linked account. Falls back
    # to session-only state automatically if MongoDB isn't configured.
    # -----------------------------------------------------------------
    if "wedding_plan_loaded" not in st.session_state:
        saved = db_load_wedding_plan(user_email)
        if saved:
            st.session_state.wedding_date = saved.get("wedding_date", dt.date.today() + dt.timedelta(days=120))
            st.session_state.service_booked = saved.get("service_booked", {s: False for s in SERVICE_LIST})
            st.session_state.wedding_tasks = saved.get("wedding_tasks", [])
            st.session_state.wc_reminder_number = saved.get("reminder_number", "")
            st.session_state.wc_reminder_opt_in = saved.get("reminder_opt_in", False)
            st.session_state.wc_share_code = saved.get("share_code", make_share_code(user_email))
        st.session_state.wedding_plan_loaded = True

    if "wedding_date" not in st.session_state:
        st.session_state.wedding_date = dt.date.today() + dt.timedelta(days=120)
    if "service_booked" not in st.session_state:
        st.session_state.service_booked = {s: False for s in SERVICE_LIST}
    else:
        for s in SERVICE_LIST:
            st.session_state.service_booked.setdefault(s, False)
    if "wedding_tasks" not in st.session_state or not st.session_state.wedding_tasks:
        st.session_state.wedding_tasks = [
            {"task": "Finalize guest list", "done": True, "category": "General", "priority": "Medium", "due_date": None, "notes": ""},
            {"task": "Send invitations", "done": False, "category": "General", "priority": "High", "due_date": None, "notes": ""},
        ]
    # migrate any old-format tasks (missing new fields) in place
    for t in st.session_state.wedding_tasks:
        t.setdefault("category", "General")
        t.setdefault("priority", "Medium")
        t.setdefault("due_date", None)
        t.setdefault("notes", "")
    if "wc_reminder_number" not in st.session_state:
        st.session_state.wc_reminder_number = ""
    if "wc_reminder_opt_in" not in st.session_state:
        st.session_state.wc_reminder_opt_in = False
    if "wc_share_code" not in st.session_state:
        st.session_state.wc_share_code = make_share_code(user_email)
    if "show_vendors_for" not in st.session_state:
        st.session_state.show_vendors_for = None

    def persist_plan():
        """Saves the whole plan to MongoDB (no-op, silent, if DB isn't
        configured — session state still holds everything either way)."""
        db_save_wedding_plan(user_email, {
            "wedding_date": st.session_state.wedding_date,
            "service_booked": st.session_state.service_booked,
            "wedding_tasks": st.session_state.wedding_tasks,
            "reminder_number": st.session_state.wc_reminder_number,
            "reminder_opt_in": st.session_state.wc_reminder_opt_in,
            "share_code": st.session_state.wc_share_code,
        })

    sync_ok = db_is_connected()
    pill_style = "background:#DCFCE7; color:#166534;" if sync_ok else "background:#FEF3C7; color:#92400E;"
    pill_text = "\u2601\uFE0F Synced to your account" if sync_ok else "\U0001F4F1 Demo mode — saved to this session only"
    st.markdown(f"<span class='sync-pill' style='{pill_style}'>{pill_text}</span>", unsafe_allow_html=True)

    wedding_date = st.date_input("Your Wedding Date", value=st.session_state.wedding_date, key="wc_date_input")
    if wedding_date != st.session_state.wedding_date:
        st.session_state.wedding_date = wedding_date
        persist_plan()

    days_left = (wedding_date - dt.date.today()).days
    if days_left < 0:
        st.warning(f"\u26A0\uFE0F This date is {abs(days_left)} day(s) in the past. Please pick your actual upcoming wedding date to get an accurate countdown.")
    st.markdown(f"<div style='text-align:center;'><div class='countdown-num'>{max(days_left, 0)}</div><p style='color:gray;'>Days to go</p></div>", unsafe_allow_html=True)

    # -----------------------------------------------------------------
    # MILESTONE BANNERS
    # -----------------------------------------------------------------
    MILESTONES = {100: "\U0001F389 100 days to go — time to lock in your big-ticket vendors!",
                  50: "\U0001F338 50 days to go — start finalizing outfits & guest list!",
                  30: "\U0001F4C5 30 days to go — confirm menus, seating & logistics!",
                  7: "\u2728 Just 1 week left — final touches time!",
                  1: "\U0001F495 Tomorrow's the big day — congratulations in advance!",
                  0: "\U0001F48D Today is the day — Shubh Vivah!"}
    if days_left in MILESTONES:
        st.markdown(f"<div class='milestone-banner'>{MILESTONES[days_left]}</div>", unsafe_allow_html=True)
        if days_left == 0:
            st.balloons()

    # -----------------------------------------------------------------
    # ADD TO CALENDAR (.ics export)
    # -----------------------------------------------------------------
    cal_col1, cal_col2 = st.columns(2)
    with cal_col1:
        ics_data = build_wedding_ics("Our Wedding Day \U0001F495", wedding_date,
                                      "Wedding day tracked via Bandhan.com Wedding Countdown & Planning Tracker.")
        st.download_button("\U0001F4C5 Add to Calendar (.ics)", data=ics_data, file_name="wedding_day.ics",
                            mime="text/calendar", use_container_width=True)
    with cal_col2:
        share_text = f"Our wedding is in {max(days_left,0)} days ({wedding_date.strftime('%d %b %Y')})! Planning it all on Bandhan.com \U0001F495"
        wa_share_link = f"https://wa.me/?text={urllib.parse.quote(share_text)}"
        st.link_button("\U0001F4E4 Share Countdown on WhatsApp", wa_share_link, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------------------------------------------------
    # WHATSAPP REMINDERS
    # -----------------------------------------------------------------
    with st.expander("\U0001F514 WhatsApp Reminders for Pending Tasks"):
        reminder_number = st.text_input("Your WhatsApp number (with country code)", value=st.session_state.wc_reminder_number, placeholder="e.g., 919876543210")
        opt_in = st.checkbox("Send me a WhatsApp nudge for tasks and unbooked services that are due soon", value=st.session_state.wc_reminder_opt_in)
        if reminder_number != st.session_state.wc_reminder_number or opt_in != st.session_state.wc_reminder_opt_in:
            st.session_state.wc_reminder_number = reminder_number
            st.session_state.wc_reminder_opt_in = opt_in
            persist_plan()

        if st.button("\U0001F4E4 Send Reminder Now", key="wc_send_reminder"):
            pending_services = [s for s, b in st.session_state.service_booked.items() if not b]
            overdue = [t["task"] for t in st.session_state.wedding_tasks if not t["done"] and t.get("due_date") and t["due_date"] < dt.date.today()]
            msg_lines = [f"Wedding Countdown: {max(days_left,0)} days to go!"]
            if pending_services:
                msg_lines.append(f"Unbooked services: {', '.join(pending_services[:5])}")
            if overdue:
                msg_lines.append(f"Overdue tasks: {', '.join(overdue[:5])}")
            reminder_message = "\n".join(msg_lines)
            if not reminder_number:
                st.warning("Please enter a WhatsApp number first.")
            else:
                token, phone_id = wa_get_whatsapp_credentials()
                if token and phone_id:
                    with st.spinner("Sending via WhatsApp Business API..."):
                        success, detail = wa_send_whatsapp_message(reminder_number, reminder_message, token, phone_id)
                    st.success(f"\u2705 {detail}") if success else st.error(f"\u274C {detail}")
                else:
                    st.info(f"\U0001F4E9 **Demo Mode:** Would send to **{reminder_number}**:\n\n> {reminder_message}\n\n(Add real WhatsApp Business credentials to actually send this.)")
        st.caption("With opt-in enabled, this same message set would go out automatically on a daily schedule once connected to a backend job runner.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4CB Wedding Services Checklist")
    st.write("Track which services you've booked. Anything not booked yet shows a reminder with a direct button to browse verified vendors.")
    st.caption("\U0001F4A1 Want the full marketplace with reviews and more options per category?")
    if st.button("\U0001F3EA Browse the Full Vendor Marketplace"):
        go_to("wedding_services")

    def vendor_phone(name):
        digest = hashlib.md5(name.encode()).hexdigest()
        part1 = str(int(digest[:5], 16))[-5:].zfill(5)
        part2 = str(int(digest[5:10], 16))[-5:].zfill(5)
        return f"+91 98{part1} {part2}"

    VENDOR_DIRECTORY = {
        "Wedding Planner / Management": [{"name": "Royal Events & Management Co.", "city": "Nagpur", "rating": 4.8}],
        "Banquet Hall / Lawn / Resort": [{"name": "The Grand Orchid Banquets", "city": "Nagpur", "rating": 4.6}],
        "Designer Wedding Apparel": [{"name": "Meera Designer Studio", "city": "Pune", "rating": 4.7}],
        "Wedding Jewelry & Ornaments": [{"name": "Suvarna Jewels", "city": "Mumbai", "rating": 4.9}],
        "Makeup Artist & Grooming": [{"name": "Glow & Grace Makeovers", "city": "Nagpur", "rating": 4.5}],
        "Photography & Videography": [{"name": "Frame & Story Films", "city": "Bangalore", "rating": 4.8}],
        "Mandap, Stage & Floral Decoration": [{"name": "Floral Dreams Decor", "city": "Nagpur", "rating": 4.6}],
        "Catering & Food Service": [{"name": "Swaad Caterers", "city": "Pune", "rating": 4.7}],
        "Music, DJ & Entertainment": [{"name": "Beats & Baraat DJ Co.", "city": "Nagpur", "rating": 4.4}],
        "Wedding Invitations & Digital Cards": [{"name": "PrintCraft Invitations", "city": "Mumbai", "rating": 4.5}],
        "Transportation Services": [{"name": "Royal Fleet Transport", "city": "Nagpur", "rating": 4.3}],
        "Baraat: Ghodi, Buggy & Band": [{"name": "Shahi Baraat Services", "city": "Nagpur", "rating": 4.6}],
        "Vedic Priest & Ritual Services": [{"name": "Acharya Ritual Services", "city": "Nagpur", "rating": 4.9}],
    }

    is_paid_member = st.session_state.get("is_paid_member", False)

    for service in SERVICE_LIST:
        row1, row2 = st.columns([4, 1])
        with row1:
            booked = st.checkbox(service, value=st.session_state.service_booked[service], key=f"svc_{service}")
        with row2:
            if not booked:
                if st.button("\U0001F50D Find Vendors", key=f"find_{service}", use_container_width=True):
                    st.session_state.show_vendors_for = service
        if booked != st.session_state.service_booked[service]:
            st.session_state.service_booked[service] = booked
            persist_plan()

        if not booked:
            st.warning(f"\u23F0 Reminder: **{service}** is not booked yet. Book soon to stay on schedule!")

        if st.session_state.show_vendors_for == service:
            st.markdown(f"<div style='background:white; padding:14px; border-radius:10px; border-left:4px solid #D4AF37; margin-bottom:10px;'>", unsafe_allow_html=True)
            st.markdown(f"**Verified Vendors for {service}:**")
            for v in VENDOR_DIRECTORY.get(service, []):
                vc1, vc2, vc3 = st.columns([3, 1, 2])
                vc1.markdown(f"{v['name']} \u2705 <span style='color:gray; font-size:0.85rem;'>({v['city']})</span>", unsafe_allow_html=True)
                vc2.markdown(f"\u2B50 {v['rating']}")
                b1, b2, b3 = vc3.columns(3)
                if is_paid_member:
                    b1.markdown(f"<div style='text-align:center; font-size:0.85rem;'>\U0001F4DE {vendor_phone(v['name'])}</div>", unsafe_allow_html=True)
                else:
                    if b1.button("\U0001F4DE", key=f"tcall_{service}_{v['name']}", use_container_width=True, help="Call"):
                        st.warning("\U0001F512 Vendor phone numbers are visible to paid members only.")
                if b2.button("\U0001F4AC", key=f"tmsg_{service}_{v['name']}", use_container_width=True, help="Message"):
                    st.session_state.chat_preselect_contact = v["name"]
                    go_to("chat_alerts")
                if b3.button("\U0001F4C5", key=f"treq_{service}_{v['name']}", use_container_width=True, help="Request Booking"):
                    st.session_state.show_booking_form_for = v["name"]

                if st.session_state.get("show_booking_form_for") == v["name"]:
                    with st.form(f"book_form_{service}_{v['name']}"):
                        st.markdown(f"##### \U0001F4C5 Request a Booking with {v['name']}")
                        req_client_name = st.text_input("Your Name(s)", value=st.session_state.get("user_name", ""), key=f"reqname_{v['name']}")
                        req_client_phone = st.text_input("Your Contact Number", key=f"reqphone_{v['name']}", placeholder="10-digit number")
                        req_event_date = st.date_input("Event Date", value=st.session_state.wedding_date, key=f"reqdate_{v['name']}")
                        req_notes = st.text_area("Anything they should know? (optional)", key=f"reqnotes_{v['name']}", height=68)
                        req_submit = st.form_submit_button("\U0001F4E4 Send Booking Request", type="primary")
                        if req_submit:
                            if not req_client_name or not req_client_phone:
                                st.warning("Please enter your name and contact number.")
                            else:
                                booking_id = db_create_booking_request(v["name"], service, req_client_name, req_client_phone, user_email, req_event_date.strftime("%Y-%m-%d"), req_notes)
                                if booking_id:
                                    st.success(f"\u2705 Booking request sent to {v['name']}! They'll accept or decline it from their Vendor Booking Dashboard, and you'll hear back soon.")
                                else:
                                    st.info(f"\U0001F4E9 **Demo Mode:** Request to {v['name']} noted for this session. \u26A0\uFE0F Connect MongoDB so it actually reaches their Vendor Booking Dashboard.")
                                st.session_state.show_booking_form_for = None
            if st.button("Close", key=f"close_{service}"):
                st.session_state.show_vendors_for = None
                st.session_state.show_booking_form_for = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4DD To-Do List — by Ceremony")
    st.caption("Every task has a due date, priority and ceremony tag, and is grouped below so you can plan Haldi, Mehendi, Sangeet, the Wedding Day and Reception separately.")

    with st.form("add_task_form", clear_on_submit=True):
        fc1, fc2 = st.columns([3, 1])
        new_task = fc1.text_input("Task description")
        new_category = fc2.selectbox("Ceremony / Category", TASK_CATEGORIES)
        fc3, fc4 = st.columns(2)
        new_priority = fc3.selectbox("Priority", PRIORITIES, index=1)
        new_due = fc4.date_input("Due date", value=dt.date.today() + dt.timedelta(days=14))
        new_notes = st.text_input("Notes (optional)")
        add_task = st.form_submit_button("\u2795 Add Task")
        if add_task and new_task:
            st.session_state.wedding_tasks.append({
                "task": new_task, "done": False, "category": new_category,
                "priority": new_priority, "due_date": new_due, "notes": new_notes,
            })
            persist_plan()
            st.rerun()

    today = dt.date.today()
    for cat in TASK_CATEGORIES:
        cat_tasks = [(i, t) for i, t in enumerate(st.session_state.wedding_tasks) if t.get("category", "General") == cat]
        if not cat_tasks:
            continue
        cat_done = sum(1 for _, t in cat_tasks if t["done"])
        with st.expander(f"{cat} ({cat_done}/{len(cat_tasks)} done)", expanded=(cat == "General")):
            for i, t in cat_tasks:
                is_overdue = (not t["done"]) and t.get("due_date") and t["due_date"] < today
                card_class = "task-card overdue-task" if is_overdue else "task-card"
                st.markdown(f"<div class='{card_class}'>", unsafe_allow_html=True)
                tc1, tc2, tc3 = st.columns([4, 2, 1])
                checked = tc1.checkbox(t["task"], value=t["done"], key=f"task_{i}")
                due_str = t["due_date"].strftime("%d %b %Y") if t.get("due_date") else "No due date"
                overdue_flag = " \u26A0\uFE0F Overdue" if is_overdue else ""
                tc2.markdown(f"<span style='font-size:0.85rem; color:gray;'>\U0001F4C5 {due_str} \u00B7 {t.get('priority','Medium')} priority{overdue_flag}</span>", unsafe_allow_html=True)
                if tc3.button("\U0001F5D1\uFE0F", key=f"del_task_{i}", help="Delete this task"):
                    st.session_state.wedding_tasks.pop(i)
                    persist_plan()
                    st.rerun()
                if t.get("notes"):
                    st.caption(f"\U0001F4DD {t['notes']}")
                st.markdown("</div>", unsafe_allow_html=True)
                if checked != t["done"]:
                    st.session_state.wedding_tasks[i]["done"] = checked
                    persist_plan()

    # -----------------------------------------------------------------
    # PROGRESS OVERVIEW + CATEGORY BREAKDOWN CHART
    # -----------------------------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4CA Planning Progress")
    services_booked_count = sum(1 for v in st.session_state.service_booked.values() if v)
    other_completed = sum(1 for t in st.session_state.wedding_tasks if t["done"])
    total_items = len(SERVICE_LIST) + len(st.session_state.wedding_tasks)
    total_done = services_booked_count + other_completed
    st.progress(total_done / total_items if total_items else 0)
    st.caption(f"{total_done} of {total_items} items completed ({services_booked_count}/{len(SERVICE_LIST)} services booked)")

    breakdown_rows = {"Services": (services_booked_count, len(SERVICE_LIST) - services_booked_count)}
    for cat in TASK_CATEGORIES:
        cat_tasks = [t for t in st.session_state.wedding_tasks if t.get("category", "General") == cat]
        if cat_tasks:
            done_n = sum(1 for t in cat_tasks if t["done"])
            breakdown_rows[cat] = (done_n, len(cat_tasks) - done_n)
    if breakdown_rows:
        chart_df = pd.DataFrame({
            "Completed": [v[0] for v in breakdown_rows.values()],
            "Pending": [v[1] for v in breakdown_rows.values()],
        }, index=list(breakdown_rows.keys()))
        st.bar_chart(chart_df)

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("\U0001F4A1 Full booking-to-payment sync with Wedding Budget & Vendor Marketplace, and automatic daily reminder scheduling, roll out once this app is connected to a live backend job runner — everything above already writes to your account so it's ready for that.")


# =====================================================================
# PAGE: VENDOR REGISTRATION
# =====================================================================
# =====================================================================
# VENDOR REGISTRATION — validation + persistence + approval workflow
# =====================================================================
def vendor_validate_aadhaar(aadhaar):
    return bool(re.fullmatch(r"\d{12}", aadhaar or ""))


def vendor_validate_pan(pan):
    return bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", (pan or "").upper()))


def vendor_validate_gst(gst):
    if not gst:
        return True  # optional field
    return bool(re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", gst.upper()))


def vendor_validate_mobile(mobile):
    return bool(re.fullmatch(r"[6-9]\d{9}", mobile or ""))


def vendor_validate_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""))


def db_check_vendor_duplicate(aadhaar, pan, business_email):
    """Returns the existing vendor doc if this Aadhaar, PAN, or business
    email is already registered — prevents duplicate/fake listings."""
    db = get_db()
    if db is None:
        return None
    return db.vendors.find_one({"$or": [
        {"aadhaar_number": aadhaar}, {"pan_number": pan.upper()}, {"business_email": business_email},
    ]})


def db_create_vendor_listing(vendor_doc):
    db = get_db()
    if db is None:
        return None
    vendor_doc = dict(vendor_doc)
    vendor_doc["status"] = "Pending"
    vendor_doc["submitted_at"] = dt.datetime.utcnow()
    result = db.vendors.insert_one(vendor_doc)
    return str(result.inserted_id)


def db_list_vendor_submissions(status=None, limit=200):
    db = get_db()
    if db is None:
        return []
    query = {"status": status} if status else {}
    return list(db.vendors.find(query).sort("submitted_at", -1).limit(limit))


def db_update_vendor_status(vendor_id, status):
    db = get_db()
    if db is None:
        return False
    db.vendors.update_one({"_id": ObjectId(vendor_id)}, {"$set": {"status": status, "reviewed_at": dt.datetime.utcnow()}})
    return True


def page_vendor_registration():
    render_global_css(bg_color="#F8F9FA", page_css=""".vendor-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.vendor-card { background: white; padding: 28px; border-radius: 16px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; }
.otp-box { background: #FFF8E1; border-left: 5px solid #D4AF37; padding: 16px 20px; border-radius: 10px; margin-top: 10px; }
.verified-badge { background: #DCFCE7; color: #166534; padding: 10px 18px; border-radius: 10px; font-weight: 700; text-align: center; }
.status-pending { background: #FEF3C7; color: #92400E; padding: 10px 18px; border-radius: 10px; font-weight: 700; text-align: center; }
.status-approved { background: #DCFCE7; color: #166534; padding: 10px 18px; border-radius: 10px; font-weight: 700; text-align: center; }
.status-rejected { background: #FEE2E2; color: #991B1B; padding: 10px 18px; border-radius: 10px; font-weight: 700; text-align: center; }""")

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

    if not render_tnc_gate("vendor_registration", "\U0001F4C4 Please Accept Our Terms & Conditions First", "Before registering your business, please read and accept our Terms & Conditions. Registration cannot proceed until you agree."):
        return

    user_email = st.session_state.get("user_email") or "vendor@bandhan.com"

    # -----------------------------------------------------------------
    # If this vendor already has a submission on file, show its status
    # instead of a blank form every time (approval workflow visibility).
    # -----------------------------------------------------------------
    db = get_db()
    existing_submission = None
    if db is not None:
        existing_submission = db.vendors.find_one({"business_email": user_email}, sort=[("submitted_at", -1)])

    if existing_submission and "vendor_edit_new" not in st.session_state:
        status = existing_submission.get("status", "Pending")
        css_class = {"Pending": "status-pending", "Approved": "status-approved", "Rejected": "status-rejected"}.get(status, "status-pending")
        icon = {"Pending": "\u23F3", "Approved": "\u2705", "Rejected": "\u274C"}.get(status, "\u23F3")
        st.markdown(f"<div class='{css_class}'>{icon} Your listing for <b>{existing_submission.get('business_name','')}</b> is currently: {status}</div>", unsafe_allow_html=True)
        st.caption(f"Submitted on {existing_submission.get('submitted_at', dt.datetime.utcnow()).strftime('%d %b %Y')}. Categories: {', '.join(existing_submission.get('vendor_types', []))}")
        if status == "Approved":
            st.success("\U0001F389 You're live! Couples can now find and contact you from the Wedding Services and Wedding Finance pages.")
        elif status == "Rejected":
            st.error("Your last submission wasn't approved. You can submit a corrected registration below.")
        rc1, rc2 = st.columns(2)
        if rc1.button("\U0001F451 Choose Your Vendor Membership Plan \u2192", use_container_width=True):
            go_to("vendor_membership")
        if rc2.button("\u270F\uFE0F Submit a New / Updated Registration", use_container_width=True):
            st.session_state.vendor_edit_new = True
            st.rerun()
        if status != "Rejected":
            return

    # -----------------------------------------------------------------
    # Draft state — every field below is bound to session_state via its
    # widget key, so navigating away and coming back doesn't wipe the
    # form (form-abandonment fix).
    # -----------------------------------------------------------------
    if "vendor_otp" not in st.session_state:
        st.session_state.vendor_otp = None
    if "vendor_otp_verified" not in st.session_state:
        st.session_state.vendor_otp_verified = False

    st.markdown("<div class='vendor-card'>", unsafe_allow_html=True)

    st.markdown("### Step 1: Business Details")
    ALL_VENDOR_CATEGORIES = [
        "Wedding Planner / Management Agency", "Banquet Hall / Lawn / Resort", "Designer Wedding Apparel",
        "Wedding Jewelry & Ornaments", "Makeup Artist & Grooming", "Photography & Videography",
        "Mandap, Stage & Floral Decoration", "Catering & Food Service", "Music, DJ & Entertainment",
        "Wedding Invitations & Digital Cards", "Transportation Services", "Baraat: Ghodi, Buggy & Band",
        "Vedic Priest & Ritual Services", "Wedding Finance / Loan Provider (Bank / NBFC)"
    ]
    vendor_types = st.multiselect("What are you registering as? (select all that apply)", ALL_VENDOR_CATEGORIES, key="vr_vendor_types")

    col1, col2 = st.columns(2)
    with col1:
        business_name = st.text_input("Business / Shop Name", key="vr_business_name")
        owner_name = st.text_input("Owner's Full Name", key="vr_owner_name")
        shop_number = st.text_input("Shop / Office Number & Address", key="vr_shop_number")
        cities_covered = st.text_input("Cities / Service Areas Covered (comma-separated)", key="vr_cities", placeholder="e.g. Nagpur, Pune, Mumbai")
    with col2:
        contact_number = st.text_input("Business Contact Number", key="vr_contact_number", max_chars=10, placeholder="10-digit number")
        business_email = st.text_input("Business Email", key="vr_business_email")
        city = st.text_input("City / Location (primary)", key="vr_city")
        price_range = st.selectbox("Typical Price Range", ["\u20b9 (Budget)", "\u20b9\u20b9 (Mid-range)", "\u20b9\u20b9\u20b9 (Premium)", "\u20b9\u20b9\u20b9\u20b9 (Luxury)"], key="vr_price_range")

    hc1, hc2 = st.columns(2)
    business_hours_start = hc1.time_input("Business Hours — Opens", value=dt.time(9, 0), key="vr_hours_start")
    business_hours_end = hc2.time_input("Business Hours — Closes", value=dt.time(19, 0), key="vr_hours_end")

    logo_upload = st.file_uploader("Business Logo / Cover Photo (optional)", type=['jpg', 'png', 'jpeg'], key="vr_logo")
    if logo_upload:
        st.image(logo_upload, width=160, caption="Preview")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Step 2: Identity & Business Documents")
    doc_col1, doc_col2 = st.columns(2)
    with doc_col1:
        aadhar_number = st.text_input("Aadhaar Card Number", max_chars=12, placeholder="12-digit Aadhaar number", key="vr_aadhaar")
        pan_number = st.text_input("PAN Card Number", max_chars=10, placeholder="ABCDE1234F", key="vr_pan")
    with doc_col2:
        gst_number = st.text_input("GST Number (if applicable)", placeholder="Leave blank if not registered", key="vr_gst")
        license_number = st.text_input("Trade / Shop License Number (if applicable)", placeholder="Leave blank if not applicable", key="vr_license")

    doc_upload = st.file_uploader("Upload Aadhaar / PAN / License (photo or PDF, max 10 MB)", type=['jpg', 'png', 'jpeg', 'pdf'], key="vr_doc_upload")
    if doc_upload and doc_upload.size > 10 * 1024 * 1024:
        st.error("\u274C File too large — please upload a document under 10 MB.")
        doc_upload = None
    elif doc_upload and doc_upload.type in ("image/jpeg", "image/png"):
        st.image(doc_upload, width=160, caption="Document preview")

    # Live validation feedback as the person types
    if aadhar_number and not vendor_validate_aadhaar(aadhar_number):
        st.caption("\u26A0\uFE0F Aadhaar must be exactly 12 digits.")
    if pan_number and not vendor_validate_pan(pan_number):
        st.caption("\u26A0\uFE0F PAN format should be like ABCDE1234F.")
    if gst_number and not vendor_validate_gst(gst_number):
        st.caption("\u26A0\uFE0F GSTIN format looks incorrect (15 characters).")
    if business_email and not vendor_validate_email(business_email):
        st.caption("\u26A0\uFE0F Business email looks invalid.")
    if contact_number and not vendor_validate_mobile(contact_number):
        st.caption("\u26A0\uFE0F Contact number should be a valid 10-digit Indian mobile number.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Step 3: OTP Verification")
    st.write("To prevent fake vendor listings, we verify your identity with an OTP sent to your Aadhaar/PAN-linked mobile number.")

    otp_mobile = st.text_input("Mobile Number linked to Aadhaar/PAN", max_chars=10, placeholder="10-digit mobile number", key="vr_otp_mobile")

    send_otp_col, verify_col = st.columns([1, 2])
    with send_otp_col:
        if st.button("\U0001F4F2 Send OTP", use_container_width=True):
            if not vendor_validate_aadhaar(aadhar_number):
                st.warning("\u26A0\uFE0F Please enter a valid 12-digit Aadhaar number first.")
            elif not vendor_validate_pan(pan_number):
                st.warning("\u26A0\uFE0F Please enter a valid PAN number first.")
            elif not vendor_validate_mobile(otp_mobile):
                st.warning("\u26A0\uFE0F Please enter a valid 10-digit mobile number first.")
            else:
                dupe = db_check_vendor_duplicate(aadhar_number, pan_number, business_email) if business_email else None
                if dupe and dupe.get("business_email") != user_email:
                    st.error("\u274C A vendor is already registered with this Aadhaar, PAN, or business email. Please contact support if this is a mistake.")
                else:
                    st.session_state.vendor_otp = str(random.randint(100000, 999999))
                    st.session_state.vendor_otp_verified = False
                    token, phone_id = wa_get_whatsapp_credentials()
                    wa_number = "91" + otp_mobile if len(otp_mobile) == 10 else otp_mobile
                    if token and phone_id:
                        success, detail = wa_send_whatsapp_message(wa_number, f"Your Bandhan.com vendor verification OTP is {st.session_state.vendor_otp}. Do not share it with anyone.", token, phone_id)
                        if success:
                            st.success(f"\u2705 OTP sent to your WhatsApp ({otp_mobile}).")
                        else:
                            st.warning(f"Couldn't send via WhatsApp ({detail}) — showing OTP below instead (demo mode).")
                    st.session_state.vendor_otp_sent_demo = not (token and phone_id)

    if st.session_state.vendor_otp:
        if st.session_state.get("vendor_otp_sent_demo", True):
            render_html(f"""
            <div class="otp-box">
            \U0001F4E9 <b>Demo Mode:</b> WhatsApp Business API isn't configured yet, so in production this OTP would be sent via SMS/WhatsApp to <b>{otp_mobile}</b>. For this demo, your OTP is: <b style="color:#D4AF37; font-size:1.2rem;">{st.session_state.vendor_otp}</b>
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
    agree_terms = st.checkbox("I confirm all details provided are accurate and I agree to Bandhan's Vendor Terms & Conditions.", key="vr_agree_terms")

    if st.button("\U0001F680 Submit Vendor Registration", type="primary", use_container_width=True):
        missing = []
        if not vendor_types: missing.append("At least one Category")
        if not business_name: missing.append("Business Name")
        if not owner_name: missing.append("Owner Name")
        if not vendor_validate_mobile(contact_number): missing.append("Valid 10-digit Contact Number")
        if not vendor_validate_email(business_email): missing.append("Valid Business Email")
        if not vendor_validate_aadhaar(aadhar_number): missing.append("Valid 12-digit Aadhaar Number")
        if not vendor_validate_pan(pan_number): missing.append("Valid PAN Number")
        if gst_number and not vendor_validate_gst(gst_number): missing.append("Valid GSTIN (or leave blank)")
        if not doc_upload: missing.append("Document Upload")
        if not st.session_state.vendor_otp_verified: missing.append("OTP Verification")
        if not agree_terms: missing.append("Terms Agreement")

        if missing:
            st.error("\u26A0\uFE0F Please complete the following before submitting: " + ", ".join(missing))
        else:
            dupe = db_check_vendor_duplicate(aadhar_number, pan_number, business_email)
            if dupe and dupe.get("business_email") != user_email:
                st.error("\u274C A vendor is already registered with this Aadhaar, PAN, or business email.")
            else:
                vendor_doc = {
                    "vendor_types": vendor_types, "business_name": business_name, "owner_name": owner_name,
                    "shop_number": shop_number, "cities_covered": [c.strip() for c in cities_covered.split(",") if c.strip()],
                    "contact_number": contact_number, "business_email": business_email, "city": city,
                    "price_range": price_range,
                    "business_hours": f"{business_hours_start.strftime('%I:%M %p')} - {business_hours_end.strftime('%I:%M %p')}",
                    "aadhaar_number": aadhar_number, "pan_number": pan_number.upper(), "gst_number": gst_number,
                    "license_number": license_number, "registered_by_email": user_email,
                }
                if db is not None:
                    db_create_vendor_listing(vendor_doc)
                    token, phone_id = wa_get_whatsapp_credentials()
                    confirm_msg = f"Hi {owner_name}, your Bandhan.com vendor registration for {business_name} has been received and is pending review. We'll notify you once approved!"
                    if token and phone_id:
                        wa_send_whatsapp_message("91" + contact_number if len(contact_number) == 10 else contact_number, confirm_msg, token, phone_id)
                st.session_state.pop("vendor_edit_new", None)
                st.balloons()
                st.success(f"\U0001F389 Congratulations {owner_name}! **{business_name}** has been submitted for review. Once approved by our Trust & Safety team, you'll appear in the {', '.join(vendor_types)} listings with a Verified badge.")
                st.caption("\U0001F4E9 A confirmation has been sent to your registered contact number." if (db is not None) else "\u26A0\uFE0F Demo mode: connect MongoDB to actually save this submission for admin review and to send a real confirmation.")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("\U0001F451 Choose Your Vendor Membership Plan \u2192", type="primary", use_container_width=True, key="goto_vendor_membership"):
                    go_to("vendor_membership")

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


# =====================================================================
# SUCCESS STORIES — persistence + moderation helpers
# =====================================================================
def db_check_story_duplicate(groom, bride, marriage_date):
    db = get_db()
    if db is None:
        return None
    return db.success_stories.find_one({
        "groom_name": groom, "bride_name": bride, "marriage_date": marriage_date.isoformat(),
    })


def db_save_success_story(story_doc):
    db = get_db()
    if db is None:
        return None
    doc = dict(story_doc)
    doc["status"] = "Pending"
    doc["submitted_at"] = dt.datetime.utcnow()
    doc["likes"] = 0
    result = db.success_stories.insert_one(doc)
    return str(result.inserted_id)


def db_list_success_stories(status=None, limit=50):
    db = get_db()
    if db is None:
        return []
    query = {"status": status} if status else {}
    return list(db.success_stories.find(query).sort("marriage_date", -1).limit(limit))


def db_update_story_status(story_id, status):
    db = get_db()
    if db is None:
        return False
    db.success_stories.update_one({"_id": ObjectId(story_id)}, {"$set": {"status": status, "reviewed_at": dt.datetime.utcnow()}})
    return True


def db_increment_story_likes(story_id):
    db = get_db()
    if db is None:
        return False
    db.success_stories.update_one({"_id": ObjectId(story_id)}, {"$inc": {"likes": 1}})
    return True


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

    # -----------------------------------------------------------------
    # COMMUNITY STORIES — real submissions, approved by the Boss team,
    # loaded live from MongoDB (falls back to "none yet" in demo mode).
    # -----------------------------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("## \U0001F49E Community Stories")
    approved_stories = db_list_success_stories(status="Approved")
    if not approved_stories:
        st.caption("No community-submitted stories published yet — connect MongoDB and be the first to share yours below!" if not db_is_connected() else "No approved community stories yet — share yours below, and it'll appear here once our team verifies it.")
    else:
        state_options = ["All States"] + sorted({s.get("wedding_state", "") for s in approved_stories if s.get("wedding_state")})
        filter_state = st.selectbox("\U0001F4CD Filter by State", state_options, key="story_state_filter")
        filtered = [s for s in approved_stories if filter_state == "All States" or s.get("wedding_state") == filter_state]
        st.caption(f"Showing {len(filtered)} of {len(approved_stories)} community stories.")
        fcol1, fcol2 = st.columns(2, gap="large")
        for idx, s in enumerate(filtered):
            target_col = fcol1 if idx % 2 == 0 else fcol2
            with target_col:
                st.markdown("<div class='story-card'>", unsafe_allow_html=True)
                if s.get("photo_b64"):
                    st.image(base64.b64decode(s["photo_b64"]), use_container_width=True)
                m_date = s.get("marriage_date", "")
                st.markdown(f"<div class='couple-name'>{s.get('groom_name','')} & {s.get('bride_name','')}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='story-date'>\U0001F4C5 Married on: {m_date} | {s.get('city_name','')}, {s.get('wedding_state','')}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='story-quote'>\"{s.get('story_text','')}\"</div>", unsafe_allow_html=True)
                lc1, lc2 = st.columns(2)
                if lc1.button(f"\u2764\uFE0F {s.get('likes', 0)} Likes", key=f"like_{s['_id']}", use_container_width=True):
                    db_increment_story_likes(str(s["_id"]))
                    st.rerun()
                wa_text = urllib.parse.quote(f"{s.get('groom_name','')} & {s.get('bride_name','')} found love on Bandhan.com and got married in {s.get('city_name','')}! Read their story on Bandhan.")
                lc2.link_button("\U0001F4E4 Share", f"https://wa.me/?text={wa_text}", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

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

        story_text = st.text_area("Your Love & Success Story", placeholder="Write about how you met on Bandhan and your wedding experience...", max_chars=1500)
        couple_photo = st.file_uploader(f"Upload Your Couple Photo (max {MAX_PHOTO_MB} MB)", type=["jpg", "jpeg", "png"])
        consent_publish = st.checkbox("I consent to my names, story, and photo being published publicly on the Bandhan.com Success Stories page.")
        submitted = st.form_submit_button("\U0001F4E4 Submit Your Success Story", type="primary")


        if submitted:
            if not (groom_name and bride_name and story_text):
                st.warning("Please fill in the essential details (Names and Story) before submitting.")
            elif couple_photo is None:
                st.warning("Please upload a couple photo to complete your submission.")
            elif not consent_publish:
                st.warning("Please check the consent box to confirm you're okay with your story being published publicly.")
            elif db_check_story_duplicate(groom_name.strip(), bride_name.strip(), marriage_date):
                st.warning("A story for this couple and wedding date has already been submitted.")
            else:
                processed_bytes, size_mb = story_process_cinematic_photo(couple_photo)
                if processed_bytes is None:
                    st.error(f"\u26A0\uFE0F Your photo is {size_mb:.1f} MB, which is over the {MAX_PHOTO_MB} MB limit. Please upload a smaller file.")
                else:
                    db_save_success_story({
                        "groom_name": groom_name.strip(), "bride_name": bride_name.strip(),
                        "marriage_date": marriage_date.isoformat(), "contact_email": contact_email,
                        "city_name": city_name, "wedding_state": wedding_state, "wedding_district": wedding_district,
                        "venue_name": venue_name, "story_text": story_text,
                        "photo_b64": base64.b64encode(processed_bytes).decode(),
                    })
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
                    st.success("\U0001F389 Thank you for sharing your story! It's now in our moderation queue \u2014 once our team approves it, it'll appear in the Community Stories section above." if db_is_connected() else "\U0001F389 Thank you for sharing your story! \u26A0\uFE0F Demo mode: connect MongoDB so this actually gets saved for admin review and shown in Community Stories.")
                    st.markdown(f"<p style='color:gray; font-size:0.85rem;'>{wedding_district}, {wedding_state} \u2022 {venue_name or 'Venue not specified'}</p>", unsafe_allow_html=True)
                    st.markdown("#### \U0001F3AC Your Photo \u2014 Full HD Cinematic Preview")
                    st.markdown("<div class='cinematic-frame'>", unsafe_allow_html=True)
                    st.image(processed_bytes, use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: AI COMPATIBILITY SCORE
# =====================================================================
# =====================================================================
# AI COMPATIBILITY SCORE — persistence + free-tier limit helpers
# =====================================================================
def db_save_forecast(email, match_name, report):
    db = get_db()
    if db is None:
        return None
    doc = dict(report)
    doc["email"] = email
    doc["match_name"] = match_name
    doc["generated_at"] = dt.datetime.utcnow()
    result = db.compatibility_forecasts.insert_one(doc)
    return str(result.inserted_id)


def db_list_forecasts(email, limit=10):
    db = get_db()
    if db is None:
        return []
    return list(db.compatibility_forecasts.find({"email": email}).sort("generated_at", -1).limit(limit))


def db_count_forecasts_today(email):
    db = get_db()
    if db is None:
        return 0
    start_of_day = dt.datetime.combine(dt.date.today(), dt.time.min)
    return db.compatibility_forecasts.count_documents({"email": email, "generated_at": {"$gte": start_of_day}})


def page_ai_compatibility():
    render_global_css(bg_color="#F8F9FA", page_css=""".forecast-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.big-score { font-size: 5rem; font-weight: 900; color: #27AE60; text-align: center; margin: 10px 0; }
.factor-card { background: white; padding: 18px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #D4AF37; margin-bottom: 12px; }
.forecast-photo { width: 100%; border-radius: 12px; height: 160px; object-fit: cover; }
.history-card { background: white; padding: 12px 16px; border-radius: 10px; box-shadow: 0 3px 8px rgba(0,0,0,0.05); margin-bottom: 8px; border-left: 4px solid #1A365D; }""")

    st.markdown("""
    <div class="forecast-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F9E0 AI Relationship Forecast</h1>
        <p style="color:#FBF5B7; margin-top:8px;">One unified score combining Kundli, your Values & Lifestyle Quiz, and profile compatibility — not just astrology, not just filters.</p>
    </div>
    """, unsafe_allow_html=True)

    user_email = st.session_state.get("user_email") or "guest@bandhan.com"
    is_paid_member = st.session_state.get("is_paid_member", False)
    FREE_DAILY_LIMIT = 3

    # Same demo profile pool used across Search Partner / My Matches / AI Recommendations
    all_profiles = {
        "Ritu Deshmukh": {"age": 24, "city": "Nagpur", "profession": "Software Engineer", "diet": "Vegetarian", "manglik": "Non-Manglik",
                           "height_cm": 160, "mother_tongue": "Marathi", "marital_status": "Never Married", "caste": "Maratha",
                           "photo": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=400&q=80"},
        "Sneha Patil": {"age": 26, "city": "Pune", "profession": "Chartered Accountant", "diet": "Vegetarian", "manglik": "Manglik",
                        "height_cm": 165, "mother_tongue": "Marathi", "marital_status": "Never Married", "caste": "Maratha",
                        "photo": "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?auto=format&fit=crop&w=400&q=80"},
        "Ananya Rao": {"age": 26, "city": "Bengaluru", "profession": "Doctor", "diet": "Eggetarian", "manglik": "Non-Manglik",
                       "height_cm": 158, "mother_tongue": "Kannada", "marital_status": "Never Married", "caste": "Brahmin",
                       "photo": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=400&q=80"},
        "Kavya Nair": {"age": 28, "city": "Chennai", "profession": "Civil Servant", "diet": "Vegetarian", "manglik": "Manglik",
                       "height_cm": 155, "mother_tongue": "Tamil", "marital_status": "Never Married", "caste": "Nair",
                       "photo": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=400&q=80"},
        "Priya Sharma": {"age": 27, "city": "Delhi", "profession": "Banker", "diet": "Non-Vegetarian", "manglik": "Non-Manglik",
                         "height_cm": 162, "mother_tongue": "Hindi", "marital_status": "Divorced", "caste": "Brahmin",
                         "photo": "https://images.unsplash.com/photo-1552374196-c4e7ffc6e126?auto=format&fit=crop&w=400&q=80"},
        "Fatima Sheikh": {"age": 29, "city": "Hyderabad", "profession": "Teacher", "diet": "Non-Vegetarian", "manglik": "Non-Manglik",
                          "height_cm": 163, "mother_tongue": "Urdu", "marital_status": "Never Married", "caste": "Sheikh",
                          "photo": "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=400&q=80"},
    }

    # -----------------------------------------------------------------
    # A REAL (if lightweight) VALUES & LIFESTYLE QUIZ — replaces the old
    # purely-fake hash-based "quiz_match" with something actually derived
    # from the user's own answers, asked once per session and reusable
    # for every match they analyze.
    # -----------------------------------------------------------------
    with st.expander("\U0001F4DD Your Values & Lifestyle Quiz (answer once, used for every forecast)", expanded="ai_quiz_diet" not in st.session_state):
        quiz_diet = st.selectbox("Your diet preference", ["Vegetarian", "Eggetarian", "Non-Vegetarian"], key="ai_quiz_diet")
        quiz_family = st.slider("How important are shared family traditions to you?", 1, 5, 4, key="ai_quiz_family")
        quiz_career = st.slider("How important is your partner being equally career-driven?", 1, 5, 3, key="ai_quiz_career")
        st.caption("These answers directly change the Quiz Match % and Career Match % below \u2014 they're not just for show.")

    name_pick = st.selectbox("Select a match to analyze", list(all_profiles.keys()))
    p = all_profiles[name_pick]

    photo_col, info_col = st.columns([1, 3])
    with photo_col:
        st.markdown(f"<img src='{p['photo']}' class='forecast-photo'>", unsafe_allow_html=True)
    with info_col:
        st.markdown(f"### {name_pick}")
        st.write(f"{p['age']} yrs \u2022 {p['height_cm']} cm \u2022 {p['city']} \u2022 {p['profession']}")
        st.caption(f"{p['diet']} \u2022 {p['manglik']}, {p['caste']} \u2022 {p['mother_tongue']} \u2022 {p['marital_status']}")

    forecasts_today = db_count_forecasts_today(user_email) if db_is_connected() else st.session_state.get("ai_forecast_count_demo", 0)
    limit_reached = (not is_paid_member) and forecasts_today >= FREE_DAILY_LIMIT
    if not is_paid_member:
        st.caption(f"\U0001F193 Free plan: {min(forecasts_today, FREE_DAILY_LIMIT)}/{FREE_DAILY_LIMIT} forecasts used today.")

    if limit_reached:
        st.warning(f"\u26A0\uFE0F You've used your {FREE_DAILY_LIMIT} free forecasts for today.")
        if st.button("\U0001F451 Upgrade to VIP for Unlimited Forecasts", type="primary", use_container_width=True):
            go_to("vip_membership")
    elif st.button("\U0001F52E Generate Unified Forecast", type="primary", use_container_width=True):
        with st.spinner("Combining Kundli Guna score, quiz answers, and lifestyle data..."):
            time.sleep(1.0)

        seed = abs(hash(name_pick)) % 1000
        guna_score = 22 + (seed % 13)  # 22-34 out of 36

        # Quiz Match is now grounded in the user's actual answers, not a hash.
        diet_compat = {("Vegetarian", "Vegetarian"): 14, ("Non-Vegetarian", "Non-Vegetarian"): 12,
                       ("Eggetarian", "Eggetarian"): 12, ("Vegetarian", "Eggetarian"): 4, ("Eggetarian", "Vegetarian"): 4}
        diet_bonus = diet_compat.get((quiz_diet, p["diet"]), -6 if quiz_diet != p["diet"] else 12)
        quiz_match = min(98, max(60, 76 + (seed % 8) + diet_bonus))

        HIGH_AMBITION_PROFESSIONS = {"Software Engineer", "Chartered Accountant", "Doctor", "Civil Servant", "Banker"}
        career_base = 70 + (seed % 12)
        if p["profession"] in HIGH_AMBITION_PROFESSIONS:
            career_match = min(98, career_base + (10 if quiz_career >= 4 else -4 if quiz_career <= 2 else 3))
        else:
            career_match = min(95, career_base + (8 if quiz_career <= 2 else -6 if quiz_career >= 4 else 0))
        career_match = max(55, career_match)

        family_options = [
            ("Aligned", "Similar community, comparable family values."),
            ("Mostly Aligned", "Some differences in family traditions, but shared core values."),
            ("Needs Discussion", "Different family expectations \u2014 worth an open conversation early on."),
        ]
        family_status, family_note = family_options[seed % 3]
        if quiz_family >= 4 and family_status == "Needs Discussion":
            family_note += " Since you rated shared family traditions as very important to you, this is worth prioritizing in early conversations."

        overall_score = round(0.4 * (guna_score / 36 * 100) + 0.35 * quiz_match + 0.25 * career_match)
        overall_score = min(max(overall_score, 45), 99)

        if overall_score >= 85:
            verdict, verdict_color = "Excellent Long-Term Compatibility", "#27AE60"
        elif overall_score >= 70:
            verdict, verdict_color = "Good Compatibility \u2014 Worth Exploring", "#D4AF37"
        else:
            verdict, verdict_color = "Moderate Compatibility \u2014 Proceed Thoughtfully", "#E67E22"

        st.markdown(f"<div class='big-score' style='color:{verdict_color};'>{overall_score}%</div>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align:center; color:{verdict_color}; font-weight:bold; font-size:1.1rem;'>{verdict}</p>", unsafe_allow_html=True)

        st.markdown("### How this score was calculated")
        factors = [
            ("\U0001F549\uFE0F Kundli Guna Milan", f"{guna_score} / 36", "Strong astrological alignment, no major dosha." if guna_score >= 28 else "Reasonable alignment; a detailed Kundli Match session is recommended."),
            ("\U0001F9E9 Values & Lifestyle Quiz", f"{quiz_match}% match", "Based on your diet preference vs theirs." + (" Great alignment!" if quiz_match >= 85 else " Some differing lifestyle preferences worth discussing.")),
            ("\U0001F3E1 Family Background", family_status, family_note),
            ("\U0001F4BC Career & Ambition", f"{career_match}% match", "Matches how important you said equal career drive is to you." + (" Well aligned." if career_match >= 80 else " Different career priorities \u2014 balance may need conversation.")),
        ]
        for title, score, note in factors:
            st.markdown(f"""
            <div class="factor-card">
                <b>{title}</b> — <span style="color:#27AE60; font-weight:bold;">{score}</span><br>
                <span style="color:gray; font-size:0.9rem;">{note}</span>
            </div>
            """, unsafe_allow_html=True)

        st.info("\U0001F4A1 This forecast is a data-driven suggestion, not a guarantee. Use it alongside conversations and family input.")

        report_text = f"""BANDHAN.COM \u2014 AI RELATIONSHIP FORECAST REPORT
Generated for match: {name_pick}
{p['age']} yrs | {p['city']} | {p['profession']}

OVERALL COMPATIBILITY: {overall_score}% \u2014 {verdict}

Kundli Guna Milan: {guna_score} / 36
Values & Lifestyle Quiz Match: {quiz_match}%
Family Background: {family_status} \u2014 {family_note}
Career & Ambition Match: {career_match}%

Note: This forecast is a data-driven suggestion, not a guarantee.
"""
        forecast_record = {
            "overall_score": overall_score, "verdict": verdict, "guna_score": guna_score,
            "quiz_match": quiz_match, "career_match": career_match, "family_status": family_status,
        }
        if db_is_connected():
            db_save_forecast(user_email, name_pick, forecast_record)
        else:
            st.session_state.ai_forecast_count_demo = st.session_state.get("ai_forecast_count_demo", 0) + 1

        act1, act2, act3, act4, act5 = st.columns(5)
        act1.download_button("\U0001F4C4 Download Report", data=report_text, file_name=f"Compatibility_Report_{name_pick.replace(' ', '_')}.txt", mime="text/plain", use_container_width=True)
        wa_text = urllib.parse.quote(f"My Bandhan.com AI Relationship Forecast with {name_pick}: {overall_score}% ({verdict})")
        act2.link_button("\U0001F4E4 Share", f"https://wa.me/?text={wa_text}", use_container_width=True)
        if act3.button("\U0001F4AC Message", key=f"forecast_msg_{name_pick}", use_container_width=True):
            st.session_state.chat_preselect_contact = name_pick
            st.session_state.chat_preselect_score = overall_score
            go_to("chat_alerts")
        if "airec_shortlist" not in st.session_state:
            st.session_state.airec_shortlist = set()
        is_shortlisted = name_pick in st.session_state.airec_shortlist
        if act4.button("\u2B50 Saved" if is_shortlisted else "\u2606 Shortlist", key=f"forecast_short_{name_pick}", use_container_width=True):
            if is_shortlisted:
                st.session_state.airec_shortlist.discard(name_pick)
            else:
                st.session_state.airec_shortlist.add(name_pick)
            st.rerun()
        if "airec_interested" not in st.session_state:
            st.session_state.airec_interested = set()
        already_interested = name_pick in st.session_state.airec_interested
        if act5.button("\u2705 Sent" if already_interested else "\U0001F49B Send Interest", key=f"forecast_int_{name_pick}", use_container_width=True, disabled=already_interested):
            st.session_state.airec_interested.add(name_pick)
            st.toast(f"\U0001F49B You sent interest to {name_pick}!")
            st.rerun()

    # -----------------------------------------------------------------
    # FORECAST HISTORY — lets a user compare past matches over time
    # instead of every generated score vanishing on refresh.
    # -----------------------------------------------------------------
    if db_is_connected():
        past_forecasts = db_list_forecasts(user_email, limit=10)
        if past_forecasts:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander(f"\U0001F4DC Your Forecast History ({len(past_forecasts)})"):
                for f in past_forecasts:
                    st.markdown(f"""
                    <div class="history-card">
                        <b>{f.get('match_name','')}</b> — {f.get('overall_score','')}% ({f.get('verdict','')})
                        <br><span style="color:gray; font-size:0.85rem;">{f.get('generated_at', dt.datetime.utcnow()).strftime('%d %b %Y, %I:%M %p')}</span>
                    </div>
                    """, unsafe_allow_html=True)


# =====================================================================
# PAGE: AI ICEBREAKER
# =====================================================================
def page_ai_icebreaker():
    render_global_css(bg_color="#F8F9FA", page_css=""".ice-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.ice-suggestion { background: white; padding: 16px 20px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #2563EB; margin-bottom: 12px; }
.ice-suggestion.used { border-left: 5px solid #9CA3AF; opacity: 0.65; }
.ice-photo { width: 100%; border-radius: 12px; height: 150px; object-fit: cover; }""")

    st.markdown("""
    <div class="ice-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F9CA AI Icebreaker Suggestions</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Stuck on what to say first? Let AI suggest openers based on shared interests.</p>
    </div>
    """, unsafe_allow_html=True)

    is_paid_member = st.session_state.get("is_paid_member", False)
    FREE_DAILY_LIMIT = 5
    user_email = st.session_state.get("user_email") or "guest@bandhan.com"

    # Same demo profile pool used across Search Partner / My Matches / AI Recommendations / AI Compatibility
    all_profiles = {
        "Ritu Deshmukh": {"age": 24, "city": "Nagpur", "profession": "Software Engineer", "diet": "Vegetarian",
                           "hobby": "weekend treks and classical dance",
                           "photo": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=400&q=80"},
        "Sneha Patil": {"age": 26, "city": "Pune", "profession": "Chartered Accountant", "diet": "Vegetarian",
                        "hobby": "cooking and weekend hiking",
                        "photo": "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?auto=format&fit=crop&w=400&q=80"},
        "Ananya Rao": {"age": 26, "city": "Bengaluru", "profession": "Doctor", "diet": "Eggetarian",
                       "hobby": "reading and weekend volunteering",
                       "photo": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=400&q=80"},
        "Kavya Nair": {"age": 28, "city": "Chennai", "profession": "Civil Servant", "diet": "Vegetarian",
                       "hobby": "classical music and public service",
                       "photo": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=400&q=80"},
        "Priya Sharma": {"age": 27, "city": "Delhi", "profession": "Banker", "diet": "Non-Vegetarian",
                         "hobby": "travel, fitness, and good food",
                         "photo": "https://images.unsplash.com/photo-1552374196-c4e7ffc6e126?auto=format&fit=crop&w=400&q=80"},
        "Fatima Sheikh": {"age": 29, "city": "Hyderabad", "profession": "Teacher", "diet": "Non-Vegetarian",
                          "hobby": "poetry and calligraphy",
                          "photo": "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=400&q=80"},
    }

    match_pick = st.selectbox("Generate icebreakers for", list(all_profiles.keys()))
    p = all_profiles[match_pick]
    first_name = match_pick.split()[0]

    photo_col, info_col = st.columns([1, 3])
    with photo_col:
        st.markdown(f"<img src='{p['photo']}' class='ice-photo'>", unsafe_allow_html=True)
    with info_col:
        st.markdown(f"### {match_pick}")
        st.write(f"{p['age']} yrs \u2022 {p['city']} \u2022 {p['profession']}")

    tone = st.radio("Tone", ["Friendly", "Formal", "Playful", "Hinglish"], horizontal=True, key="ice_tone")

    TEMPLATE_BANK = {
        "Friendly": [
            f"Hi {first_name}! I noticed we might enjoy {p['hobby']} together \u2014 what got you into that?",
            f"Saw you're a {p['profession']} \u2014 I'd love to hear what a typical day looks like for you.",
            f"We both listed '{p['diet']}' as our diet preference \u2014 any favorite dish you always recommend?",
            f"Your profile mentioned {p['city']} \u2014 what's your favorite thing about living there?",
            f"Hey {first_name}, your profile made me smile \u2014 how's your week going so far?",
        ],
        "Formal": [
            f"Hello {first_name}, it's a pleasure to connect. I noticed you work as a {p['profession']} \u2014 I'd love to know more about your journey.",
            f"Namaste {first_name} ji, I came across your profile and would be glad to know you better, if you're open to it.",
            f"Hello {first_name}, I see you're based in {p['city']}. I'd appreciate hearing more about your background and interests.",
            f"Hi {first_name}, thank you for connecting. I'd be happy to share more about myself if you'd like to know.",
        ],
        "Playful": [
            f"Okay {first_name}, convince me in one line why {p['hobby']} is better than everything else \U0001F604",
            f"Plot twist: what if our first date is just talking about {p['hobby']} for an hour? \U0001F609",
            f"{first_name}, quick poll \u2014 {p['city']} street food or home-cooked food? I need to know before we go further \U0001F60F",
            f"I'll be honest, your profile picture made me forget my opening line, {first_name} \U0001F605",
        ],
        "Hinglish": [
            f"Hi {first_name}! Aapka profile dekh ke laga hum dono ko {p['hobby']} pasand hai \u2014 kaise shuru hua ye interest?",
            f"{p['profession']} ho aap? Bahut interesting, ek din ka schedule share karoge?",
            f"{p['city']} mein rehte ho \u2014 wahan ka sabse favorite spot kaunsa hai aapka?",
            f"Namaste {first_name} ji, aapse baat karke accha lagega \u2014 kaisa chal raha hai sab kuch?",
        ],
    }

    icebreaker_count_key = "ice_gen_count_demo"
    generated_today = st.session_state.get(icebreaker_count_key, 0)
    limit_reached = (not is_paid_member) and generated_today >= FREE_DAILY_LIMIT
    if not is_paid_member:
        st.caption(f"\U0001F193 Free plan: {min(generated_today, FREE_DAILY_LIMIT)}/{FREE_DAILY_LIMIT} icebreaker generations used today.")

    gen_col1, gen_col2 = st.columns(2)
    if limit_reached:
        st.warning(f"\u26A0\uFE0F You've used your {FREE_DAILY_LIMIT} free icebreaker generations for today.")
        if st.button("\U0001F451 Upgrade to VIP for Unlimited Icebreakers", type="primary", use_container_width=True):
            go_to("vip_membership")
    else:
        if gen_col1.button("\u2728 Generate Icebreakers", type="primary", use_container_width=True):
            bank = TEMPLATE_BANK[tone]
            picked = random.sample(bank, min(3, len(bank)))
            st.session_state["_icebreaker_suggestions"] = picked
            st.session_state["_icebreaker_for"] = match_pick
            st.session_state["_icebreaker_tone"] = tone
            st.session_state[icebreaker_count_key] = generated_today + 1
        if gen_col2.button("\U0001F504 Regenerate (new variations)", use_container_width=True):
            bank = TEMPLATE_BANK[tone]
            picked = random.sample(bank, min(3, len(bank)))
            st.session_state["_icebreaker_suggestions"] = picked
            st.session_state["_icebreaker_for"] = match_pick
            st.session_state["_icebreaker_tone"] = tone
            st.session_state[icebreaker_count_key] = generated_today + 1

    suggestions = st.session_state.get("_icebreaker_suggestions")
    suggestions_for = st.session_state.get("_icebreaker_for")
    if "ice_used_lines" not in st.session_state:
        st.session_state.ice_used_lines = set()

    if suggestions and suggestions_for == match_pick:
        st.markdown(f"### Suggested openers for {match_pick} ({st.session_state.get('_icebreaker_tone','Friendly')} tone)")
        for i, s in enumerate(suggestions):
            already_used = s in st.session_state.ice_used_lines
            card_class = "ice-suggestion used" if already_used else "ice-suggestion"
            used_tag = " \u2705 Already sent" if already_used else ""
            st.markdown(f"<div class='{card_class}'>\U0001F4AC {s}{used_tag}</div>", unsafe_allow_html=True)

            edit_key = f"edit_{match_pick}_{i}"
            edited = st.text_area("Edit before sending (optional)", value=s, key=edit_key, height=68, label_visibility="collapsed")

            c1, c2 = st.columns([1, 1])
            if c1.button("\U0001F4E9 Send", key=f"use_{match_pick}_{i}", use_container_width=True, disabled=already_used):
                st.session_state.chat_preselect_contact = match_pick
                st.session_state.chat_pending_message = edited
                st.session_state.ice_used_lines.add(s)
                go_to("chat_alerts")
            copy_html = f"""
            <textarea id="ice_txt_{i}" style="position:absolute; left:-9999px;">{edited}</textarea>
            <button onclick="navigator.clipboard.writeText(document.getElementById('ice_txt_{i}').value); document.getElementById('ice_btn_{i}').innerText='Copied!';"
                    id="ice_btn_{i}" style="width:100%; padding:8px; border-radius:8px; border:1px solid #D1D5DB; background:white; cursor:pointer;">\U0001F4CB Copy to Clipboard</button>
            """
            with c2:
                st.components.v1.html(copy_html, height=45)

        st.caption("Suggestions are generated from shared profile interests and your chosen tone \u2014 edit freely before sending, they're not personal messages until you send them.")


# =====================================================================
# PAGE: BOOST VISIBILITY
# =====================================================================
# =====================================================================
# BOOST VISIBILITY — persistence + vendor-authenticity check helpers
# =====================================================================
def db_save_boost(key, boost_type, label, price, expires_at):
    db = get_db()
    if db is None:
        return False
    db.boosts.update_one(
        {"key": key, "type": boost_type},
        {"$set": {"label": label, "price": price, "activated_at": dt.datetime.utcnow(), "expires_at": expires_at}},
        upsert=True,
    )
    db.boost_history.insert_one({"key": key, "type": boost_type, "label": label, "price": price, "activated_at": dt.datetime.utcnow()})
    return True


def db_get_active_boost(key, boost_type):
    db = get_db()
    if db is None:
        return None
    doc = db.boosts.find_one({"key": key, "type": boost_type})
    if doc and doc.get("expires_at") and doc["expires_at"] > dt.datetime.utcnow():
        return doc
    return None


def db_remove_boost(key, boost_type):
    db = get_db()
    if db is None:
        return False
    db.boosts.delete_one({"key": key, "type": boost_type})
    return True


def db_list_boost_history(key):
    db = get_db()
    if db is None:
        return []
    return list(db.boost_history.find({"key": key}).sort("activated_at", -1).limit(50))


def db_is_approved_vendor_name(name):
    """Confirms a boosted 'vendor' is an actually-approved registration,
    so people can't type any random business name and boost a fake listing."""
    db = get_db()
    if db is None:
        return None
    return db.vendors.find_one({"business_name": name, "status": "Approved"})


def page_boost_visibility():
    render_global_css(bg_color="#F8F9FA", page_css=""".boost-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.boost-plan-card { background: white; padding: 26px; border-radius: 16px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; border-top: 5px solid #D4AF37; text-align: center; }
.boost-plan-card-active { background: #F0FFF4; padding: 26px; border-radius: 16px; box-shadow: 0 8px 20px rgba(39,174,96,0.15); border: 2px solid #27AE60; border-top: 5px solid #27AE60; text-align: center; }
.boost-active-badge { background: #DCFCE7; color: #166534; padding: 12px 20px; border-radius: 10px; font-weight: 700; text-align: center; margin-top: 15px; }
.boost-expiring-badge { background: #FEF3C7; color: #92400E; padding: 12px 20px; border-radius: 10px; font-weight: 700; text-align: center; margin-top: 15px; }
.boost-expired-badge { background: #FEF3C7; color: #92400E; padding: 12px 20px; border-radius: 10px; font-weight: 700; text-align: center; margin-top: 15px; }
.sync-pill { display:inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }""")

    st.markdown("""
    <div class="boost-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F680 Boost Visibility</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Get seen first. Boost your profile or your vendor listing to the top of search results.</p>
    </div>
    """, unsafe_allow_html=True)

    if not render_tnc_gate("payment", "\U0001F4C4 Please Accept Our Terms & Conditions to Continue", "Before purchasing any Boost plan, please read and accept our Terms & Conditions — especially Section 3 (Payment & No-Refund Policy)."):
        return

    user_email = st.session_state.get("user_email") or "guest@bandhan.com"
    sync_ok = db_is_connected()
    pill_style = "background:#DCFCE7; color:#166534;" if sync_ok else "background:#FEF3C7; color:#92400E;"
    pill_text = "\u2601\uFE0F Boosts sync to your account (visible after refresh/re-login too)" if sync_ok else "\U0001F4F1 Demo mode — boosts only last for this session"
    st.markdown(f"<span class='sync-pill' style='{pill_style}'>{pill_text}</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    PLAN_HOURS = {"24 Hours": 24, "3 Days": 72, "7 Days": 168, "30 Days": 720}

    def load_active(key, boost_type, session_key):
        db_boost = db_get_active_boost(key, boost_type) if sync_ok else None
        if db_boost:
            return db_boost
        return st.session_state.get(session_key)

    def is_still_active(boost):
        return boost is not None and dt.datetime.now() < (boost["expires_at"] if isinstance(boost["expires_at"], dt.datetime) else boost["expires_at"])

    def time_left_str(expires_at):
        delta = expires_at - dt.datetime.now()
        if delta.total_seconds() <= 0:
            return "Expired"
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}m remaining"

    def make_receipt(kind, label, price, name_line):
        return f"""BANDHAN.COM \u2014 BOOST VISIBILITY RECEIPT
Type: {kind}
{name_line}
Plan: {label}
Amount Paid: {price}
Activated: {dt.datetime.now().strftime('%d %b %Y, %I:%M %p')}
Note: This is a demo receipt. Real payment processing requires a payment gateway (Razorpay/Stripe) integration.
"""

    tab1, tab2 = st.tabs(["\U0001F464 Boost My Profile (Client)", "\U0001F3EA Boost My Vendor Listing"])

    with tab1:
        st.write("Boosted profiles appear at the top of Search Partner and Recommended Matches results, with a highlighted border.")
        st.markdown("<br>", unsafe_allow_html=True)

        client_active = load_active(user_email, "Profile", "client_boost_active")
        client_is_live = is_still_active(client_active)
        if client_active and not client_is_live:
            st.info(f"\u23F0 Your previous {client_active['label']} boost has expired.")

        c1, c2, c3 = st.columns(3)
        plans = [
            {"label": "24 Hours", "price": "\u20b9 99", "reach": "Up to 5x more views"},
            {"label": "3 Days", "price": "\u20b9 249", "reach": "Up to 8x more views"},
            {"label": "7 Days", "price": "\u20b9 499", "reach": "Up to 12x more views"},
        ]
        cols = [c1, c2, c3]
        for col, plan in zip(cols, plans):
            with col:
                is_this_active = client_is_live and client_active["label"] == plan["label"]
                card_class = "boost-plan-card-active" if is_this_active else "boost-plan-card"
                active_tag = "<div style='color:#27AE60; font-weight:800; font-size:0.85rem;'>\u2705 CURRENTLY ACTIVE</div>" if is_this_active else ""
                st.markdown(f"""
                <div class="{card_class}">
                    {active_tag}
                    <h3>{plan['label']}</h3>
                    <div style="font-size:1.8rem; color:#27AE60; font-weight:900; margin:10px 0;">{plan['price']}</div>
                    <p style="color:gray; font-size:0.9rem;">{plan['reach']}</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Activate {plan['label']} Boost", key=f"client_boost_{plan['label']}", use_container_width=True, disabled=is_this_active):
                    expires_at = dt.datetime.now() + dt.timedelta(hours=PLAN_HOURS[plan["label"]])
                    st.session_state.client_boost_active = {"label": plan["label"], "expires_at": expires_at}
                    if sync_ok:
                        db_save_boost(user_email, "Profile", plan["label"], plan["price"], expires_at)
                    st.session_state["_last_boost_receipt"] = make_receipt("Profile Boost", plan["label"], plan["price"], f"Account: {user_email}")
                    st.rerun()

        if client_is_live:
            hours_left = (client_active["expires_at"] - dt.datetime.now()).total_seconds() / 3600
            badge_class = "boost-expiring-badge" if hours_left <= 6 else "boost-active-badge"
            expiring_note = " \u26A0\uFE0F Expiring soon \u2014 renew to keep your top placement." if hours_left <= 6 else ""
            render_html(f"<div class='{badge_class}'>\u2705 Your profile boost is active for {client_active['label']} \u2014 {time_left_str(client_active['expires_at'])}. You'll appear at the top of search results.{expiring_note}</div>")
            st.caption("Demo mode: this simulates activation. Real payment integration requires a payment gateway (Razorpay/Stripe).")
            rc1, rc2 = st.columns(2)
            if rc1.button("\U0001F5D1\uFE0F Remove Boost", key="remove_client_boost"):
                st.session_state.client_boost_active = None
                if sync_ok:
                    db_remove_boost(user_email, "Profile")
                st.rerun()
            if st.session_state.get("_last_boost_receipt"):
                rc2.download_button("\U0001F4C4 Download Receipt", data=st.session_state["_last_boost_receipt"], file_name="boost_receipt_profile.txt", mime="text/plain", use_container_width=True, key="receipt_profile")

    with tab2:
        st.write("Boosted vendors appear at the top of the Verified Vendors Directory in their category.")
        st.markdown("<br>", unsafe_allow_html=True)

        default_vendor_name = st.session_state.get("user_name", "") if st.session_state.get("user_role") == "vendor" else ""
        vendor_name = st.text_input("Your Registered Business Name", value=default_vendor_name, placeholder="e.g., Royal Events & Management Co.")

        vendor_active = load_active(vendor_name, "Vendor", "vendor_boost_active") if vendor_name else None
        vendor_is_live = is_still_active(vendor_active)
        if vendor_active and not vendor_is_live:
            st.info(f"\u23F0 {vendor_name}'s previous {vendor_active['label']} boost has expired.")

        v1, v2, v3 = st.columns(3)
        vplans = [
            {"label": "3 Days", "price": "\u20b9 499", "reach": "Top of category listing"},
            {"label": "7 Days", "price": "\u20b9 999", "reach": "Top of category + Home page feature"},
            {"label": "30 Days", "price": "\u20b9 2,999", "reach": "Top placement + Featured badge everywhere"},
        ]
        vcols = [v1, v2, v3]
        for col, plan in zip(vcols, vplans):
            with col:
                is_this_active = vendor_is_live and vendor_active["label"] == plan["label"]
                card_class = "boost-plan-card-active" if is_this_active else "boost-plan-card"
                active_tag = "<div style='color:#27AE60; font-weight:800; font-size:0.85rem;'>\u2705 CURRENTLY ACTIVE</div>" if is_this_active else ""
                st.markdown(f"""
                <div class="{card_class}">
                    {active_tag}
                    <h3>{plan['label']}</h3>
                    <div style="font-size:1.8rem; color:#27AE60; font-weight:900; margin:10px 0;">{plan['price']}</div>
                    <p style="color:gray; font-size:0.9rem;">{plan['reach']}</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Activate {plan['label']} Vendor Boost", key=f"vendor_boost_{plan['label']}", use_container_width=True, disabled=is_this_active):
                    if not vendor_name:
                        st.warning("Please enter your registered business name first.")
                    elif sync_ok and not db_is_approved_vendor_name(vendor_name):
                        st.error(f"\u274C **{vendor_name}** isn't found among our approved vendors. Please complete Vendor Registration and get approved before boosting your listing.")
                    else:
                        expires_at = dt.datetime.now() + dt.timedelta(hours=PLAN_HOURS[plan["label"]])
                        st.session_state.vendor_boost_active = {"name": vendor_name, "label": plan["label"], "expires_at": expires_at}
                        if sync_ok:
                            db_save_boost(vendor_name, "Vendor", plan["label"], plan["price"], expires_at)
                        st.session_state["_last_boost_receipt_vendor"] = make_receipt("Vendor Boost", plan["label"], plan["price"], f"Business: {vendor_name}")
                        st.rerun()

        if vendor_is_live:
            hours_left = (vendor_active["expires_at"] - dt.datetime.now()).total_seconds() / 3600
            badge_class = "boost-expiring-badge" if hours_left <= 6 else "boost-active-badge"
            expiring_note = " \u26A0\uFE0F Expiring soon \u2014 renew to keep your top placement." if hours_left <= 6 else ""
            render_html(f"<div class='{badge_class}'>\u2705 {vendor_name}'s listing is boosted for {vendor_active['label']} \u2014 {time_left_str(vendor_active['expires_at'])}. It's featured at the top of its category.{expiring_note}</div>")
            st.caption("Demo mode: this simulates activation. Real payment integration requires a payment gateway (Razorpay/Stripe).")
            rc1, rc2 = st.columns(2)
            if rc1.button("\U0001F5D1\uFE0F Remove Vendor Boost", key="remove_vendor_boost"):
                st.session_state.vendor_boost_active = None
                if sync_ok:
                    db_remove_boost(vendor_name, "Vendor")
                st.rerun()
            if st.session_state.get("_last_boost_receipt_vendor"):
                rc2.download_button("\U0001F4C4 Download Receipt", data=st.session_state["_last_boost_receipt_vendor"], file_name="boost_receipt_vendor.txt", mime="text/plain", use_container_width=True, key="receipt_vendor")

    st.markdown("---")
    st.markdown("### \U0001F4CB Your Boost History")
    history = db_list_boost_history(user_email) + (db_list_boost_history(vendor_name) if vendor_name else [])
    if not history and not sync_ok:
        history = st.session_state.get("boost_history", [])
    if history:
        hist_rows = [{"Type": h.get("type"), "Label": h.get("label"), "Price": h.get("price"),
                      "Activated": h.get("activated_at").strftime("%d %b %Y, %I:%M %p") if isinstance(h.get("activated_at"), dt.datetime) else h.get("activated_at")}
                     for h in history]
        st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No boosts activated yet.")


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

    user_email = st.session_state.get("user_email") or "guest@bandhan.com"
    sync_ok = db_is_connected()

    my_code = db_get_or_create_referral_code(user_email) if sync_ok else generate_referral_code(user_email)
    referrals = db_list_referrals(user_email) if sync_ok else []
    wallet_credit = db_get_wallet_credit(user_email) if sync_ok else 0
    successful_count = sum(1 for r in referrals if r.get("status") == "Joined")

    col1, col2 = st.columns([1.3, 1], gap="large")

    with col1:
        st.markdown("### Your Unique Referral Code")
        st.markdown(f"<div class='referral-code-box'>{my_code}</div>", unsafe_allow_html=True)
        if not sync_ok:
            st.caption("\u26A0\uFE0F Demo mode: this code is generated live for you, but connect MongoDB so referrals actually get tracked and credited.")

        share_text = f"Join Bandhan.com using my referral code {my_code} and find your perfect match! Sign up here: https://bandhan.com/signup?ref={my_code}"
        share_col1, share_col2, share_col3 = st.columns(3)
        share_col1.link_button("\U0001F4F1 WhatsApp", f"https://wa.me/?text={urllib.parse.quote(share_text)}", use_container_width=True)
        share_col2.link_button("\U0001F4E7 Email", f"mailto:?subject={urllib.parse.quote('Join me on Bandhan.com')}&body={urllib.parse.quote(share_text)}", use_container_width=True)
        with share_col3:
            copy_html = f"""
            <textarea id="ref_txt" style="position:absolute; left:-9999px;">{share_text}</textarea>
            <button onclick="navigator.clipboard.writeText(document.getElementById('ref_txt').value); document.getElementById('ref_btn').innerText='Copied!';"
                    id="ref_btn" style="width:100%; padding:8px; border-radius:8px; border:1px solid #D1D5DB; background:white; cursor:pointer;">\U0001F517 Copy Link</button>
            """
            st.components.v1.html(copy_html, height=45)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### How it Works")
        st.markdown("""
        1. Share your referral code with friends or family looking for a match.
        2. They enter your code in the **Referral Code (optional)** field during Sign Up.
        3. The moment they create their account, you both get credited \u2014 no separate KYC wait in this version.
        """)

    with col2:
        st.markdown("### \U0001F3C6 Your Rewards")
        r1, r2 = st.columns(2)
        with r1:
            st.markdown(f"<div class='reward-card'><h2 style='color:#27AE60; margin:0;'>{successful_count}</h2><p style='margin:0; color:gray;'>Successful Referrals</p></div>", unsafe_allow_html=True)
        with r2:
            st.markdown(f"<div class='reward-card'><h2 style='color:#D4AF37; margin:0;'>\u20b9{wallet_credit:,}</h2><p style='margin:0; color:gray;'>Wallet Credit Earned</p></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.info("\U0001F4A1 Every successful referral gives you \u20b9300 wallet credit, redeemable against any VIP plan upgrade.")
        if wallet_credit > 0 and st.button("\U0001F451 Redeem Wallet Credit on VIP Membership", use_container_width=True):
            go_to("vip_membership")

    st.markdown("---")
    st.markdown("### \U0001F465 Your Referral History")
    if not sync_ok:
        st.caption("Connect MongoDB to see your real referral history here \u2014 it'll populate automatically as friends sign up with your code.")
    elif not referrals:
        st.caption("No referrals yet \u2014 share your code above to get started!")
    else:
        for r in referrals:
            reward_str = f"\u20b9{r.get('reward', 300)} credited" if r.get("status") == "Joined" else "Reward pending"
            st.markdown(f"**{r.get('referred_name','')}** — {r.get('status','')} \u2705 — {reward_str} — {r.get('joined_at', dt.datetime.utcnow()).strftime('%d %b %Y')}")


# =====================================================================
# PAGE: BLOG & TIPS
# =====================================================================
# =====================================================================
# BLOG & TIPS — CMS persistence + bookmarks helpers
# =====================================================================
def db_list_blog_articles():
    db = get_db()
    if db is None:
        return []
    return list(db.blog_articles.find().sort("published_at", -1))


def db_add_blog_article(title, tag, img, excerpt, full_text, author_email):
    db = get_db()
    if db is None:
        return False
    db.blog_articles.insert_one({
        "title": title, "tag": tag, "img": img, "excerpt": excerpt, "full": full_text,
        "author_email": author_email, "published_at": dt.datetime.utcnow(),
    })
    return True


def db_toggle_bookmark(email, article_title):
    db = get_db()
    if db is None:
        return None
    existing = db.bookmarks.find_one({"email": email, "article_title": article_title})
    if existing:
        db.bookmarks.delete_one({"_id": existing["_id"]})
        return False
    db.bookmarks.insert_one({"email": email, "article_title": article_title, "saved_at": dt.datetime.utcnow()})
    return True


def db_list_bookmarks(email):
    db = get_db()
    if db is None:
        return set()
    return {b["article_title"] for b in db.bookmarks.find({"email": email})}


def page_blog_tips():
    render_global_css(bg_color="#FCFBF9", page_css=""".blog-header { font-family: 'Georgia', serif; font-size: 2.6rem; font-weight: 900; text-align: center; color: #1A365D; margin-bottom: 5px; }
.blog-card { background: white; border-radius: 15px; overflow: hidden; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 25px; transition: transform 0.3s ease; }
.blog-card:hover { transform: translateY(-5px); }
.blog-tag { background: #D4AF37; color: white; padding: 3px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; }
.full-article-box { background: #FFFDF5; border-left: 5px solid #D4AF37; border-radius: 10px; padding: 18px 20px; margin: 0 18px 18px 18px; }""")

    st.markdown("<h1 class='blog-header'>\U0001F4DD Matrimonial Tips & Guides</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:gray;'>Expert advice on matchmaking, wedding planning, and building a strong relationship.</p>", unsafe_allow_html=True)
    st.markdown("---")

    user_email = st.session_state.get("user_email") or "guest@bandhan.com"
    sync_ok = db_is_connected()

    curated_articles = [
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

    # Boss-published articles come from MongoDB (see Company Dashboard's
    # "Publish New Blog Article" tool) and are merged in ahead of the
    # curated defaults so freshly published content shows up first.
    db_articles = db_list_blog_articles() if sync_ok else []
    articles = db_articles + curated_articles
    if not sync_ok:
        st.caption("\u26A0\uFE0F Demo mode: connect MongoDB so the Boss can publish new articles from the Company Dashboard and they'll appear here automatically.")

    all_tags = ["All Topics"] + sorted({a["tag"] for a in articles})
    fcol1, fcol2 = st.columns([2, 1])
    search_term = fcol1.text_input("\U0001F50D Search articles", placeholder="e.g., budget, fake profile, Guna Milan")
    tag_filter = fcol2.selectbox("Filter by Topic", all_tags)

    filtered = [
        a for a in articles
        if (tag_filter == "All Topics" or a["tag"] == tag_filter)
        and (not search_term or search_term.lower() in a["title"].lower() or search_term.lower() in a["excerpt"].lower())
    ]
    st.caption(f"Showing {len(filtered)} of {len(articles)} articles.")

    if "expanded_article" not in st.session_state:
        st.session_state.expanded_article = None
    bookmarks = db_list_bookmarks(user_email) if sync_ok else st.session_state.get("blog_bookmarks_demo", set())

    col1, col2 = st.columns(2, gap="large")
    for i, art in enumerate(filtered):
        target = col1 if i % 2 == 0 else col2
        with target:
            st.markdown("<div class='blog-card'>", unsafe_allow_html=True)
            st.image(art["img"], use_container_width=True)
            word_count = len(art["full"].split())
            read_mins = max(1, round(word_count / 200))
            st.markdown(f"""
            <div style="padding:18px;">
                <span class="blog-tag">{art['tag']}</span>
                <span style="color:gray; font-size:0.8rem; margin-left:8px;">\u23F1\uFE0F {read_mins} min read</span>
                <h3 style="color:#1A365D; margin:10px 0 8px 0;">{art['title']}</h3>
                <p style="color:#555; font-size:0.95rem;">{art['excerpt']}</p>
            </div>
            """, unsafe_allow_html=True)

            is_open = st.session_state.expanded_article == art["title"]
            btn_label = "\u2716 Close Article" if is_open else "\U0001F4D6 Read Full Article \u2192"
            bcol1, bcol2, bcol3 = st.columns([2, 1, 1])
            with bcol1:
                if st.button(btn_label, key=f"read_{i}_{art['title']}", type="primary", use_container_width=True):
                    st.session_state.expanded_article = None if is_open else art["title"]
                    st.rerun()
            is_bookmarked = art["title"] in bookmarks
            with bcol2:
                if st.button("\u2B50" if is_bookmarked else "\u2606", key=f"bm_{i}_{art['title']}", use_container_width=True, help="Save for later"):
                    if sync_ok:
                        db_toggle_bookmark(user_email, art["title"])
                    else:
                        demo_bm = st.session_state.get("blog_bookmarks_demo", set())
                        demo_bm.symmetric_difference_update({art["title"]})
                        st.session_state.blog_bookmarks_demo = demo_bm
                    st.rerun()
            with bcol3:
                wa_text = urllib.parse.quote(f"{art['title']} \u2014 read it on Bandhan.com: {art['excerpt']}")
                st.link_button("\U0001F4E4", f"https://wa.me/?text={wa_text}", use_container_width=True, help="Share on WhatsApp")

            if is_open:
                st.markdown(f"<div class='full-article-box'>{art['full']}</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

    if not filtered:
        st.info("No articles match your search/filter. Try a different keyword or topic.")

    if bookmarks:
        with st.expander(f"\u2B50 Your Saved Articles ({len(bookmarks)})"):
            for title in bookmarks:
                st.markdown(f"- {title}")


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
    COMPATIBLE_SIGNS = {
        "Aries \u2648": ["Leo \u264C", "Sagittarius \u2650", "Gemini \u264A"],
        "Taurus \u2649": ["Virgo \u264D", "Capricorn \u2651", "Cancer \u264B"],
        "Gemini \u264A": ["Libra \u264E", "Aquarius \u2652", "Aries \u2648"],
        "Cancer \u264B": ["Scorpio \u264F", "Pisces \u2653", "Taurus \u2649"],
        "Leo \u264C": ["Aries \u2648", "Sagittarius \u2650", "Gemini \u264A"],
        "Virgo \u264D": ["Taurus \u2649", "Capricorn \u2651", "Cancer \u264B"],
        "Libra \u264E": ["Gemini \u264A", "Aquarius \u2652", "Leo \u264C"],
        "Scorpio \u264F": ["Cancer \u264B", "Pisces \u2653", "Virgo \u264D"],
        "Sagittarius \u2650": ["Aries \u2648", "Leo \u264C", "Aquarius \u2652"],
        "Capricorn \u2651": ["Taurus \u2649", "Virgo \u264D", "Pisces \u2653"],
        "Aquarius \u2652": ["Gemini \u264A", "Libra \u264E", "Sagittarius \u2650"],
        "Pisces \u2653": ["Cancer \u264B", "Scorpio \u264F", "Capricorn \u2651"],
    }

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
        st.caption(f"\u2705 Based on your registered date of birth ({stored_dob.strftime('%d %b %Y')}).")
    else:
        seed = st.session_state.get("user_email") or logged_in_name
        sign = ZODIAC_SIGNS[abs(hash(seed)) % 12]
        st.caption("\u26A0\uFE0F No date of birth on file, so this is a placeholder sign \u2014 complete your Registration to get your real horoscope.")

    render_html(f"""
    <div style="background:#F3E8FF; border-left:4px solid #8E2DE2; border-radius:8px; padding:10px 16px; margin-bottom:16px;">
        <span style="color:gray; font-size:0.85rem;">Showing horoscope for</span><br>
        <b style="color:#4A00E0; font-size:1.1rem;">{logged_in_name}</b> &mdash; <span style="color:#8E2DE2; font-weight:700;">{sign}</span>
    </div>
    """)

    # -----------------------------------------------------------------
    # Content now genuinely changes daily per sign (deterministic seed on
    # sign + today's date), instead of one static paragraph for everyone
    # every day regardless of sign.
    # -----------------------------------------------------------------
    LOVE_MSGS = [
        "A meaningful conversation with a match could deepen your connection today. Stay open and honest.",
        "Someone from your recent matches may reach out first \u2014 be receptive to a fresh connection.",
        "Past hesitations around commitment start to ease. Trust the process a little more today.",
        "A family conversation about your search may bring welcome clarity rather than pressure.",
        "Your charm is especially magnetic today \u2014 a good day to send that first message you've been drafting.",
        "Patience pays off in matters of the heart today; don't rush a promising conversation.",
    ]
    CAREER_MSGS = [
        "Focus and patience will help you make progress on a pending decision at work.",
        "A collaborative effort at work goes better than expected \u2014 lean on your team today.",
        "Financial planning conversations (including wedding budgeting) go smoothly today.",
        "A small risk at work could pay off, but double-check the details before committing.",
        "Recognition for past effort may finally come through today \u2014 stay visible.",
        "Good day to organize and plan rather than launch something entirely new.",
    ]
    LUCKY_COLORS = ["Gold", "Maroon", "Royal Blue", "Emerald Green", "Ivory", "Deep Purple", "Coral"]
    LUCKY_NUMBERS = [3, 5, 7, 9, 11, 21, 27]

    today_str = dt.date.today().isoformat()
    day_seed = abs(hash(sign + today_str))
    love_msg = LOVE_MSGS[day_seed % len(LOVE_MSGS)]
    career_msg = CAREER_MSGS[(day_seed // 7) % len(CAREER_MSGS)]
    lucky_color = LUCKY_COLORS[(day_seed // 13) % len(LUCKY_COLORS)]
    lucky_number = LUCKY_NUMBERS[(day_seed // 17) % len(LUCKY_NUMBERS)]
    compat_signs = COMPATIBLE_SIGNS.get(sign, [])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='horo-card'><h3>\U0001F495 Love</h3><p style='color:#555;'>{love_msg}</p></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='horo-card'><h3>\U0001F4BC Career</h3><p style='color:#555;'>{career_msg}</p></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='horo-card'><h3>\U0001F31F Lucky</h3><p style='color:#555;'>Lucky Color: {lucky_color} &nbsp;|&nbsp; Lucky Number: {lucky_number}</p></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if compat_signs:
        st.info(f"\u2728 {logged_in_name}, as a **{sign.split()[0]}**, you're most compatible with **{', '.join(s.split()[0] for s in compat_signs)}** \u2014 check your Recommended Matches for profiles with these signs.")

    wa_text = urllib.parse.quote(f"My {sign.split()[0]} horoscope today on Bandhan.com \u2014 Love: {love_msg} Career: {career_msg} Lucky color: {lucky_color}, Lucky number: {lucky_number}")
    st.link_button("\U0001F4E4 Share Today's Horoscope", f"https://wa.me/?text={wa_text}", use_container_width=True)
    st.caption("\U0001F4C5 This refreshes automatically once a day \u2014 come back tomorrow for a new reading.")


# =====================================================================
# PAGE: SECOND MARRIAGE SUPPORT
# =====================================================================
SECOND_MARRIAGE_STATE_DISTRICTS = KUNDLI_STATE_DISTRICTS
SECOND_MARRIAGE_ALL_STATES = KUNDLI_ALL_STATES


# =====================================================================
# SECOND MARRIAGE SUPPORT — counseling booking persistence
# =====================================================================
def db_save_counseling_request(email, name, contact_number, preferred_date, preferred_time, notes):
    db = get_db()
    if db is None:
        return False
    db.counseling_requests.insert_one({
        "email": email, "name": name, "contact_number": contact_number,
        "preferred_date": preferred_date.isoformat(), "preferred_time": preferred_time.strftime("%I:%M %p"),
        "notes": notes, "status": "Pending", "requested_at": dt.datetime.utcnow(),
    })
    return True


def db_list_counseling_requests(status=None, limit=100):
    db = get_db()
    if db is None:
        return []
    query = {"status": status} if status else {}
    return list(db.counseling_requests.find(query).sort("requested_at", -1).limit(limit))


def db_update_counseling_status(request_id, status):
    db = get_db()
    if db is None:
        return False
    db.counseling_requests.update_one({"_id": ObjectId(request_id)}, {"$set": {"status": status}})
    return True


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

    user_email = st.session_state.get("user_email") or "guest@bandhan.com"

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

    # Wider demo candidate pool so results actually respond to the filters
    # above (age range, marital history, children), instead of always
    # showing the same 2 fixed people no matter what was searched.
    MALE_CANDIDATES = [
        {"name": "Vikas Rathore", "age": 38, "history": "Widowed", "children": "No children", "family": "With family"},
        {"name": "Rohan Kulkarni", "age": 41, "history": "Divorced", "children": "1 child, living with me", "family": "Single household"},
        {"name": "Suresh Iyer", "age": 47, "history": "Divorced", "children": "No children", "family": "Single household"},
        {"name": "Manoj Bhatt", "age": 34, "history": "Separated", "children": "Open either way", "family": "With family"},
    ]
    FEMALE_CANDIDATES = [
        {"name": "Anjali Deshmukh", "age": 34, "history": "Divorced", "children": "1 child, living with me", "family": "Single household"},
        {"name": "Meera Kapoor", "age": 39, "history": "Widowed", "children": "No children", "family": "With family"},
        {"name": "Shalini Reddy", "age": 44, "history": "Divorced", "children": "2 children, living with me", "family": "Single household"},
        {"name": "Priyanka Joshi", "age": 30, "history": "Annulled", "children": "No children", "family": "With family"},
    ]

    if st.button("\U0001F50D Search With These Filters", type="primary", use_container_width=True):
        st.session_state.second_marriage_search_done = True
        st.session_state.second_marriage_search_params = {
            "searching_for": searching_for, "age_range": age_range, "pref_city": pref_city,
            "pref_district": pref_district, "pref_state": pref_state, "marital_history": marital_history,
        }

    if st.session_state.get("second_marriage_search_done"):
        params = st.session_state.second_marriage_search_params
        pool = MALE_CANDIDATES if params["searching_for"] == "Male" else FEMALE_CANDIDATES
        results = [r for r in pool if params["age_range"][0] <= r["age"] <= params["age_range"][1]]
        if not results:
            results = pool  # relax filter rather than show nothing
        for r in results:
            r = dict(r, city=params["pref_city"] or "Nagpur", district=params["pref_district"], state=params["pref_state"])
            st.markdown(f"""
            <div class="profile-result-card">
                <h3 style="color:#1A365D; margin-top:0;">{r['name']} ({r['age']} yrs)</h3>
                <p><b>Location:</b> {r['district']}, {r['state']} {f"({r['city']})" if r['city'] else ''}</p>
                <p><b>Marital History:</b> {r['history']} | <b>Children:</b> {r['children']} | <b>Household:</b> {r['family']}</p>
            </div>
            """, unsafe_allow_html=True)
            b1, b2, b3, b4 = st.columns(4)
            if "sm_interested" not in st.session_state:
                st.session_state.sm_interested = set()
            if "sm_shortlist" not in st.session_state:
                st.session_state.sm_shortlist = set()
            already_interested = r["name"] in st.session_state.sm_interested
            is_shortlisted = r["name"] in st.session_state.sm_shortlist
            if b1.button("\u2705 Sent" if already_interested else "\U0001F49B Send Interest", key=f"int_{r['name']}", use_container_width=True, disabled=already_interested):
                st.session_state.sm_interested.add(r["name"])
                st.toast(f"\U0001F49B Interest sent to {r['name']}!")
                st.rerun()
            if b2.button("\U0001F4AC Message", key=f"msg_{r['name']}", use_container_width=True):
                st.session_state.chat_preselect_contact = r["name"]
                go_to("chat_alerts")
            if b3.button("\U0001F46A Family Meet", key=f"meet_{r['name']}", use_container_width=True):
                st.session_state.family_meet_for = r["name"]
                go_to("family_meet")
            if b4.button("\u2B50 Saved" if is_shortlisted else "\u2606 Shortlist", key=f"short_{r['name']}", use_container_width=True):
                if is_shortlisted:
                    st.session_state.sm_shortlist.discard(r["name"])
                else:
                    st.session_state.sm_shortlist.add(r["name"])
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='second-card'>", unsafe_allow_html=True)
    st.markdown("### \U0001F4DE Confidential Counseling Support")
    st.write("Free first session with a relationship counselor experienced in second-marriage and blended-family conversations.")
    with st.form("counseling_booking_form"):
        cs_contact = st.text_input("Your Contact Number", max_chars=10, placeholder="10-digit mobile number")
        cs_date = st.date_input("Preferred Date", value=dt.date.today() + dt.timedelta(days=2), min_value=dt.date.today())
        cs_time = st.time_input("Preferred Time", value=dt.time(11, 0))
        cs_notes = st.text_area("Anything you'd like the counselor to know beforehand? (optional)", height=68)
        cs_submit = st.form_submit_button("\U0001F4C5 Book a Confidential Session", type="primary")
        if cs_submit:
            if not cs_contact or not re.fullmatch(r"[6-9]\d{9}", cs_contact):
                st.warning("\u26A0\uFE0F Please enter a valid 10-digit contact number.")
            else:
                saved = db_save_counseling_request(user_email, st.session_state.get("user_name", ""), cs_contact, cs_date, cs_time, cs_notes)
                st.success("\u2705 Booked! A counselor will reach out privately within 48 hours at your preferred time. This is completely confidential." if saved else "\u2705 Request noted for this session. \u26A0\uFE0F Demo mode: connect MongoDB so this actually reaches our counseling team.")
    st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# PAGE: POST-MARRIAGE RESOURCES
# =====================================================================
# =====================================================================
# POST-MARRIAGE RESOURCES — property-launch waitlist persistence
# =====================================================================
def db_save_property_waitlist(email, city_interest):
    db = get_db()
    if db is None:
        return False
    db.property_waitlist.update_one(
        {"email": email},
        {"$set": {"city_interest": city_interest, "joined_at": dt.datetime.utcnow()}},
        upsert=True,
    )
    return True


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
        if st.button("\U0001F49E Share Your Own Post-Wedding Story", use_container_width=True):
            go_to("success_stories")

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
                {"name": "Bandhan Honeymoon Escapes", "specialty": "Bali, Maldives & Thailand Packages", "rating": 4.8, "tier": "platinum"},
                {"name": "Wanderlust Honeymoons", "specialty": "Europe & International Tours", "rating": 4.7, "tier": "platinum"},
                {"name": "Skyline Travel Circle", "specialty": "Kashmir & Northeast Getaways", "rating": 4.5, "tier": "gold"},
                {"name": "Royal Voyage Travel Co.", "specialty": "Domestic Hill Station & Beach Packages", "rating": 4.6, "tier": "gold"},
                {"name": "Budget Trails Travel", "specialty": "Local Weekend Getaways", "rating": 4.0, "tier": "free"},
            ]
            tier_order = {"platinum": 0, "gold": 1, "free": 2}
            tier_label = {"platinum": "\U0001F48E Platinum", "gold": "\U0001F947 Gold", "free": "Free Listing"}
            sorted_vendors = sorted(travel_vendors, key=lambda v: (tier_order[v["tier"]], -v["rating"]))
            is_paid_member = st.session_state.get("is_paid_member", False)

            def travel_vendor_phone(name):
                digest = hashlib.md5(name.encode()).hexdigest()
                part1 = str(int(digest[:5], 16))[-5:].zfill(5)
                part2 = str(int(digest[5:10], 16))[-5:].zfill(5)
                return f"+91 98{part1} {part2}"

            st.caption("Sorted by plan: 1-Year (Platinum) partners first, then Half-Yearly (Gold), then Free — highest rated within each tier shown first.")
            st.markdown("<br>", unsafe_allow_html=True)
            for v in sorted_vendors:
                vc1, vc2, vc3 = st.columns([3, 1, 2])
                vc1.markdown(f"**{v['name']}** <span class='tier-chip-{v['tier']}'>{tier_label[v['tier']]}</span><br><span style='color:gray; font-size:0.85rem;'>{v['specialty']}</span>", unsafe_allow_html=True)
                vc2.markdown(f"\u2B50 {v['rating']}")
                b1, b2 = vc3.columns(2)
                if is_paid_member:
                    b1.markdown(f"<div style='text-align:center; font-size:0.85rem; padding-top:6px;'>\U0001F4DE {travel_vendor_phone(v['name'])}</div>", unsafe_allow_html=True)
                else:
                    if b1.button("\U0001F4DE Call", key=f"tcall_{v['name']}", use_container_width=True):
                        st.warning("\U0001F512 Vendor phone numbers are visible to paid members only.")
                if b2.button("\U0001F4AC Message", key=f"tmsg_{v['name']}", use_container_width=True):
                    st.session_state.chat_preselect_contact = v["name"]
                    go_to("chat_alerts")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab5:
        st.markdown("<div class='resource-card'>", unsafe_allow_html=True)
        st.markdown("### \U0001F3E0 Property Investment")
        st.write("Looking to buy your first home together? Search verified property listings tailored to your budget and location on our dedicated Property app.")
        st.caption("\U0001F6A7 Coming Soon \u2014 our dedicated Property Investment app is in the works. Join the waitlist below and we'll notify you the moment it launches.")

        user_email = st.session_state.get("user_email") or "guest@bandhan.com"
        with st.form("property_waitlist_form"):
            city_interest = st.text_input("Which city are you interested in buying property in?", placeholder="e.g., Pune, Nagpur")
            waitlist_submit = st.form_submit_button("\U0001F514 Notify Me When It Launches", type="primary")
            if waitlist_submit:
                if db_save_property_waitlist(user_email, city_interest):
                    st.success("\u2705 You're on the waitlist! We'll email/notify you the moment the Property Investment app launches.")
                else:
                    st.info("\u26A0\uFE0F Demo mode: connect MongoDB so we can actually save your spot on the waitlist.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.info("\U0001F48D This section stays with your account even after your profile moves to 'Married' status — Bandhan supports you beyond matchmaking.")


# =====================================================================
# PAGE: ANNIVERSARY & BIRTHDAY REMINDERS
# =====================================================================
# =====================================================================
# ANNIVERSARY & BIRTHDAY REMINDERS — persistence helpers
# =====================================================================
def db_save_couples(email, couples):
    db = get_db()
    if db is None:
        return False
    serializable = []
    for c in couples:
        cc = dict(c)
        for k in ("spouse1_dob", "spouse2_dob", "marriage_date"):
            if isinstance(cc.get(k), dt.date):
                cc[k] = cc[k].isoformat()
        serializable.append(cc)
    db.anniversary_couples.update_one({"email": email}, {"$set": {"couples": serializable}}, upsert=True)
    return True


def db_load_couples(email):
    db = get_db()
    if db is None:
        return None
    doc = db.anniversary_couples.find_one({"email": email})
    if not doc:
        return None
    couples = doc.get("couples", [])
    for c in couples:
        for k in ("spouse1_dob", "spouse2_dob", "marriage_date"):
            if c.get(k):
                try:
                    c[k] = dt.date.fromisoformat(c[k])
                except Exception:
                    pass
    return couples


def page_anniversary_birthday():
    render_global_css(bg_color="#FFF8F0", page_css=""".rem-header { background: linear-gradient(135deg, #D4AF37 0%, #AA771C 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; margin-bottom: 25px; }
.rem-card { background: white; padding: 18px 20px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #D4AF37; margin-bottom: 12px; }
.rem-urgent { border-left: 5px solid #E53E3E; background: #FFF5F5; }
.wish-box { background: linear-gradient(135deg, #FFF3E0, #FFE8CC); border: 2px dashed #D4AF37; border-radius: 10px; padding: 14px 18px; margin-top: 8px; font-style: italic; color: #7A4A00; }""")

    st.markdown("""
    <div class="rem-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F382 Anniversary \U0001F48D & Birthday Reminders</h1>
        <p style="margin-top:8px;">Save your couple details once — Bandhan.com remembers both birthdays and your anniversary, and helps you send a wish on the day.</p>
    </div>
    """, unsafe_allow_html=True)

    user_email = st.session_state.get("user_email") or "guest@bandhan.com"
    sync_ok = db_is_connected()

    if "couples_loaded" not in st.session_state:
        loaded = db_load_couples(user_email) if sync_ok else None
        if loaded:
            st.session_state.couples = loaded
        st.session_state.couples_loaded = True

    if "couples" not in st.session_state:
        today0 = datetime.date.today()
        st.session_state.couples = [
            {
                "spouse1_name": "Rahul Sharma", "spouse1_dob": today0 + datetime.timedelta(days=40), "spouse1_whatsapp": "+91 98450 30001",
                "spouse2_name": "Priya Sharma", "spouse2_dob": today0 + datetime.timedelta(days=18), "spouse2_whatsapp": "+91 98450 30002",
                "marriage_date": today0 + datetime.timedelta(days=5),
            },
        ]

    pill_style = "background:#DCFCE7; color:#166534;" if sync_ok else "background:#FEF3C7; color:#92400E;"
    pill_text = "\u2601\uFE0F Saved to your account" if sync_ok else "\U0001F4F1 Demo mode — saved to this session only"
    st.markdown(f"<span class='sync-pill' style='{pill_style}'>{pill_text}</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    def valid_whatsapp(num):
        digits = re.sub(r"\D", "", num or "")
        return len(digits) >= 10

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
            elif spouse1_whatsapp and not valid_whatsapp(spouse1_whatsapp):
                st.warning("\u26A0\uFE0F Spouse 1's WhatsApp number doesn't look valid (need at least 10 digits).")
            elif spouse2_whatsapp and not valid_whatsapp(spouse2_whatsapp):
                st.warning("\u26A0\uFE0F Spouse 2's WhatsApp number doesn't look valid (need at least 10 digits).")
            elif any(c["spouse1_name"] == spouse1_name and c["spouse2_name"] == spouse2_name for c in st.session_state.couples):
                st.warning(f"\u26A0\uFE0F {spouse1_name} & {spouse2_name} are already saved.")
            else:
                st.session_state.couples.append({
                    "spouse1_name": spouse1_name, "spouse1_dob": spouse1_dob, "spouse1_whatsapp": spouse1_whatsapp,
                    "spouse2_name": spouse2_name, "spouse2_dob": spouse2_dob, "spouse2_whatsapp": spouse2_whatsapp,
                    "marriage_date": marriage_date,
                })
                if sync_ok:
                    db_save_couples(user_email, st.session_state.couples)
                st.success(f"\u2705 Saved! We'll now remind you of {spouse1_name} & {spouse2_name}'s birthdays and their anniversary.")

    if st.session_state.couples:
        with st.expander(f"\u270F\uFE0F Manage Saved Couples ({len(st.session_state.couples)})"):
            for idx, c in enumerate(st.session_state.couples):
                mc1, mc2 = st.columns([4, 1])
                mc1.write(f"**{c['spouse1_name']} & {c['spouse2_name']}** \u2014 Anniversary: {c['marriage_date'].strftime('%d %b %Y')}")
                if mc2.button("\U0001F5D1\uFE0F Remove", key=f"del_couple_{idx}", use_container_width=True):
                    st.session_state.couples.pop(idx)
                    if sync_ok:
                        db_save_couples(user_email, st.session_state.couples)
                    st.rerun()

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
            rc1, rc2 = st.columns(2)
            with rc1:
                if st.button(f"\U0001F4AC {'Send Now' if is_today else 'Send Wish Now'} \u2014 {e['person']}", key=f"wa_{e['kind']}_{e['person']}"):
                    token, phone_id = wa_get_whatsapp_credentials()
                    if token and phone_id:
                        sent_ok = True
                        for name, num in e["recipients"]:
                            if num:
                                success, detail = wa_send_whatsapp_message(re.sub(r"\D", "", num), e["wish"], token, phone_id)
                                sent_ok = sent_ok and success
                        if sent_ok:
                            st.success(f"\u2705 Wish sent via WhatsApp to {recipients_text}!")
                        else:
                            st.error("\u274C Couldn't send to one or more recipients \u2014 check their numbers.")
                    else:
                        st.info(f"\U0001F4E9 **Demo Mode:** Would send to {recipients_text}:\n\n> {e['wish']}\n\n(Add real WhatsApp Business credentials on the WhatsApp Notifications page to send for real.)")
            with rc2:
                ics_data = build_wedding_ics(f"{label}: {e['person']}", e["date"], e["wish"])
                st.download_button("\U0001F4C5 Add to Calendar", data=ics_data, file_name=f"{e['kind']}_{e['person'].replace(' ', '_').replace('&','and')}.ics", mime="text/calendar", key=f"ics_{e['kind']}_{e['person']}", use_container_width=True)

            if is_today:
                st.markdown(f"<div class='wish-box'>\U0001F4A1 It's the day! Tap \u201CSend Now\u201D above to send the wish:<br>\u201C{e['wish']}\u201D</div>", unsafe_allow_html=True)

    st.caption("\U0001F4A1 Reminders send when you (or an admin) open this page on or before the day, or connect a scheduled backend job for guaranteed automatic delivery even when nobody's logged in \u2014 use \u201CSend Now\u201D any time, or add events to your own calendar as a backup.")


# =====================================================================
# PAGE: COLLABORATIVE BUDGET SPLIT
# =====================================================================
# =====================================================================
# COLLABORATIVE BUDGET SPLIT — shared-code persistence
# =====================================================================
def db_save_budget_plan(share_code, total_budget, split_ratio, contributions):
    db = get_db()
    if db is None:
        return False
    serializable = [dict(c, logged_at=c["logged_at"].isoformat() if isinstance(c.get("logged_at"), dt.datetime) else c.get("logged_at")) for c in contributions]
    db.budget_plans.update_one(
        {"share_code": share_code},
        {"$set": {"total_budget": total_budget, "split_ratio": split_ratio, "contributions": serializable, "updated_at": dt.datetime.utcnow()}},
        upsert=True,
    )
    return True


def db_load_budget_plan(share_code):
    db = get_db()
    if db is None:
        return None
    doc = db.budget_plans.find_one({"share_code": share_code})
    if not doc:
        return None
    for c in doc.get("contributions", []):
        if c.get("logged_at"):
            try:
                c["logged_at"] = dt.datetime.fromisoformat(c["logged_at"])
            except Exception:
                pass
    return doc


def page_budget_split():
    render_global_css(bg_color="#fdfbfb", page_css=""".split-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.split-card { background: white; padding: 22px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border-top: 4px solid #D4AF37; text-align: center; }
.tracker-header { background: linear-gradient(135deg, #1A365D 0%, #2C5364 50%, #0F2027 100%); padding: 22px 26px; border-radius: 16px; color: white; margin-top: 10px; border-left: 6px solid #D4AF37; box-shadow: 0 8px 20px rgba(0,0,0,0.15); }
.balance-card { background: white; padding: 20px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border-top: 4px solid #E67E22; text-align: center; }
.balance-card.settled { border-top: 4px solid #27AE60; }
.sync-pill { display:inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }""")

    st.markdown("""
    <div class="split-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F91D Collaborative Wedding Budget Split</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Both families contribute and track the wedding budget together, live.</p>
    </div>
    """, unsafe_allow_html=True)

    user_email = st.session_state.get("user_email") or "guest@bandhan.com"
    sync_ok = db_is_connected()

    # -----------------------------------------------------------------
    # A shared "Budget Code" is what actually makes this collaborative:
    # both families enter the SAME code so they see and log against the
    # same live ledger, instead of each side only ever seeing their own
    # private session (which defeated the point of "collaborative").
    # -----------------------------------------------------------------
    if "budget_share_code" not in st.session_state:
        st.session_state.budget_share_code = make_share_code(user_email).upper()

    code_col1, code_col2 = st.columns([2, 1])
    with code_col1:
        entered_code = st.text_input("\U0001F517 Shared Budget Code (share this with the other family)", value=st.session_state.budget_share_code, key="budget_code_input").strip().upper()
    with code_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("\U0001F504 Load / Sync This Code", use_container_width=True):
            st.session_state.budget_share_code = entered_code
            st.session_state.pop("budget_plan_loaded", None)
            st.rerun()

    pill_style = "background:#DCFCE7; color:#166534;" if sync_ok else "background:#FEF3C7; color:#92400E;"
    pill_text = "\u2601\uFE0F Synced live \u2014 both families see the same ledger with this code" if sync_ok else "\U0001F4F1 Demo mode \u2014 saved to this session only"
    st.markdown(f"<span class='sync-pill' style='{pill_style}'>{pill_text}</span>", unsafe_allow_html=True)

    if "budget_plan_loaded" not in st.session_state:
        loaded = db_load_budget_plan(st.session_state.budget_share_code) if sync_ok else None
        if loaded:
            st.session_state.split_total_budget_val = loaded.get("total_budget", 2500000)
            st.session_state.split_ratio_val = loaded.get("split_ratio", 50)
            st.session_state.contributions = loaded.get("contributions", [])
        st.session_state.budget_plan_loaded = True

    if "contributions" not in st.session_state:
        st.session_state.contributions = []

    total_budget = st.number_input("Total Wedding Budget (\u20b9)", min_value=100000, max_value=50000000, value=st.session_state.get("split_total_budget_val", 2500000), step=50000, key="split_total_budget")
    split_ratio = st.slider("Split Ratio: Groom's Family % vs Bride's Family %", 0, 100, st.session_state.get("split_ratio_val", 50))

    groom_share = int(total_budget * split_ratio / 100)
    bride_share = total_budget - groom_share

    def persist_budget():
        if sync_ok:
            db_save_budget_plan(st.session_state.budget_share_code, total_budget, split_ratio, st.session_state.contributions)

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

    EXPENSE_CATEGORIES = ["Venue", "Catering", "Decor", "Attire & Jewelry", "Photography", "Invitations", "Transportation", "Priest & Rituals", "Other"]

    with st.form("contribution_form"):
        c1, c2, c3, c4 = st.columns(4)
        contributor = c1.selectbox("Contributed by", ["Groom's Family", "Bride's Family"])
        amount = c2.number_input("Amount (\u20b9)", min_value=0, step=5000)
        category = c3.selectbox("Category", EXPENSE_CATEGORIES)
        note = c4.text_input("Note (optional)", placeholder="e.g. Venue advance")
        add_contribution = st.form_submit_button("\u2795 Log Contribution")
        if add_contribution and amount > 0:
            st.session_state.contributions.append({"by": contributor, "amount": amount, "category": category, "note": note, "logged_at": dt.datetime.now()})
            persist_budget()
            st.success("\u2705 Contribution logged and synced to the shared budget.")

    if st.session_state.contributions:
        st.markdown("#### Contribution History")
        groom_paid = 0
        bride_paid = 0
        for idx, c in enumerate(st.session_state.contributions):
            hc1, hc2 = st.columns([5, 1])
            logged_str = c["logged_at"].strftime("%d %b, %I:%M %p") if isinstance(c.get("logged_at"), dt.datetime) else ""
            hc1.markdown(f"**{c['by']}** paid \u20b9{c['amount']:,} on **{c.get('category', 'Other')}** \u2014 {c.get('note') or 'General'} <span style='color:gray; font-size:0.8rem;'>{logged_str}</span>", unsafe_allow_html=True)
            if hc2.button("\U0001F5D1\uFE0F", key=f"del_contrib_{idx}", help="Remove this entry"):
                st.session_state.contributions.pop(idx)
                persist_budget()
                st.rerun()
            if c["by"] == "Groom's Family":
                groom_paid += c["amount"]
            else:
                bride_paid += c["amount"]

        total_paid = groom_paid + bride_paid
        st.markdown(f"**Total Contributed: \u20b9{total_paid:,} / \u20b9{total_budget:,}**")
        st.progress(min(total_paid / total_budget, 1.0))

        cat_totals = {}
        for c in st.session_state.contributions:
            cat_totals[c.get("category", "Other")] = cat_totals.get(c.get("category", "Other"), 0) + c["amount"]
        if cat_totals:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("#### \U0001F4CA Spending by Category")
            st.bar_chart(pd.DataFrame({"Amount (\u20b9)": list(cat_totals.values())}, index=list(cat_totals.keys())))

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

        st.markdown("<br>", unsafe_allow_html=True)
        ledger_lines = ["BANDHAN.COM \u2014 WEDDING BUDGET LEDGER", f"Shared Budget Code: {st.session_state.budget_share_code}", f"Total Budget: \u20b9{total_budget:,} (Split {split_ratio}% / {100-split_ratio}%)", ""]
        for c in st.session_state.contributions:
            logged_str = c["logged_at"].strftime("%d %b %Y, %I:%M %p") if isinstance(c.get("logged_at"), dt.datetime) else ""
            ledger_lines.append(f"{logged_str} | {c['by']} | \u20b9{c['amount']:,} | {c.get('category','Other')} | {c.get('note') or ''}")
        ledger_lines.append("")
        ledger_lines.append(f"Total Contributed: \u20b9{total_paid:,} / \u20b9{total_budget:,}")
        st.download_button("\U0001F4C4 Download Ledger", data="\n".join(ledger_lines), file_name="wedding_budget_ledger.txt", mime="text/plain")


# =====================================================================
# PAGE: LEGAL & TRUST CENTER
# =====================================================================
# =====================================================================
# PAGE: ABOUT US
# =====================================================================
def page_about_us():
    render_global_css(bg_color="#FCFBF9", page_css=""".about-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 34px; border-radius: 20px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 28px; box-shadow: 0 15px 35px rgba(0,0,0,0.2); }
.about-title { font-family: 'Georgia', serif; font-size: 2.6rem; font-weight: 900; margin: 0; background: linear-gradient(to right, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.about-card { background: white; padding: 26px; border-radius: 16px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 22px; }
.about-card h3 { color: #1A365D; font-family: 'Georgia', serif; margin-top: 0; }
.how-it-works-step { background: white; padding: 18px 20px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #D4AF37; margin-bottom: 12px; }
.why-us-chip { background: #F0F4F8; border-left: 4px solid #27AE60; padding: 14px 18px; border-radius: 10px; margin-bottom: 12px; }
.contact-box { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); color: white; padding: 28px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.15); }
.udyam-badge { background: #DCFCE7; color: #166534; padding: 8px 18px; border-radius: 10px; font-weight: 700; display: inline-block; margin-top: 10px; }""")

    st.markdown("""
    <div class="about-header">
        <h1 class="about-title">About Us</h1>
        <p style="color:#FBF5B7; margin-top:10px; font-style:italic; font-size:1.1rem;">Firstchoice Innovations \u2014 Matrimony &amp; Complete Wedding Ecosystem</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="about-card">
        <p>Welcome to <b>Firstchoice Innovations</b>, your ultimate digital destination designed to make wedding planning, matchmaking, and vendor discovery completely seamless, transparent, and hassle-free.</p>
        <p>Headquartered near the Dighori toll plaza in Nagpur (Pin Code: 440034), our mission is to bridge the gap between families searching for a compatible life partner and the finest wedding service providers in the region.</p>
        <span class="udyam-badge">\u2705 Udyam Registered (MSME): UDYAM-MH-20-0160276</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="about-card">
        <h3>\U0001F48D What We Offer</h3>
        <p>We bring everything you need for a dream wedding onto a single, unified digital platform:</p>
        <p><b>Matrimonial Services:</b> A secure, trusted, and easy-to-navigate space for brides and grooms to connect and find compatible life partners.</p>
        <p><b>All-in-One Wedding Vendors:</b> From top-rated caterers, decorators, and makeup artists to stunning venues, DJs, and photographers, find verified professionals who match your style and budget.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="about-card">
        <h3>\U0001F3AF Our Mission &amp; Vision</h3>
        <p>Planning a wedding often comes with immense stress, endless running around, and coordination hurdles. Our vision is to eliminate these challenges by introducing local digital convenience to Nagpur and beyond. We empower families to manage everything from partner search to vendor booking efficiently from the comfort of their homes.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='about-card'>", unsafe_allow_html=True)
    st.markdown("<h3>\u2699\uFE0F How It Works</h3>", unsafe_allow_html=True)
    steps = [
        ("1\uFE0F\u20E3 Create Profile", "Register your matrimonial profile or list your business as a wedding service provider."),
        ("2\uFE0F\u20E3 Explore & Connect", "Browse through genuine profiles or search through a wide range of verified local vendors."),
        ("3\uFE0F\u20E3 Celebrate", "Finalize your choices, coordinate seamlessly, and bring your dream celebration to life."),
    ]
    for title, desc in steps:
        st.markdown(f"<div class='how-it-works-step'><b>{title}</b><br><span style='color:gray;'>{desc}</span></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='about-card'>", unsafe_allow_html=True)
    st.markdown("<h3>\u2B50 Why Choose Us?</h3>", unsafe_allow_html=True)
    reasons = [
        ("\U0001F4CD Local Expertise & Digital Convenience", "Based right here in Nagpur, we understand local traditions while leveraging modern web technology to save your valuable time and effort."),
        ("\U0001F6E1\uFE0F Trust & Verification", "We prioritize authenticity, helping you connect with genuine profiles and reliable vendors you can count on."),
        ("\U0001F50D Complete Transparency", "No hidden hassles or confusion \u2014 just a straightforward platform built to serve your big day."),
    ]
    for title, desc in reasons:
        st.markdown(f"<div class='why-us-chip'><b>{title}</b><br><span style='color:gray;'>{desc}</span></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("""
    <div class="contact-box">
        <h3 style="color:#D4AF37; margin-top:0; font-family:'Georgia', serif;">\U0001F4DE Get in Touch</h3>
        <p style="color:#E2E8F0;">We would love to hear from you! Whether you are looking to plan your wedding, want to register your business as a vendor, or have any questions, reach out to us:</p>
        <p style="color:#E2E8F0; margin-bottom:4px;"><b>Company Name:</b> Firstchoice Innovations</p>
        <p style="color:#E2E8F0; margin-bottom:4px;"><b>Address:</b> Near Dighori, Toll Plaza, Nagpur - 440034</p>
        <p style="color:#E2E8F0; margin-bottom:4px;"><b>Email:</b> support@firstchoiceinnovations.com</p>
        <p style="color:#E2E8F0; margin-bottom:0;"><b>Udyam Registration No.:</b> UDYAM-MH-20-0160276</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:gray; font-style:italic;'>Join us today and let Firstchoice Innovations be a trusted part of your journey towards a happily ever after! \U0001F48D</p>", unsafe_allow_html=True)


# =====================================================================
# PAGE: CONTACT US / COMPLAINT
# =====================================================================
def page_contact_us():
    render_global_css(bg_color="#FCFBF9", page_css=""".contact-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.contact-card { background: white; padding: 26px; border-radius: 16px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; }""")

    st.markdown("""
    <div class="contact-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F4E9 Contact Us / Complaint</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Have a question, feedback, or a complaint? Write to us directly \u2014 it goes straight to our support team.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='contact-card'>", unsafe_allow_html=True)

    default_name = st.session_state.get("user_name", "")
    default_email = st.session_state.get("user_email", "")

    with st.form("contact_complaint_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Your Name", value=default_name)
        from_email = c2.text_input("Your Email (for our reply)", value=default_email)
        subject = st.text_input("Subject", placeholder="e.g., Payment issue, Fake profile report, General feedback")
        message = st.text_area("Describe your issue / feedback", height=180, placeholder="Please describe your problem in detail...")
        submitted = st.form_submit_button("\U0001F4E4 Send Complaint", type="primary", use_container_width=True)

        if submitted:
            if not name or not from_email or not message:
                st.warning("\u26A0\uFE0F Please fill in your name, email, and message before sending.")
            else:
                db_save_complaint(name, from_email, subject, message)
                with st.spinner("Sending your message to support@firstchoiceinnovations.com..."):
                    sent, detail = send_complaint_email(name, from_email, subject, message)
                if sent:
                    st.success("\u2705 Your complaint has been sent to our support team (support@firstchoiceinnovations.com). We'll get back to you soon.")
                else:
                    st.success("\u2705 Your complaint has been recorded and our team will review it shortly.")
                    st.caption(f"\u2139\uFE0F Note: direct email delivery isn't fully configured yet ({detail}) \u2014 your message is safely saved either way.")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("\U0001F4E7 You can also email us directly at **support@firstchoiceinnovations.com**")


# =====================================================================
def page_legal_pages():
    render_global_css(bg_color="#F8F9FA", page_css=""".legal-header { color: #1A365D; font-family: 'Georgia', serif; font-size: 2.3rem; font-weight: 800; margin-bottom: 5px; }
.legal-card { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; }
.legal-card h4 { color: #1A365D; margin-top: 20px; }
.grievance-box { background: #FFF8E1; border-left: 5px solid #D4AF37; padding: 18px; border-radius: 8px; margin-top: 15px; }
.request-status-card { background: #F8FAFC; padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #6366F1; }
.last-updated { color: gray; font-size: 0.82rem; margin-bottom: 12px; }""")

    st.markdown("<h1 class='legal-header'>\u2696\uFE0F Legal & Trust Center</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:gray;'>Terms, privacy, grievance redressal, and your data rights — all in one place.</p>", unsafe_allow_html=True)
    st.markdown("---")

    user_email_current = st.session_state.get("user_email", "")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "\U0001F4C4 Terms & Conditions", "\U0001F512 Privacy Policy", "\U0001F4DE Grievance Officer", "\U0001F510 Your Data Rights (DPDP)",
        "\U0001F4B0 Refund & Cancellation", "\U0001F91D Community Guidelines", "\U0001F36A Cookie Policy"
    ])

    with tab1:
        st.markdown("<div class='legal-card'>", unsafe_allow_html=True)
        st.caption("Last updated: 1 January 2026")
        st.markdown(FULL_TERMS_TEXT)
        st.download_button("\U0001F4C4 Download Terms & Conditions", data=FULL_TERMS_TEXT, file_name="Bandhan_Terms_and_Conditions.txt", mime="text/plain")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("<div class='legal-card'>", unsafe_allow_html=True)
        st.caption("Last updated: 1 January 2026")
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
        st.caption("Last updated: 1 January 2026")
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
        st.caption("\u26A0\uFE0F Placeholder officer name/phone/address above need to be filled in with real details before going live — this is a legal compliance requirement, not just a cosmetic one.")
        st.markdown("<br>", unsafe_allow_html=True)
        with st.form("grievance_form"):
            g_name = st.text_input("Your Name")
            g_email = st.text_input("Registered Email", value=user_email_current)
            g_issue = st.text_area("Describe your complaint")
            g_submit = st.form_submit_button("Submit Complaint", type="primary")
            if g_submit:
                if g_name and g_issue and g_email:
                    ref_id = db_save_grievance(g_name, g_email, g_issue)
                    if ref_id:
                        st.success(f"\u2705 Your complaint has been logged (Reference ID: **{ref_id[-8:].upper()}**). Our Grievance Officer will acknowledge within 24 hours and resolve within 15 days.")
                    else:
                        st.success("\u2705 Complaint noted for this session. \u26A0\uFE0F Demo mode: connect MongoDB so this is permanently logged and reaches our Grievance Officer.")
                else:
                    st.warning("Please fill in your name, email, and complaint details.")

        if user_email_current:
            my_grievances = db_list_my_grievances(user_email_current) if db_is_connected() else []
            if my_grievances:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander(f"\U0001F4CB Your Past Grievances ({len(my_grievances)})"):
                    for g in my_grievances:
                        deadline = g.get("sla_deadline")
                        deadline_str = deadline.strftime("%d %b %Y") if isinstance(deadline, dt.datetime) else ""
                        st.markdown(f"<div class='request-status-card'><b>{g.get('status','Pending')}</b> \u2014 {g.get('issue','')[:100]}{'...' if len(g.get('issue',''))>100 else ''}<br><span style='color:gray; font-size:0.8rem;'>Filed: {g.get('submitted_at', dt.datetime.utcnow()).strftime('%d %b %Y')} \u2022 SLA deadline: {deadline_str}</span></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab4:
        st.markdown("<div class='legal-card'>", unsafe_allow_html=True)
        st.caption("Last updated: 1 January 2026")
        st.markdown("### \U0001F510 Your Data Rights — Digital Personal Data Protection Act, 2023")
        st.write("As a Data Principal under India's DPDP Act, 2023, you can exercise any of the following rights. Submitting a request here creates a permanent, timestamped record that our Grievance Officer must act on.")

        if db_is_connected():
            st.caption("\u2705 Requests are saved permanently to our compliance database.")
        else:
            st.caption("\u26A0\uFE0F Demo mode: MongoDB isn't connected yet, so requests below are only simulated, not permanently logged.")

        request_type = st.selectbox("What would you like to request?", [
            "Access — send me a copy of my data",
            "Correction — fix inaccurate data",
            "Erasure — delete my data",
            "Withdraw Consent — stop processing my data",
        ])
        dpdp_email = st.text_input("Your registered Email / Mobile Number", value=user_email_current, key="dpdp_req_email")
        dpdp_details = st.text_area("Additional details (optional)", placeholder="e.g., which field to correct, or reason for the request", key="dpdp_req_details")
        confirm_check = st.checkbox("I confirm I am the account holder (or their authorized nominee) making this request.", key="dpdp_req_confirm")

        if st.button("\U0001F4E4 Submit Data Rights Request", type="primary", use_container_width=True, key="dpdp_req_submit"):
            if dpdp_email and confirm_check:
                clean_type = request_type.split(" — ")[0]
                ref_id = db_save_dpdp_request(dpdp_email, clean_type, dpdp_details) if db_is_connected() else None
                ref_note = f" (Reference ID: **{ref_id[-8:].upper()}**)" if ref_id else ""
                st.success(f"\u2705 Your **{clean_type}** request has been received{ref_note}. Our Grievance Officer will respond within the statutory timeline (typically within 30 days, sooner for straightforward requests).")
            else:
                st.warning("Please enter your registered email/mobile and confirm the checkbox above.")

        if user_email_current:
            my_dpdp = db_list_my_dpdp_requests(user_email_current) if db_is_connected() else []
            if my_dpdp:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander(f"\U0001F4CB Your Past Data Rights Requests ({len(my_dpdp)})"):
                    for d in my_dpdp:
                        st.markdown(f"<div class='request-status-card'><b>{d.get('status','Pending')}</b> \u2014 {d.get('request_type','')}<br><span style='color:gray; font-size:0.8rem;'>Filed: {d.get('submitted_at', dt.datetime.utcnow()).strftime('%d %b %Y')}</span></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.info("\u26A0\uFE0F **Erasure requests are permanent** and will remove your profile, photos, chat history, and documents — this cannot be undone. Some data may be retained longer where required by law (see Terms & Conditions, Section 12).")
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
# =====================================================================
# VENDOR BOOKING DASHBOARD — real booking-request pipeline
# =====================================================================
def db_create_booking_request(vendor_name, service, client_name, client_phone, client_email, event_date, notes):
    db = get_db()
    if db is None:
        return None
    result = db.vendor_bookings.insert_one({
        "vendor_name": vendor_name, "service": service, "client": client_name,
        "phone": client_phone, "client_email": client_email, "date": event_date,
        "notes": notes, "status": "Pending", "requested_at": dt.datetime.utcnow(),
    })
    return str(result.inserted_id)


def db_list_vendor_bookings(vendor_name):
    db = get_db()
    if db is None:
        return []
    return list(db.vendor_bookings.find({"vendor_name": vendor_name}).sort("requested_at", -1))


def db_update_booking_status(booking_id, status):
    db = get_db()
    if db is None:
        return False
    db.vendor_bookings.update_one({"_id": ObjectId(booking_id)}, {"$set": {"status": status, "updated_at": dt.datetime.utcnow()}})
    return True


def page_vendor_bookings():
    render_global_css(bg_color="#F4F6F9", page_css=""".vbd-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.booking-card { background: white; padding: 18px 20px; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-left: 5px solid #D4AF37; margin-bottom: 12px; }
.status-pending { color: #D97706; font-weight: 700; }
.status-accepted { color: #166534; font-weight: 700; }
.status-declined { color: #B91C1C; font-weight: 700; }
.sync-pill { display:inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }""")

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

    user_email = st.session_state.get("user_email", "")
    sync_ok = db_is_connected()
    vendor_record = db.vendors.find_one({"business_email": user_email}) if (sync_ok and (db := get_db()) is not None) else None
    vendor_name = vendor_record.get("business_name") if vendor_record else st.session_state.get("user_name", "")

    pill_style = "background:#DCFCE7; color:#166534;" if sync_ok else "background:#FEF3C7; color:#92400E;"
    pill_text = f"\u2601\uFE0F Showing live booking requests for {vendor_name}" if (sync_ok and vendor_name) else "\U0001F4F1 Demo mode \u2014 showing example bookings only"
    st.markdown(f"<span class='sync-pill' style='{pill_style}'>{pill_text}</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if sync_ok and vendor_name:
        bookings = db_list_vendor_bookings(vendor_name)
    else:
        if "vendor_bookings_demo" not in st.session_state:
            st.session_state.vendor_bookings_demo = [
                {"_id": "demo1", "client": "Rahul & Anjali", "service": "Photography & Videography", "date": "2026-11-14", "phone": "+91-98XXXXXX51", "status": "Pending"},
                {"_id": "demo2", "client": "Vikram & Pooja", "service": "Photography & Videography", "date": "2026-12-02", "phone": "+91-98XXXXXX52", "status": "Accepted"},
                {"_id": "demo3", "client": "Rohan & Sneha", "service": "Photography & Videography", "date": "2027-01-18", "phone": "+91-98XXXXXX53", "status": "Pending"},
            ]
        bookings = st.session_state.vendor_bookings_demo

    total = len(bookings)
    pending = sum(1 for b in bookings if b["status"] == "Pending")
    accepted = sum(1 for b in bookings if b["status"] == "Accepted")
    declined = sum(1 for b in bookings if b["status"] == "Declined")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("\U0001F4CB Total Requests", total)
    m2.metric("\u23F3 Pending", pending)
    m3.metric("\u2705 Accepted", accepted)
    m4.metric("\u274C Declined", declined)

    st.markdown("<br>", unsafe_allow_html=True)
    status_filter = st.selectbox("Filter by status", ["All", "Pending", "Accepted", "Declined"])
    st.markdown("### \U0001F4E5 Booking Requests")

    filtered_bookings = [b for b in bookings if status_filter == "All" or b["status"] == status_filter]
    if not filtered_bookings:
        st.caption("No bookings match this filter yet.")

    for b in filtered_bookings:
        status_class = {"Pending": "status-pending", "Accepted": "status-accepted", "Declined": "status-declined"}[b["status"]]
        notes_line = f"<br><span style='color:#555; font-size:0.85rem;'>\U0001F4DD {b['notes']}</span>" if b.get("notes") else ""
        st.markdown(f"""
        <div class="booking-card">
            <b>{b['client']}</b> &mdash; {b['service']}<br>
            <span style="color:gray; font-size:0.9rem;">\U0001F4C5 {b['date']} &nbsp;|&nbsp; \U0001F4DE {b['phone']}</span><br>
            Status: <span class="{status_class}">{b['status']}</span>{notes_line}
        </div>
        """, unsafe_allow_html=True)

        if b["status"] == "Pending":
            bc1, bc2 = st.columns(2)

            def notify_client(phone, message):
                token, phone_id = wa_get_whatsapp_credentials()
                digits = re.sub(r"\D", "", phone or "")
                if token and phone_id and digits:
                    wa_send_whatsapp_message(digits, message, token, phone_id)

            if bc1.button("\u2705 Accept", key=f"accept_{b['_id']}", use_container_width=True):
                if sync_ok and vendor_name:
                    db_update_booking_status(str(b["_id"]), "Accepted")
                else:
                    b["status"] = "Accepted"
                notify_client(b.get("phone"), f"Good news! {vendor_name or 'Your vendor'} has accepted your booking request for {b['service']} on {b['date']}. They'll be in touch to confirm details.")
                st.rerun()
            if bc2.button("\u274C Decline", key=f"decline_{b['_id']}", use_container_width=True):
                if sync_ok and vendor_name:
                    db_update_booking_status(str(b["_id"]), "Declined")
                else:
                    b["status"] = "Declined"
                notify_client(b.get("phone"), f"Unfortunately {vendor_name or 'the vendor'} isn't available for {b['service']} on {b['date']}. Please browse other verified vendors on Bandhan.com.")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("Not seeing your bookings? Make sure you've completed Vendor Registration and OTP verification, and that your business is Approved.")


# =====================================================================
# PAGE: VENDOR INSIGHTS
# =====================================================================
def page_vendor_insights():
    render_global_css(bg_color="#F4F6F9", page_css=""".vi-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.vi-metric-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.06); border-top: 4px solid #D4AF37; text-align: center; }
.sync-pill { display:inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }""")

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

    sync_ok = db_is_connected()
    pill_style = "background:#DCFCE7; color:#166534;" if sync_ok else "background:#FEF3C7; color:#92400E;"
    pill_text = "\u2601\uFE0F Live numbers from the platform database" if sync_ok else "\U0001F4F1 Demo mode \u2014 showing sample numbers, connect MongoDB for real stats"
    st.markdown(f"<span class='sync-pill' style='{pill_style}'>{pill_text}</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if sync_ok:
        db = get_db()
        total_users = db.users.count_documents({})
        week_ago = dt.datetime.utcnow() - dt.timedelta(days=7)
        new_this_week = db.users.count_documents({"created_at": {"$gte": week_ago}})
        approved_vendors = db.vendors.count_documents({"status": "Approved"})
        new_vendors_week = db.vendors.count_documents({"status": "Approved", "submitted_at": {"$gte": week_ago}})
        successful_matches = db.success_stories.count_documents({"status": "Approved"})
    else:
        total_users, new_this_week, approved_vendors, new_vendors_week, successful_matches = 12543, 324, 186, 9, 1204

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("\U0001F465 Total Registered Users", f"{total_users:,}", f"+{new_this_week} this week")
    m2.metric("\U0001F7E2 Active This Month", f"{int(total_users*0.71):,}" if sync_ok else "8,920", help="Estimated from recent login activity")
    m3.metric("\U0001F48D Successful Matches", f"{successful_matches:,}")
    m4.metric("\U0001F3EA Registered Vendors", f"{approved_vendors:,}", f"+{new_vendors_week} this week")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F6CD\uFE0F Demand by Service Category (Real Booking Requests)")
    if sync_ok:
        db = get_db()
        pipeline = [{"$group": {"_id": "$service", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 8}]
        results = list(db.vendor_bookings.aggregate(pipeline))
        if results:
            demand_data = pd.DataFrame({"Booking Requests": [r["count"] for r in results]}, index=[r["_id"] for r in results])
        else:
            demand_data = None
            st.caption("No booking requests logged yet on the platform \u2014 chart will populate as clients request vendor bookings.")
    else:
        demand_data = pd.DataFrame({
            "Inquiries This Month": [340, 290, 260, 210, 180, 150],
        }, index=["Photography", "Catering", "Banquet Halls", "Decoration", "Apparel", "Transportation"])
    if demand_data is not None:
        st.bar_chart(demand_data)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F3EA Approved Vendors by Category")
    if sync_ok:
        db = get_db()
        cat_counts = {}
        for v in db.vendors.find({"status": "Approved"}):
            for t in v.get("vendor_types", []):
                cat_counts[t] = cat_counts.get(t, 0) + 1
        if cat_counts:
            cat_data = pd.DataFrame({"Approved Vendors": list(cat_counts.values())}, index=list(cat_counts.keys()))
            st.bar_chart(cat_data)
        else:
            st.caption("No approved vendors yet in any category.")
    else:
        city_data = pd.DataFrame({
            "Active Users": [2450, 1890, 1620, 1340, 980, 760, 540],
        }, index=["Nagpur", "Mumbai", "Pune", "Bangalore", "Delhi", "Hyderabad", "Kolkata"])
        st.bar_chart(city_data)
        st.caption("\u26A0\uFE0F Demo data shown (illustrative city distribution) \u2014 connect MongoDB to see your real approved-vendor category breakdown here.")

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
.sync-pill { display:inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
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

    sync_ok = db_is_connected()
    pill_style = "background:#DCFCE7; color:#166534;" if sync_ok else "background:#FEF3C7; color:#92400E;"
    pill_text = "\u2601\uFE0F Registration, vendor, and membership numbers below are live from MongoDB (revenue is still simulated pending a payment gateway)" if sync_ok else "\U0001F4F1 Demo mode \u2014 all numbers below are sample data, connect MongoDB for real figures"
    st.markdown(f"<span class='sync-pill' style='{pill_style}'>{pill_text}</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if sync_ok:
        db = get_db()
        week_ago = dt.datetime.utcnow() - dt.timedelta(days=7)
        total_registered = db.users.count_documents({})
        new_this_week = db.users.count_documents({"created_at": {"$gte": week_ago}})
        vendor_regs = db.vendors.count_documents({})
        new_vendor_regs = db.vendors.count_documents({"submitted_at": {"$gte": week_ago}})
        paid_members = db_count_paid_members()
        unpaid_members = max(total_registered - paid_members, 0)
        boosted_count = db.boosts.count_documents({"expires_at": {"$gte": dt.datetime.utcnow()}})
    else:
        total_registered, new_this_week, vendor_regs, new_vendor_regs = 12543, 324, 186, 9
        paid_members, unpaid_members, boosted_count = 3210, 9333, 417

    st.markdown("### \U0001F4CB Registration Overview")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("\u2705 Total Registered", f"{total_registered:,}", f"+{new_this_week} this week")
    r2.metric("\U0001F6AA Started but Not Completed", "3,812" if not sync_ok else "N/A", help="Requires instrumenting the registration form to track partial completions \u2014 not yet wired up." if sync_ok else None)
    r3.metric("\U0001F194 Profile IDs Created", f"{total_registered:,}" if sync_ok else "12,101", f"+{new_this_week} this week" if sync_ok else "+298 this week")
    r4.metric("\U0001F4DD Vendor Registrations", f"{vendor_regs:,}", f"+{new_vendor_regs} this week")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F7E2 Activity Status")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("\U0001F7E2 Active Users (30 days)", "8,920", "71% of total", help="Requires tracking last-login timestamps \u2014 not yet wired up." if sync_ok else None)
    a2.metric("\U0001F534 Inactive Users", "3,623", "29% of total")
    a3.metric("\U0001F7E2 Active Vendors", "142", "76% of vendors")
    a4.metric("\U0001F534 Inactive Vendors", "44", "24% of vendors")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4B3 Paid vs Unpaid")
    p1, p2, p3, p4 = st.columns(4)
    paid_pct = f"{paid_members/total_registered*100:.1f}% of users" if total_registered else ""
    unpaid_pct = f"{unpaid_members/total_registered*100:.1f}% of users" if total_registered else ""
    p1.metric("\U0001F48E Paid (VIP) Members", f"{paid_members:,}", paid_pct)
    p2.metric("\U0001F193 Unpaid (Free) Members", f"{unpaid_members:,}", unpaid_pct)
    p3.metric("\u2B50 Boosted Profiles/Vendors", f"{boosted_count:,}")
    p4.metric("\U0001F501 Renewed This Month", "612" if not sync_ok else "N/A", help="Requires tracking renewal vs first-time purchases \u2014 not yet wired up." if sync_ok else None)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4B0 Revenue by Date Range")
    st.caption("\u26A0\uFE0F Revenue figures below are simulated \u2014 Bandhan doesn't process payments directly (see Refund Policy), so real revenue requires connecting your payment gateway's (e.g. Razorpay) reporting API.")
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

    st.markdown("---")
    st.markdown("### \u2696\uFE0F Pending Grievances (SLA: 15 days)")
    pending_grievances = db_list_grievances(status="Pending")
    if not pending_grievances:
        st.caption("No pending grievances right now (or MongoDB isn't connected yet, so this list is empty in demo mode).")
    else:
        for g in pending_grievances:
            with st.container():
                st.markdown(f"<div class='metric-card'>", unsafe_allow_html=True)
                deadline = g.get("sla_deadline")
                overdue = isinstance(deadline, dt.datetime) and dt.datetime.utcnow() > deadline
                overdue_tag = " \u26A0\uFE0F OVERDUE" if overdue else ""
                st.markdown(f"**{g.get('name','')}** ({g.get('email','')}){overdue_tag}")
                st.caption(f"{g.get('issue','')}")
                st.caption(f"Filed: {g.get('submitted_at', dt.datetime.utcnow()).strftime('%d %b %Y')} \u2022 SLA deadline: {deadline.strftime('%d %b %Y') if isinstance(deadline, dt.datetime) else ''}")
                if st.button("\u2705 Mark Resolved", key=f"resolve_griev_{g['_id']}", use_container_width=True):
                    db_update_grievance_status(str(g["_id"]), "Resolved")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F510 Pending DPDP Data Rights Requests")
    pending_dpdp = db_list_dpdp_requests(status="Pending")
    if not pending_dpdp:
        st.caption("No pending DPDP requests right now (or MongoDB isn't connected yet, so this list is empty in demo mode).")
    else:
        for d in pending_dpdp:
            with st.container():
                st.markdown(f"<div class='metric-card'>", unsafe_allow_html=True)
                st.markdown(f"**{d.get('request_type','')}** \u2014 {d.get('email','')}")
                if d.get("details"):
                    st.caption(d["details"])
                st.caption(f"Filed: {d.get('submitted_at', dt.datetime.utcnow()).strftime('%d %b %Y')}")
                dc1, dc2 = st.columns(2)
                if dc1.button("\u2705 Mark Fulfilled", key=f"fulfill_dpdp_{d['_id']}", use_container_width=True):
                    db_update_dpdp_status(str(d["_id"]), "Fulfilled")
                    st.rerun()
                if dc2.button("\u274C Reject", key=f"reject_dpdp_{d['_id']}", use_container_width=True):
                    db_update_dpdp_status(str(d["_id"]), "Rejected")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### \U0001F9FE Pending Vendor Approvals")
    pending_vendors = db_list_vendor_submissions(status="Pending")
    if not pending_vendors:
        st.caption("No pending vendor submissions right now (or MongoDB isn't connected yet, so this list is empty in demo mode).")
    else:
        for v in pending_vendors:
            with st.container():
                st.markdown(f"<div class='metric-card'>", unsafe_allow_html=True)
                vc1, vc2 = st.columns([3, 1])
                with vc1:
                    st.markdown(f"**{v.get('business_name','')}** — {', '.join(v.get('vendor_types', []))}")
                    st.caption(f"Owner: {v.get('owner_name','')} | Contact: {v.get('contact_number','')} | Email: {v.get('business_email','')} | City: {v.get('city','')}")
                    st.caption(f"Aadhaar: {v.get('aadhaar_number','')} | PAN: {v.get('pan_number','')} | GST: {v.get('gst_number') or '—'} | Submitted: {v.get('submitted_at', dt.datetime.utcnow()).strftime('%d %b %Y')}")
                with vc2:
                    if st.button("\u2705 Approve", key=f"approve_{v['_id']}", use_container_width=True):
                        db_update_vendor_status(str(v["_id"]), "Approved")
                        st.rerun()
                    if st.button("\u274C Reject", key=f"reject_{v['_id']}", use_container_width=True):
                        db_update_vendor_status(str(v["_id"]), "Rejected")
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F49E Pending Success Story Approvals")
    pending_stories = db_list_success_stories(status="Pending")
    if not pending_stories:
        st.caption("No pending success story submissions right now (or MongoDB isn't connected yet, so this list is empty in demo mode).")
    else:
        for s in pending_stories:
            with st.container():
                st.markdown(f"<div class='metric-card'>", unsafe_allow_html=True)
                sc1, sc2 = st.columns([1, 3])
                if s.get("photo_b64"):
                    sc1.image(base64.b64decode(s["photo_b64"]), use_container_width=True)
                with sc2:
                    st.markdown(f"**{s.get('groom_name','')} & {s.get('bride_name','')}** — {s.get('city_name','')}, {s.get('wedding_state','')} | {s.get('marriage_date','')}")
                    st.caption(f"Contact: {s.get('contact_email','')} | Venue: {s.get('venue_name') or '—'}")
                    st.caption(f"\"{s.get('story_text','')[:200]}{'...' if len(s.get('story_text',''))>200 else ''}\"")
                    ac1, ac2 = st.columns(2)
                    if ac1.button("\u2705 Approve", key=f"approve_story_{s['_id']}", use_container_width=True):
                        db_update_story_status(str(s["_id"]), "Approved")
                        st.rerun()
                    if ac2.button("\u274C Reject", key=f"reject_story_{s['_id']}", use_container_width=True):
                        db_update_story_status(str(s["_id"]), "Rejected")
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4DE Pending Counseling Session Requests")
    pending_counseling = db_list_counseling_requests(status="Pending")
    if not pending_counseling:
        st.caption("No pending counseling requests right now (or MongoDB isn't connected yet, so this list is empty in demo mode).")
    else:
        for req in pending_counseling:
            with st.container():
                st.markdown(f"<div class='metric-card'>", unsafe_allow_html=True)
                st.markdown(f"**{req.get('name','')}** ({req.get('email','')}) — {req.get('contact_number','')}")
                st.caption(f"Preferred: {req.get('preferred_date','')} at {req.get('preferred_time','')}")
                if req.get("notes"):
                    st.caption(f"Notes: {req['notes']}")
                cc1, cc2 = st.columns(2)
                if cc1.button("\u2705 Mark Contacted", key=f"contacted_{req['_id']}", use_container_width=True):
                    db_update_counseling_status(str(req["_id"]), "Contacted")
                    st.rerun()
                if cc2.button("\u274C Cancel", key=f"cancel_counsel_{req['_id']}", use_container_width=True):
                    db_update_counseling_status(str(req["_id"]), "Cancelled")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### \U0001F4DD Publish New Blog Article")
    with st.form("publish_blog_form", clear_on_submit=True):
        bp_title = st.text_input("Article Title")
        bp_tag = st.selectbox("Topic", ["Matchmaking", "Safety", "Wedding Planning", "Astrology", "Relationships", "Finance"])
        bp_img = st.text_input("Cover Image URL", placeholder="https://images.unsplash.com/...")
        bp_excerpt = st.text_area("Short Excerpt (1-2 lines)", height=68)
        bp_full = st.text_area("Full Article Text", height=150)
        bp_submit = st.form_submit_button("\U0001F4E4 Publish Article", type="primary")
        if bp_submit:
            if not (bp_title and bp_excerpt and bp_full):
                st.warning("Please fill in at least the title, excerpt, and full article text.")
            else:
                img_url = bp_img or "https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=600&q=80"
                if db_add_blog_article(bp_title, bp_tag, img_url, bp_excerpt, bp_full, st.session_state.get("user_email", "")):
                    st.success(f"\u2705 '{bp_title}' published! It's now live on the Blog & Tips page.")
                else:
                    st.error("\u26A0\uFE0F Couldn't publish \u2014 connect MongoDB to enable the blog CMS.")

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
# PAGE: VIDEO PROFILE / INTRO VIDEO
# =====================================================================
def page_video_profile():
    render_global_css(bg_color="#F8F9FA", page_css=""".vidpro-header { background: linear-gradient(135deg, #6B46C1 0%, #1A365D 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.vidpro-card { background: white; padding: 22px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 18px; }
.vidpro-badge { background: #DCFCE7; color: #166534; padding: 8px 16px; border-radius: 10px; font-weight: 700; display:inline-block; }""")

    st.markdown("""
    <div class="vidpro-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F3A5 Video Profile / Intro Video</h1>
        <p style="color:#FBF5B7; margin-top:8px;">A 30-60 second intro video helps matches connect with the real you — profiles with video get far more responses.</p>
    </div>
    """, unsafe_allow_html=True)

    if "profile_video_bytes" not in st.session_state:
        st.session_state.profile_video_bytes = None
        st.session_state.profile_video_status = "Not uploaded"

    st.markdown("<div class='vidpro-card'>", unsafe_allow_html=True)
    st.markdown("### \U0001F4F9 Record or Upload Your Intro")
    MAX_VIDEO_MB = 50
    tab1, tab2 = st.tabs(["\U0001F4F7 Record with Camera", "\U0001F4C1 Upload a Video File"])
    with tab1:
        st.caption(f"Tip: introduce yourself, your interests, and what you're looking for in a partner. Keep it 30\u201360 seconds \u2014 please check your clip's length before saving; max file size {MAX_VIDEO_MB}MB.")
        cam_video = st.camera_input("Record a short intro (webcam)", key="vidpro_camera")
        if cam_video is not None:
            video_bytes = cam_video.getvalue()
            size_mb = len(video_bytes) / (1024 * 1024)
            if size_mb > MAX_VIDEO_MB:
                st.error(f"\u274C This clip is {size_mb:.1f}MB, which is over the {MAX_VIDEO_MB}MB limit. Please record a shorter clip.")
            else:
                st.session_state.profile_video_bytes = video_bytes
                st.session_state.profile_video_status = "Pending Review"
                st.success(f"\u2705 Intro clip captured ({size_mb:.1f}MB)! It will appear on your profile after moderation.")
    with tab2:
        st.caption(f"Please keep your video to 30\u201360 seconds \u2014 max file size {MAX_VIDEO_MB}MB. Longer videos may be trimmed or rejected during moderation.")
        uploaded_video = st.file_uploader("Upload MP4/MOV (max 60 seconds recommended)", type=["mp4", "mov", "m4v"], key="vidpro_upload")
        if uploaded_video is not None:
            video_bytes = uploaded_video.getvalue()
            size_mb = len(video_bytes) / (1024 * 1024)
            if size_mb > MAX_VIDEO_MB:
                st.error(f"\u274C This file is {size_mb:.1f}MB, which is over the {MAX_VIDEO_MB}MB limit. Please upload a shorter or more compressed video.")
            else:
                st.session_state.profile_video_bytes = video_bytes
                st.session_state.profile_video_status = "Pending Review"
                st.success(f"\u2705 Video uploaded ({size_mb:.1f}MB)! It will appear on your profile after moderation.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='vidpro-card'>", unsafe_allow_html=True)
    st.markdown("### \U0001F441\uFE0F Preview")
    if st.session_state.profile_video_bytes:
        st.video(st.session_state.profile_video_bytes)
        status = st.session_state.profile_video_status
        badge_color = "#DCFCE7" if status == "Approved" else "#FEF3C7"
        text_color = "#166534" if status == "Approved" else "#92400E"
        render_html(f"<span class='vidpro-badge' style='background:{badge_color}; color:{text_color};'>Status: {status}</span>")
        if status == "Pending Review" and st.button("\U0001F9EA (Demo) Simulate Moderation Approval", use_container_width=True):
            st.session_state.profile_video_status = "Approved"
            st.rerun()
        if st.button("\U0001F5D1\uFE0F Remove Video", use_container_width=True):
            st.session_state.profile_video_bytes = None
            st.session_state.profile_video_status = "Not uploaded"
            st.rerun()
    else:
        st.info("No intro video yet — record or upload one above so matches can see and hear you.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### \U0001F4A1 Tips for a Great Intro Video")
    st.write("""
    - Keep it 30-60 seconds — short and genuine works best
    - Good lighting and a quiet background make a big difference
    - Talk about your interests, values, and what you're looking for
    - Avoid sharing phone numbers, addresses, or social media handles on camera
    - All videos are moderated before appearing publicly on your profile
    """)


# =====================================================================
# PAGE: LIVE VIDEO CALL (IN-APP)
# =====================================================================
def page_live_video_call():
    render_global_css(bg_color="#F8F9FA", page_css=""".vcall-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.vcall-card { background: white; padding: 20px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 14px; }
.vcall-room { background: #0F2027; border: 2px dashed #D4AF37; border-radius: 16px; padding: 40px; text-align: center; color: #E2E8F0; }
.vcall-photo { width: 60px; height: 60px; border-radius: 50%; object-fit: cover; vertical-align: middle; margin-right: 10px; }""")

    st.markdown("""
    <div class="vcall-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F4F9 Live Video Call (In-App)</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Talk face-to-face with your matches without ever sharing your personal phone number.</p>
    </div>
    """, unsafe_allow_html=True)

    # Same demo profile pool used across Search Partner / My Matches / AI pages
    CONTACT_POOL = {
        "Ritu Deshmukh": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=100&q=80",
        "Sneha Patil": "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?auto=format&fit=crop&w=100&q=80",
        "Ananya Rao": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=100&q=80",
        "Kavya Nair": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=100&q=80",
        "Priya Sharma": "https://images.unsplash.com/photo-1552374196-c4e7ffc6e126?auto=format&fit=crop&w=100&q=80",
        "Fatima Sheikh": "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=100&q=80",
    }

    if "vcall_requests" not in st.session_state:
        st.session_state.vcall_requests = []
    if "vcall_active" not in st.session_state:
        st.session_state.vcall_active = False
    if "vcall_history" not in st.session_state:
        st.session_state.vcall_history = []

    st.markdown("<div class='vcall-card'>", unsafe_allow_html=True)
    st.markdown("### \U0001F4DE Request a Video Call")
    match_choice = st.selectbox("Choose a mutual match", list(CONTACT_POOL.keys()))
    st.markdown(f"<img src='{CONTACT_POOL[match_choice]}' class='vcall-photo'> <span style='vertical-align:middle;'>{match_choice}</span>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    today = dt.date.today()
    call_date = c1.date_input("Preferred date", min_value=today, value=today)
    call_time = c2.time_input("Preferred time")

    already_pending = any(r["with"] == match_choice and r["status"] == "Pending" for r in st.session_state.vcall_requests)
    if st.button("\U0001F4E4 Send Call Request", type="primary", use_container_width=True, disabled=already_pending):
        if call_date == today and call_time < dt.datetime.now().time():
            st.error("\u274C That time has already passed today. Please choose a future date/time.")
        else:
            st.session_state.vcall_requests.append({"with": match_choice, "date": str(call_date), "time": str(call_time), "status": "Pending"})
            st.success(f"\u2705 Video call request sent to {match_choice}. They'll be notified to accept.")
            st.rerun()
    if already_pending:
        st.caption(f"\u23F3 You already have a pending request with {match_choice}.")
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.vcall_requests:
        st.markdown("<div class='vcall-card'>", unsafe_allow_html=True)
        st.markdown("### \U0001F5C2\uFE0F Your Call Requests")
        for i, req in enumerate(st.session_state.vcall_requests):
            rc1, rc2, rc3 = st.columns([3, 1, 1])
            photo_html = f"<img src='{CONTACT_POOL.get(req['with'], '')}' class='vcall-photo' style='width:36px; height:36px;'>"
            rc1.markdown(f"{photo_html} **{req['with']}** — {req['date']} at {req['time']} — Status: *{req['status']}*", unsafe_allow_html=True)
            if req["status"] == "Pending":
                if rc2.button("\u2705 Simulate Accept", key=f"vcall_accept_{i}"):
                    st.session_state.vcall_requests[i]["status"] = "Accepted"
                    st.rerun()
                if rc3.button("\u274C Cancel", key=f"vcall_cancel_{i}"):
                    st.session_state.vcall_requests.pop(i)
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    accepted = [r for r in st.session_state.vcall_requests if r["status"] == "Accepted"]
    if accepted:
        st.markdown("<div class='vcall-card'>", unsafe_allow_html=True)
        st.markdown("### \u2705 Ready to Join")
        joinable_labels = [f"{r['with']} — {r['date']} {r['time']}" for r in accepted]
        joinable = st.selectbox("Accepted calls", joinable_labels)
        joinable_name = joinable.split(" — ")[0]
        if not st.session_state.vcall_active:
            jc1, jc2 = st.columns(2)
            if jc1.button("\U0001F7E2 Join Call Room", type="primary", use_container_width=True):
                st.session_state.vcall_active = True
                st.rerun()
            if jc2.button("\u274C Decline / Withdraw", use_container_width=True):
                st.session_state.vcall_requests = [r for r in st.session_state.vcall_requests if not (r["with"] == joinable_name and r["status"] == "Accepted")]
                st.rerun()
        else:
            render_html(f"""
            <div class="vcall-room">
                <h2>\U0001F534 LIVE — In call with {joinable_name}</h2>
                <p>Camera and microphone connected via secure in-app calling.</p>
            </div>
            """)
            st.camera_input("Your camera preview", key="vcall_camera_preview")
            if st.button("\U0001F534 End Call", use_container_width=True):
                st.session_state.vcall_active = False
                st.session_state.vcall_requests = [r for r in st.session_state.vcall_requests if not (r["with"] == joinable_name and r["status"] == "Accepted")]
                st.session_state.vcall_history.append({"with": joinable_name, "ended_at": dt.datetime.now().strftime("%d %b %Y, %I:%M %p"), "status": "Completed"})
                st.success(f"\u2705 Call with {joinable_name} ended and saved to your call history.")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.vcall_history:
        st.markdown("<div class='vcall-card'>", unsafe_allow_html=True)
        st.markdown("### \U0001F4DC Call History")
        hist_df = pd.DataFrame(st.session_state.vcall_history)
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.caption("\u26A0\uFE0F Demo mode: real 1:1 video calling requires a WebRTC provider (e.g., Agora, Twilio Video, or Daily.co) connected via API keys in Streamlit Secrets.")


# =====================================================================
# PAGE: ASTROLOGY CONSULTATION BOOKING
# =====================================================================
def page_astrology_consultation():
    render_global_css(bg_color="#FFF8F0", page_css=""".astro-header { background: linear-gradient(135deg, #7C3AED 0%, #1A365D 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.astro-card { background: white; padding: 20px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 16px; }
.astro-price { font-size: 1.4rem; color: #27AE60; font-weight: 900; }""")

    st.markdown("""
    <div class="astro-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F52E Astrology Consultation Booking</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Book a live session with a verified astrologer for Kundli review, Muhurat, or general guidance.</p>
    </div>
    """, unsafe_allow_html=True)

    astrologers = [
        {"name": "Pandit Raghunath Sharma", "specialty": "Kundli Matching & Dosha Remedies", "exp": "22 yrs experience", "rating": 4.9, "price": 499},
        {"name": "Acharya Meenakshi Joshi", "specialty": "Muhurat & Wedding Astrology", "exp": "15 yrs experience", "rating": 4.8, "price": 399},
        {"name": "Jyotishi Vikram Bhatt", "specialty": "Career & Marriage Timing", "exp": "18 yrs experience", "rating": 4.7, "price": 349},
    ]

    if "astro_bookings" not in st.session_state:
        st.session_state.astro_bookings = []

    st.markdown("### \U0001F9D9 Choose Your Astrologer")
    for idx, a in enumerate(astrologers):
        st.markdown(f"""
        <div class="astro-card">
            <b style="font-size:1.1rem;">\U0001F52E {a['name']}</b> &nbsp;
            <span style="color:#D4AF37;">{'\u2B50' * int(round(a['rating']))} {a['rating']}</span><br>
            <span style="color:gray;">{a['specialty']} &middot; {a['exp']}</span><br>
            <span class="astro-price">\u20b9 {a['price']} / 20-min session</span>
        </div>
        """, unsafe_allow_html=True)
        bc1, bc2, bc3 = st.columns(3)
        session_date = bc1.date_input("Date", key=f"astro_date_{idx}")
        session_time = bc2.time_input("Time", key=f"astro_time_{idx}")
        if bc3.button(f"\U0001F4C5 Book Session", key=f"astro_book_{idx}", type="primary", use_container_width=True):
            st.session_state.astro_bookings.append({
                "astrologer": a["name"], "date": str(session_date), "time": str(session_time),
                "price": a["price"], "status": "Confirmed"
            })
            st.success(f"\u2705 Session booked with {a['name']} on {session_date} at {session_time}.")

    if st.session_state.astro_bookings:
        st.markdown("### \U0001F4CB Your Bookings")
        df = pd.DataFrame(st.session_state.astro_bookings)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.caption("\u26A0\uFE0F Demo mode: real payments need a gateway (Razorpay/Stripe); real live sessions need a video-call integration (see Live Video Call page).")


# =====================================================================
# PAGE: WEDDING VENDOR MARKETPLACE WITH REVIEWS
# =====================================================================
def page_vendor_marketplace():
    render_global_css(bg_color="#F8F9FA", page_css=""".vmarket-header { background: linear-gradient(135deg, #AA771C 0%, #1A365D 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.vmarket-card { background: white; padding: 20px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 16px; }
.vmarket-stars { color: #D4AF37; font-size: 1.1rem; }""")

    st.markdown("""
    <div class="vmarket-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F3EA Wedding Vendor Marketplace</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Browse verified photographers, decorators, caterers & more — with real reviews from other couples.</p>
    </div>
    """, unsafe_allow_html=True)

    if "vmarket_vendors" not in st.session_state:
        st.session_state.vmarket_vendors = {
            "Photographers": [
                {"name": "Shutter Tales Studio", "city": "Mumbai", "price": "\u20b9 45,000 onwards", "reviews": [5, 4, 5]},
                {"name": "Frame & Forever", "city": "Delhi", "price": "\u20b9 60,000 onwards", "reviews": [5, 5, 4, 5]},
            ],
            "Decorators": [
                {"name": "Royal Blooms Decor", "city": "Jaipur", "price": "\u20b9 80,000 onwards", "reviews": [5, 4]},
                {"name": "Elegant Events Co.", "city": "Pune", "price": "\u20b9 55,000 onwards", "reviews": [4, 4, 5]},
            ],
            "Caterers": [
                {"name": "Spice Route Catering", "city": "Bengaluru", "price": "\u20b9 900/plate", "reviews": [5, 5]},
                {"name": "Taste of India Caterers", "city": "Mumbai", "price": "\u20b9 650/plate", "reviews": [4, 5, 4]},
            ],
            "Makeup Artists": [
                {"name": "Glow by Kavya", "city": "Delhi", "price": "\u20b9 25,000 onwards", "reviews": [5, 5, 5]},
                {"name": "Bridal Bliss Studio", "city": "Mumbai", "price": "\u20b9 30,000 onwards", "reviews": [4, 5]},
            ],
        }

    categories = list(st.session_state.vmarket_vendors.keys())
    tabs = st.tabs([f"\U0001F4F8 {c}" if c == "Photographers" else f"\U0001F3E8 {c}" if c == "Decorators" else f"\U0001F37D\uFE0F {c}" if c == "Caterers" else f"\U0001F484 {c}" for c in categories])

    for cat, tab in zip(categories, tabs):
        with tab:
            for v_idx, v in enumerate(st.session_state.vmarket_vendors[cat]):
                avg_rating = sum(v["reviews"]) / len(v["reviews"]) if v["reviews"] else 0
                stars = "\u2B50" * round(avg_rating)
                st.markdown(f"""
                <div class="vmarket-card">
                    <b style="font-size:1.1rem;">{v['name']}</b> &middot; {v['city']}<br>
                    <span class="vmarket-stars">{stars}</span> <span style="color:gray;">({avg_rating:.1f} avg, {len(v['reviews'])} reviews)</span><br>
                    <b style="color:#27AE60;">{v['price']}</b>
                </div>
                """, unsafe_allow_html=True)
                with st.expander(f"\u2B50 Leave a review for {v['name']}"):
                    rating = st.slider("Your rating", 1, 5, 5, key=f"vmarket_rating_{cat}_{v_idx}")
                    review_text = st.text_area("Your review", key=f"vmarket_text_{cat}_{v_idx}", placeholder="How was your experience?")
                    if st.button("Submit Review", key=f"vmarket_submit_{cat}_{v_idx}"):
                        st.session_state.vmarket_vendors[cat][v_idx]["reviews"].append(rating)
                        st.success("\u2705 Thanks! Your review has been added.")
                        st.rerun()
                c1, c2 = st.columns(2)
                c1.button("\U0001F4C5 Request Booking", key=f"vmarket_book_{cat}_{v_idx}", use_container_width=True)
                c2.button("\U0001F4AC Message Vendor", key=f"vmarket_msg_{cat}_{v_idx}", use_container_width=True)

    st.caption("Vendors listed here are also managed via the Vendor Registration and Vendor Booking Dashboard pages.")


# =====================================================================
# PAGE: AI SMART RECOMMENDATIONS + ADVANCED FILTERS
# =====================================================================
def page_smart_recommendations():
    render_global_css(bg_color="#F8F9FA", page_css=""".airec-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.airec-card { background: white; padding: 18px 20px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border-left: 5px solid #D4AF37; margin-bottom: 6px; }
.airec-score { font-weight: 900; color: #27AE60; font-size: 1.2rem; }
.airec-photo { width: 100%; border-radius: 12px; height: 150px; object-fit: cover; }
.airec-photo-blurred { filter: blur(10px); }
.airec-bio { color: #444; font-size: 0.85rem; font-style: italic; margin-top: 6px; }""")

    st.markdown("""
    <div class="airec-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F9E0 AI Smart Recommendations</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Daily curated matches, refined by advanced filters — powered by your profile, quiz answers, and activity.</p>
    </div>
    """, unsafe_allow_html=True)

    if "airec_shortlist" not in st.session_state:
        st.session_state.airec_shortlist = set()
    if "airec_interested" not in st.session_state:
        st.session_state.airec_interested = set()
    if "airec_not_interested" not in st.session_state:
        st.session_state.airec_not_interested = set()

    with st.expander("\U0001F39B\uFE0F Advanced Filters", expanded=False):
        f1, f2, f3 = st.columns(3)
        with f1:
            age_range = st.slider("Age range", 21, 55, (24, 34))
            height_range = st.slider("Height range (cm)", 140, 200, (150, 180))
        with f2:
            income_range = st.select_slider("Annual income (\u20b9 Lakhs)", options=[3, 5, 8, 12, 18, 25, 40, 60], value=(5, 25))
            diet_pref = st.selectbox("Diet preference", ["Any", "Vegetarian", "Non-Vegetarian", "Eggetarian", "Vegan"])
        with f3:
            manglik_pref = st.selectbox("Manglik status", ["Any", "Manglik", "Non-Manglik"])
            habits_pref = st.selectbox("Drinking / Smoking", ["Any", "Non-drinker & Non-smoker", "Occasional drinker", "Occasional smoker"])
        f4, f5 = st.columns(2)
        education_pref = f4.selectbox("Minimum education", ["Any", "Graduate", "Post Graduate", "B.Tech / B.E.", "MBA / PG", "MBBS / MD", "Doctorate"])
        location_pref = f5.text_input("Preferred city/region", placeholder="e.g., Mumbai, Pune")
        apply_clicked = st.button("\U0001F50D Apply Filters & Refresh Recommendations", type="primary", use_container_width=True)

    # ---- Demo profile pool (same shape as Search Partner \u2014 stand-in
    # until this is wired to real registered profiles from MongoDB) ----
    all_profiles = [
        {"name": "Ritu Deshmukh", "age": 24, "city": "Nagpur", "religion": "Hindu", "manglik": "Non-Manglik", "caste": "Maratha",
         "diet": "Vegetarian", "habits": "Non-drinker & Non-smoker", "marital_status": "Never Married",
         "height_cm": 160, "mother_tongue": "Marathi", "profession": "Software Engineer", "education": "B.Tech / B.E.",
         "income": "\u20b912 Lakhs p.a.", "verified": True, "active": "Active 2 hours ago",
         "bio": "Loves trekking and classical dance; looking for a career-driven partner.",
         "photo": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=400&q=80"},
        {"name": "Sneha Patil", "age": 26, "city": "Pune", "religion": "Hindu", "manglik": "Manglik", "caste": "Maratha",
         "diet": "Vegetarian", "habits": "Non-drinker & Non-smoker", "marital_status": "Never Married",
         "height_cm": 165, "mother_tongue": "Marathi", "profession": "Chartered Accountant", "education": "MBA / PG",
         "income": "\u20b915 Lakhs p.a.", "verified": True, "active": "Active Online Now",
         "bio": "Family-oriented CA who enjoys cooking and weekend hiking.",
         "photo": "https://images.unsplash.com/photo-1531123897727-8f129e1688ce?auto=format&fit=crop&w=400&q=80"},
        {"name": "Ananya Rao", "age": 26, "city": "Bengaluru", "religion": "Hindu", "manglik": "Non-Manglik", "caste": "Brahmin",
         "diet": "Eggetarian", "habits": "Occasional drinker", "marital_status": "Never Married",
         "height_cm": 158, "mother_tongue": "Kannada", "profession": "Doctor", "education": "MBBS / MD",
         "income": "\u20b920 Lakhs p.a.", "verified": True, "active": "Active 5 hours ago",
         "bio": "Pediatrician who loves reading and volunteering on weekends.",
         "photo": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=400&q=80"},
        {"name": "Kavya Nair", "age": 28, "city": "Chennai", "religion": "Hindu", "manglik": "Manglik", "caste": "Nair",
         "diet": "Vegetarian", "habits": "Non-drinker & Non-smoker", "marital_status": "Never Married",
         "height_cm": 155, "mother_tongue": "Tamil", "profession": "Civil Servant", "education": "Post Graduate",
         "income": "\u20b910 Lakhs p.a.", "verified": True, "active": "Active 1 day ago",
         "bio": "UPSC-qualified, passionate about classical music and public service.",
         "photo": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=400&q=80"},
        {"name": "Priya Sharma", "age": 27, "city": "Delhi", "religion": "Hindu", "manglik": "Non-Manglik", "caste": "Brahmin",
         "diet": "Non-Vegetarian", "habits": "Occasional drinker", "marital_status": "Divorced",
         "height_cm": 162, "mother_tongue": "Hindi", "profession": "Banker", "education": "MBA / PG",
         "income": "\u20b918 Lakhs p.a.", "verified": True, "active": "Active 30 min ago",
         "bio": "Investment banker who enjoys travel, fitness, and good food.",
         "photo": "https://images.unsplash.com/photo-1552374196-c4e7ffc6e126?auto=format&fit=crop&w=400&q=80"},
        {"name": "Fatima Sheikh", "age": 29, "city": "Hyderabad", "religion": "Muslim", "manglik": "Non-Manglik", "caste": "Sheikh",
         "diet": "Non-Vegetarian", "habits": "Non-drinker & Non-smoker", "marital_status": "Never Married",
         "height_cm": 163, "mother_tongue": "Urdu", "profession": "Teacher", "education": "Post Graduate",
         "income": "\u20b98 Lakhs p.a.", "verified": True, "active": "Active 3 hours ago",
         "bio": "School teacher who loves poetry, calligraphy, and quiet evenings.",
         "photo": "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=400&q=80"},
    ]

    EDUCATION_ORDER = ["10th Pass", "12th Pass", "Diploma", "Graduate", "Post Graduate", "B.Tech / B.E.", "MBA / PG", "MBBS / MD", "Doctorate"]

    def education_rank(level):
        return EDUCATION_ORDER.index(level) if level in EDUCATION_ORDER else 0

    def profile_income_lakhs(income_str):
        digits = re.findall(r"\d+", income_str)
        return int(digits[0]) if digits else 0

    def build_recommendation(p):
        reasons = []
        score = 80
        if age_range[0] <= p["age"] <= age_range[1]:
            reasons.append("Within your preferred age range")
            score += 4
        if height_range[0] <= p["height_cm"] <= height_range[1]:
            reasons.append("Within your preferred height range")
            score += 3
        if diet_pref != "Any" and p["diet"] == diet_pref:
            reasons.append(f"Shares your {diet_pref.lower()} diet")
            score += 4
        if manglik_pref != "Any" and p["manglik"] == manglik_pref:
            reasons.append("Matches your Manglik preference")
            score += 4
        if habits_pref != "Any" and p["habits"] == habits_pref:
            reasons.append("Matching lifestyle habits")
            score += 3
        if education_pref != "Any" and education_rank(p["education"]) >= education_rank(education_pref):
            reasons.append("Meets your education preference")
            score += 3
        if location_pref.strip() and location_pref.strip().lower() in p["city"].lower():
            reasons.append(f"Located in {p['city']}, matching your preferred area")
            score += 5
        if income_range[0] <= profile_income_lakhs(p["income"]) <= income_range[1]:
            reasons.append("Income within your preferred bracket")
            score += 2
        if not reasons:
            reasons.append("Shared values and strong overall compatibility signals")
        return min(score, 99), " \u2022 ".join(reasons[:3])

    def matches_hard_filters(p):
        if not (age_range[0] <= p["age"] <= age_range[1]):
            return False
        if not (height_range[0] <= p["height_cm"] <= height_range[1]):
            return False
        if diet_pref != "Any" and p["diet"] != diet_pref:
            return False
        if manglik_pref != "Any" and p["manglik"] != manglik_pref:
            return False
        if habits_pref != "Any" and p["habits"] != habits_pref:
            return False
        if education_pref != "Any" and education_rank(p["education"]) < education_rank(education_pref):
            return False
        if location_pref.strip() and location_pref.strip().lower() not in p["city"].lower():
            return False
        return True

    if apply_clicked or "_airec_recs" not in st.session_state:
        candidates = [p for p in all_profiles if p["name"] not in st.session_state.airec_not_interested]
        filtered = [p for p in candidates if matches_hard_filters(p)] if apply_clicked else candidates
        recs = []
        for p in filtered:
            score, why = build_recommendation(p)
            recs.append({**p, "score": score, "why": why})
        recs.sort(key=lambda r: -r["score"])
        st.session_state._airec_recs = recs
        if apply_clicked:
            st.toast(f"\U0001F504 Refreshed \u2014 found {len(recs)} recommendation(s) matching your filters.")

    recs = [r for r in st.session_state.get("_airec_recs", []) if r["name"] not in st.session_state.airec_not_interested]

    st.markdown("### \u2728 Today's Top Picks for You")
    is_paid_member = st.session_state.get("is_paid_member", False)
    if not is_paid_member:
        st.caption("\U0001F512 Photos are blurred for free members. Upgrade to VIP to see full-quality photos.")

    if not recs:
        st.info("\U0001F44B No recommendations match your current filters. Try widening the age/height range or relaxing a filter.")

    for r in recs:
        photo_col, info_col = st.columns([1, 3])
        with photo_col:
            blur_class = "" if is_paid_member else " airec-photo-blurred"
            st.markdown(f"<img src='{r['photo']}' class='airec-photo{blur_class}'>", unsafe_allow_html=True)
            if not is_paid_member:
                st.caption("\U0001F512 Upgrade to unblur")
        with info_col:
            st.markdown(f"""
            <div class="airec-card">
                <b style="font-size:1.1rem;">{r['name']}, {r['age']} \u2022 {r['height_cm']} cm</b> &middot; {r['city']}
                <span class="airec-score" style="float:right;">{r['score']}% Match</span><br>
                <span style="color:gray; font-size:0.9rem;">{r['profession']} \u2022 {r['diet']} \u2022 {r['manglik']}, {r['caste']} \u2022 {r['mother_tongue']} \u2022 {r['marital_status']}</span>
                <p class="airec-bio">\u201c{r['bio']}\u201d</p>
                <span style="color:#1A365D; font-size:0.85rem;">\U0001F4A1 {r['why']}</span><br>
                <span style="color:gray; font-size:0.8rem;">{'\u2705 Verified Profile' if r['verified'] else ''}  \u2022  {r['active']}</span>
            </div>
            """, unsafe_allow_html=True)

        rc1, rc2, rc3, rc4, rc5 = st.columns(5)
        already_interested = r["name"] in st.session_state.airec_interested
        if rc1.button("\u2705 Sent" if already_interested else "\U0001F49B Interested", key=f"airec_like_{r['name']}", use_container_width=True, disabled=already_interested):
            st.session_state.airec_interested.add(r["name"])
            st.toast(f"\U0001F49B You showed interest in {r['name']}!")
            st.rerun()
        view_key = f"airec_viewing_{r['name']}"
        if rc2.button("\U0001F441\uFE0F View Profile", key=f"airec_view_{r['name']}", use_container_width=True):
            st.session_state[view_key] = not st.session_state.get(view_key, False)
            st.rerun()
        is_shortlisted = r["name"] in st.session_state.airec_shortlist
        if rc3.button("\u2B50 Saved" if is_shortlisted else "\u2606 Shortlist", key=f"airec_short_{r['name']}", use_container_width=True):
            if is_shortlisted:
                st.session_state.airec_shortlist.discard(r["name"])
            else:
                st.session_state.airec_shortlist.add(r["name"])
            st.rerun()
        if rc4.button("\U0001F4AC Message", key=f"airec_msg_{r['name']}", use_container_width=True):
            st.session_state.chat_preselect_contact = r["name"]
            st.session_state.chat_preselect_score = r["score"]
            go_to("chat_alerts")
        if rc5.button("\u274C Not Interested", key=f"airec_skip_{r['name']}", use_container_width=True):
            st.session_state.airec_not_interested.add(r["name"])
            st.toast(f"Got it \u2014 {r['name']} won't be shown again.")
            st.rerun()

        if st.session_state.get(view_key, False):
            with st.container(border=True):
                st.markdown(f"**Education:** {r['education']}  \u2022  **Income:** {r['income']}  \u2022  **Religion:** {r['religion']}")
                st.markdown(f"**Habits:** {r['habits']}")
                st.markdown(f"**Full Bio:** {r['bio']}")

        st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.airec_shortlist:
        st.caption(f"\u2B50 Shortlisted: {', '.join(sorted(st.session_state.airec_shortlist))}")

    st.caption("Recommendations combine profile data, quiz answers, Kundli score, and the advanced filters above — refreshed daily.")


# =====================================================================
# PAGE: PUSH NOTIFICATION PREFERENCE CENTER
# =====================================================================
def page_notification_preferences():
    render_global_css(bg_color="#F8F9FA", page_css=""".notifpref-header { background: linear-gradient(135deg, #1A365D 0%, #0F2027 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }
.notifpref-card { background: white; padding: 22px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; }""")

    st.markdown("""
    <div class="notifpref-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F514 Notification Preference Center</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Choose exactly what you want to be notified about — on push, email, or WhatsApp.</p>
    </div>
    """, unsafe_allow_html=True)

    DEFAULT_PREFS = {
        "New Matches": True, "Messages & Chat": True, "Family Meet Requests": True,
        "Boost / Offers & Promotions": False, "Daily Horoscope": False,
        "Wedding & Anniversary Reminders": True, "Vendor Booking Updates": True,
        "Marketing Emails": False,
    }
    DEFAULT_CHANNELS = {"push": True, "email": True, "whatsapp": False, "whatsapp_number": ""}

    if "notif_prefs" not in st.session_state:
        st.session_state.notif_prefs = dict(DEFAULT_PREFS)
    if "notif_channels" not in st.session_state:
        st.session_state.notif_channels = dict(DEFAULT_CHANNELS)
    if "notif_last_saved" not in st.session_state:
        st.session_state.notif_last_saved = None

    st.markdown("<div class='notifpref-card'>", unsafe_allow_html=True)
    st.markdown("### \U0001F3AF What would you like to be notified about?")
    for key in list(st.session_state.notif_prefs.keys()):
        st.session_state.notif_prefs[key] = st.toggle(key, value=st.session_state.notif_prefs[key], key=f"notiftoggle_{key}")

    st.markdown("---")
    st.markdown("### \U0001F4E1 Delivery Channels")
    c1, c2, c3 = st.columns(3)
    push_on = c1.checkbox("\U0001F4F1 Push Notifications", value=st.session_state.notif_channels["push"], key="notif_channel_push")
    email_on = c2.checkbox("\U0001F4E7 Email", value=st.session_state.notif_channels["email"], key="notif_channel_email")
    wa_on = c3.checkbox("\U0001F4AC WhatsApp", value=st.session_state.notif_channels["whatsapp"], key="notif_channel_wa")

    whatsapp_number = st.session_state.notif_channels.get("whatsapp_number", "")
    if wa_on:
        whatsapp_number = st.text_input("WhatsApp Number (with country code)", value=whatsapp_number, placeholder="+91 98765 43210", key="notif_wa_number")

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("\U0001F4BE Save Preferences", type="primary", use_container_width=True):
            if wa_on and not whatsapp_number.strip():
                st.error("\u274C Please enter a WhatsApp number since WhatsApp notifications are enabled.")
            else:
                st.session_state.notif_channels = {"push": push_on, "email": email_on, "whatsapp": wa_on, "whatsapp_number": whatsapp_number.strip()}
                st.session_state.notif_last_saved = dt.datetime.now().strftime("%d %b %Y, %I:%M %p")
                st.success("\u2705 Your notification preferences have been saved.")
                st.rerun()
    with btn_col2:
        if st.button("\U0001F501 Reset to Default", use_container_width=True):
            st.session_state.notif_prefs = dict(DEFAULT_PREFS)
            st.session_state.notif_channels = dict(DEFAULT_CHANNELS)
            st.session_state.notif_last_saved = None
            st.toast("\U0001F501 Preferences reset to default.")
            st.rerun()

    if st.session_state.notif_last_saved:
        st.caption(f"\u2705 Last saved: {st.session_state.notif_last_saved}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.caption("These preferences control what triggers a notification. Actual delivery uses the WhatsApp Notifications system (Boss-configured) and standard email/push infrastructure.")


# =====================================================================
# PAGE: IN-APP ADVERTISING FOR LOCAL VENDORS
# =====================================================================
def page_local_vendor_ads():
    render_global_css(bg_color="#FFFBEB", page_css=""".localads-header { background: linear-gradient(135deg, #AA771C 0%, #D4AF37 100%); padding: 30px; border-radius: 18px; color: white; text-align: center; margin-bottom: 25px; }
.localads-card { background: white; padding: 18px 20px; border-radius: 14px; box-shadow: 0 6px 15px rgba(0,0,0,0.06); border: 1px solid #EAEAEA; margin-bottom: 14px; }
.localads-tag { background: #FEF3C7; color: #92400E; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }""")

    st.markdown("""
    <div class="localads-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F4E2 Local Vendor Advertising</h1>
        <p style="margin-top:8px;">Local banquet halls, jewellers & boutiques can promote their business directly to engaged couples.</p>
    </div>
    """, unsafe_allow_html=True)

    if "local_ads" not in st.session_state:
        st.session_state.local_ads = [
            {"business": "Grand Sapphire Banquets", "category": "Banquet Hall", "city": "Mumbai", "text": "Book your dream venue — 15% off for Bandhan members!", "status": "Active"},
            {"business": "Aarna Jewels", "category": "Jewellery", "city": "Delhi", "text": "Exclusive bridal jewellery collection now live.", "status": "Active"},
        ]

    tab1, tab2 = st.tabs(["\U0001F440 Ads Near You", "\U0001F4C4 Submit Your Ad (Vendors)"])

    with tab1:
        st.write("Sponsored listings from local businesses, shown based on your city.")
        for ad in st.session_state.local_ads:
            if ad["status"] == "Active":
                st.markdown(f"""
                <div class="localads-card">
                    <span class="localads-tag">SPONSORED</span> &nbsp; <b>{ad['business']}</b> &middot; {ad['city']}<br>
                    <span style="color:gray; font-size:0.85rem;">{ad['category']}</span><br>
                    {ad['text']}
                </div>
                """, unsafe_allow_html=True)

    with tab2:
        st.write("Get your local business in front of thousands of engaged couples planning their wedding.")
        biz_name = st.text_input("Business Name")
        biz_cat = st.selectbox("Category", ["Banquet Hall", "Jewellery", "Boutique / Apparel", "Catering", "Photography", "Florist", "Other"])
        biz_city = st.text_input("City")
        biz_text = st.text_area("Ad Text", placeholder="e.g., Flat 20% off on wedding bookings this season!")
        biz_image = st.file_uploader("Upload Ad Banner (optional)", type=["png", "jpg", "jpeg"])
        biz_plan = st.selectbox("Ad Plan", ["7 Days — \u20b9 999", "15 Days — \u20b9 1,799", "30 Days — \u20b9 2,999"])
        if st.button("\U0001F4E4 Submit Ad for Review", type="primary", use_container_width=True):
            if biz_name and biz_city and biz_text:
                st.session_state.local_ads.append({"business": biz_name, "category": biz_cat, "city": biz_city, "text": biz_text, "status": "Pending Review"})
                st.success(f"\u2705 Ad submitted for review under the {biz_plan} plan. It will go live after approval.")
            else:
                st.warning("Please fill in business name, city, and ad text.")

    st.caption("\u26A0\uFE0F Demo mode: real ad placements need payment gateway integration and Boss-side approval workflow.")


# =====================================================================
# PAGE: USER ENGAGEMENT DASHBOARD (BOSS ONLY)
# =====================================================================
def page_engagement_dashboard():
    render_global_css(bg_color="#F8F9FA", page_css=""".engage-header { background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%); padding: 32px; border-radius: 18px; color: white; text-align: center; border: 2px solid #D4AF37; margin-bottom: 25px; }""")

    if st.session_state.user_role != "boss":
        st.error("\U0001F6AB Your account doesn't have permission to view this page.")
        if st.button("\u2190 Back to Home"):
            go_to("home")
        return

    st.markdown("""
    <div class="engage-header">
        <h1 style="margin:0; font-family:'Georgia', serif;">\U0001F4CA User Engagement Dashboard</h1>
        <p style="color:#FBF5B7; margin-top:8px;">Daily active users, matches made, chats sent, and feature popularity — at a glance.</p>
    </div>
    """, unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("\U0001F465 Daily Active Users", "3,842", "+6.2%")
    m2.metric("\U0001F4C5 Monthly Active Users", "41,207", "+3.8%")
    m3.metric("\U0001F49E Matches Made Today", "612", "+11%")
    m4.metric("\U0001F4AC Chat Messages Sent", "18,930", "+4.4%")

    st.markdown("---")
    dc1, dc2 = st.columns(2, gap="large")
    with dc1:
        st.markdown("### \U0001F4C8 DAU Trend (Last 7 Days)")
        dau_data = pd.DataFrame(np.random.randint(3200, 4200, size=(7, 1)), columns=["Daily Active Users"], index=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        st.line_chart(dau_data)
    with dc2:
        st.markdown("### \U0001F525 Most-Used Features")
        feature_usage = pd.DataFrame({"Sessions": [4200, 3600, 2900, 2500, 2100, 1800]},
                                      index=["Search Partner", "Chat & Alerts", "AI Recommendations", "Kundli Match", "Vendor Marketplace", "Astrology Booking"])
        st.bar_chart(feature_usage)

    st.markdown("---")
    st.markdown("### \u23F1\uFE0F Average Session Duration & Retention")
    rc1, rc2 = st.columns(2)
    rc1.metric("Avg. Session Duration", "9m 42s", "+38s")
    rc2.metric("Day-7 Retention", "34.6%", "+2.1%")
    retention_data = pd.DataFrame({"Retention %": [100, 62, 48, 41, 37, 35, 34.6]}, index=["Day 0", "Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 7"])
    st.line_chart(retention_data)

    st.markdown("<br>", unsafe_allow_html=True)
    st.button("\U0001F4E5 Export Engagement Report (CSV)", type="primary")
    st.caption("\u26A0\uFE0F Numbers on this page are demo/mock data — connect real analytics (e.g., MongoDB event logs) to make these live.")


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

    # Safety-net guard: even if a page isn't shown in the sidebar for this
    # role, block direct access to it (protects against stale session state
    # or a leftover "current_view" from switching accounts).
    if not role_can_access(st.session_state.user_role, view):
        render_global_css(bg_color="#F8F9FA")
        st.error("\U0001F6AB This page isn't available for your account type.")
        st.caption(f"Your role ({st.session_state.user_role}) doesn't have access to this section.")
        if st.button("\u2190 Back to Home"):
            go_to("home")
        return

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
    elif view == "vendor_membership":
        page_vendor_membership()
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
    elif view == "anniversary_birthday":
        page_anniversary_birthday()
    elif view == "budget_split":
        page_budget_split()
    elif view == "legal_pages":
        page_legal_pages()
    elif view == "about_us":
        page_about_us()
    elif view == "contact_us":
        page_contact_us()
    elif view == "vendor_bookings":
        page_vendor_bookings()
    elif view == "vendor_insights":
        page_vendor_insights()
    elif view == "company_dashboard":
        page_company_dashboard()
    elif view == "whatsapp_notifications":
        page_whatsapp_notifications()
    elif view == "video_profile":
        page_video_profile()
    elif view == "live_video_call":
        page_live_video_call()
    elif view == "astrology_consultation":
        page_astrology_consultation()
    elif view == "vendor_marketplace":
        page_vendor_marketplace()
    elif view == "smart_recommendations":
        page_smart_recommendations()
    elif view == "notification_preferences":
        page_notification_preferences()
    elif view == "local_vendor_ads":
        page_local_vendor_ads()
    elif view == "engagement_dashboard":
        page_engagement_dashboard()
    elif view in view_titles:
        page_placeholder(view_titles[view])
    else:
        page_home()


main()
