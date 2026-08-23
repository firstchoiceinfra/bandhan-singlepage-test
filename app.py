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
Everything else still shows a "coming in the next batch" placeholder —
nothing was skipped from these 8 pages, they're 1:1 with the originals.
"""

import streamlit as st
import base64
import datetime
import time
import io
from PIL import Image

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
# DEMO "DATABASE" (session-only — same as before)
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
# LOGIN / SIGNUP UI
# =====================================================================
def render_login_signup():
    init_demo_store()
    boss_email, boss_password = get_boss_credentials()

    render_html("""
    <div style="text-align:center; margin-bottom:20px;">
        <h2 style="color:#1A365D;">\U0001F510 Login to Bandhan.com</h2>
        <p style="color:gray;">Please log in or create an account to continue.</p>
    </div>
    """)

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
            elif su_email_clean in st.session_state.all_users or su_email_clean == boss_email.strip().lower():
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

    st.sidebar.caption("\u2139\uFE0F More pages are being ported over in the next batches (Wedding Services, Budget, Finance, and the rest).")

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
            go_to("placeholder_wedding_services")
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
                        go_to("placeholder_wedding_finance")
                with cta_col2:
                    if st.button("\U0001F6CD\uFE0F Explore Wedding Services", key="cta_services", type="primary", use_container_width=True):
                        go_to("placeholder_wedding_services")
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
    view_titles = {
        "placeholder_wedding_services": "Wedding Services",
        "placeholder_wedding_finance": "Wedding Finance",
    }

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
    elif view in view_titles:
        page_placeholder(view_titles[view])
    else:
        page_home()


main()
