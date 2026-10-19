import math
import random
import psycopg
import streamlit as st
from db import get_connection

# --- DIRECT, CLEAN IMPORTS ---
from passenger_ops import (
    register_passenger,
    get_passenger_by_phone,
    get_available_cabs,
    book_ride,
    get_passenger_rides,
    cancel_ride,
    delete_cancelled_ride,
    update_passenger_details,
)

from driver_ops import (
    get_cab_categories,
    signup_driver,
    login_driver,
    update_driver_profile,
    update_driver_status,
    get_driver_rating_stats,
    get_driver_rides,
    driver_update_ride_status,
    reassign_ride_to_next_driver,
)

st.set_page_config(page_title="Cab Booking", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# REAL LOCATIONS & GPS COORDINATES
# ==========================================
LOCATIONS_COORDS = {
    "Chennai Central, Chennai": (13.0827, 80.2707),
    "Chennai Airport (MAA), Chennai": (12.9941, 80.1709),
    "Chennai Egmore, Chennai": (13.0732, 80.2609),
    "Chromepet, Chennai": (12.9516, 80.1462),
    "Chengalpattu Junction, Tamil Nadu": (12.6819, 79.9888),
    "Chepauk, Chennai": (13.0630, 80.2812),
    "Chidambaram, Tamil Nadu": (11.3992, 79.6935),
    "Chittoor, Andhra Pradesh": (13.2172, 79.1003),
    "Chandigarh": (30.7333, 76.7794),
    "IIITDM Kancheepuram, Melakottaiyur": (12.8395, 80.1375),
    "Vandalur Zoo, Chennai": (12.8797, 80.0816),
    "Tambaram, Chennai": (12.9249, 80.1000),
    "Guindy, Chennai": (13.0067, 80.2206),
    "T. Nagar, Chennai": (13.0418, 80.2341),
    "Adyar, Chennai": (13.0012, 80.2565),
    "Velachery, Chennai": (12.9815, 80.2180),
    "OMR Navalur, Chennai": (12.8459, 80.2265),
    "Kelambakkam, Chennai": (12.7897, 80.2214),
    "Mahabalipuram, Tamil Nadu": (12.6208, 80.1945),
    "VGP Wonder World, ECR Chennai": (12.9142, 80.2515),
    "Kanchipuram Bus Stand, Tamil Nadu": (12.8342, 79.7036),
    "Bangalore (Majestic), Karnataka": (12.9767, 77.5713),
    "Bangalore Electronic City, Karnataka": (12.8452, 77.6602),
    "Bangalore Airport (BLR), Karnataka": (13.1986, 77.7066),
    "Pondicherry (Puducherry)": (11.9416, 79.8083),
    "Vellore, Tamil Nadu": (12.9165, 79.1325),
    "Tirupati, Andhra Pradesh": (13.6288, 79.4192),
    "Madurai, Tamil Nadu": (9.9252, 78.1198),
    "Coimbatore, Tamil Nadu": (11.0168, 76.9558),
    "Trichy (Tiruchirappalli), Tamil Nadu": (10.7905, 78.7047),
    "Salem, Tamil Nadu": (11.6643, 78.1460),
    "Hyderabad, Telangana": (17.3850, 78.4867),
    "Mumbai, Maharashtra": (19.0760, 72.8777),
    "Pune, Maharashtra": (18.5204, 73.8567),
    "Delhi (Connaught Place)": (28.6315, 77.2167),
    "Kolkata, West Bengal": (22.5726, 88.3639),
    "Kochi, Kerala": (9.9312, 76.2673),
}

def calculate_road_distance_km(loc1, loc2):
    if not loc1 or not loc2 or loc1 == loc2:
        return 0.0
    lat1, lon1 = LOCATIONS_COORDS[loc1]
    lat2, lon2 = LOCATIONS_COORDS[loc2]

    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    straight_km = 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    road_km = straight_km * 1.21
    return round(max(road_km, 1.5), 1)

# ==========================================
# SVG GRAPHICS & PROGRESS BAR BUILDER
# ==========================================
CAR_SVG = '<svg width="48" height="24" viewBox="0 0 64 32" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 20L14 9C15.2 6.8 17.5 5.5 20 5.5H44C46.5 5.5 48.8 6.8 50 9L56 20H8Z" fill="#111111"/><rect x="4" y="18" width="56" height="9" rx="4.5" fill="#000000"/><path d="M16 10H29V17H12L16 10Z" fill="#E2E8F0"/><path d="M33 10H46L50 17H33V10Z" fill="#E2E8F0"/><circle cx="16" cy="26" r="5" fill="#1E293B" stroke="#FFFFFF" stroke-width="2"/><circle cx="48" cy="26" r="5" fill="#1E293B" stroke="#FFFFFF" stroke-width="2"/></svg>'

def render_brand_logo(title_text, subtitle_text=None):
    html = f'<div class="brand-header">{CAR_SVG}<h1 class="brand-title">{title_text}</h1></div>'
    if subtitle_text:
        html += f'<div class="login-bold-tagline">{subtitle_text}</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_top_nav_logo(title_text):
    html = f'<div class="brand-header">{CAR_SVG}<span class="nav-title">{title_text}</span></div>'
    st.markdown(html, unsafe_allow_html=True)

def render_ride_progress_bar(status):
    """Renders a visual road track with a car positioned at the current ride stage."""
    stage_map = {
        "REQUESTED": (12, 1, "Assigning a Driver...", "Contacting a nearby available driver in your category. If busy, another driver is approached automatically."),
        "ACCEPTED": (44, 2, "Driver Accepted!", "Your driver has accepted the ride request and is heading to your pickup point."),
        "ONGOING": (76, 3, "Ride Ongoing", "You are currently en route to your destination. Enjoy your ride!"),
        "COMPLETED": (100, 4, "Ride Completed", "You have arrived at your destination. Thank you for riding with Cab Booking!"),
    }

    if status not in stage_map:
        st.markdown(
            f'<div class="progress-alert-box">Ride Status: {status}</div>',
            unsafe_allow_html=True,
        )
        return

    pct, step_idx, headline, subtext = stage_map[status]
    fill_color = "#16A34A" if status == "COMPLETED" else "#000000"

    s1_cls = "step-active" if step_idx >= 1 else "step-inactive"
    s2_cls = "step-active" if step_idx >= 2 else "step-inactive"
    s3_cls = "step-active" if step_idx >= 3 else "step-inactive"
    s4_cls = "step-active" if step_idx >= 4 else "step-inactive"

    html = (
        f'<div class="progress-wrapper">'
        f'<div class="progress-headline">{headline}</div>'
        f'<div class="progress-subtext">{subtext}</div>'
        f'<div class="road-container">'
        f'<div class="road-track"><div class="road-fill" style="width:{pct}%; background:{fill_color};"></div></div>'
        f'<div class="car-marker" style="left:calc({pct}% - 24px);">{CAR_SVG}</div>'
        f'</div>'
        f'<div class="steps-row">'
        f'<div class="step-item {s1_cls}"><div class="step-dot">1</div><div class="step-label">Assigning Driver</div></div>'
        f'<div class="step-item {s2_cls}"><div class="step-dot">2</div><div class="step-label">Driver Accepted</div></div>'
        f'<div class="step-item {s3_cls}"><div class="step-dot">3</div><div class="step-label">Ride Ongoing</div></div>'
        f'<div class="step-item {s4_cls}"><div class="step-dot">4</div><div class="step-label">Ride Completed</div></div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# GLOBAL CSS (BALANCED FONT SCALE & NO POPOVER ARROWS)
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');

html, body, [class*="css"], p, span, div, label {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 0.95rem;
    color: #0F172A;
}

/* 1. REMOVE DOUBLE DOWN ARROWS ON PROFILE POPOVER BUTTON */
div[data-testid="stPopover"] > div > button svg {
    display: none !important;
}
div[data-testid="stPopover"] > div > button {
    background-color: #000000 !important;
    color: #FFFFFF !important;
    border: 1.5px solid #000000 !important;
    border-radius: 999px !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
    padding: 0.45rem 1.1rem !important;
}
div[data-testid="stPopover"] > div > button * {
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
}

/* 2. PROPORTIONAL HEADINGS AND HIGHLIGHTS */
.brand-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 4px;
}
.brand-title {
    font-size: 2.0rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em;
    color: #000000;
    margin: 0;
    line-height: 1.15;
}
.nav-title {
    font-size: 1.5rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em;
    color: #000000;
}
.login-bold-tagline {
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    color: #334155;
    margin-top: 2px;
    margin-bottom: 18px;
}
.section-heading {
    font-size: 1.55rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.025em;
    color: #000000;
    margin-bottom: 12px;
}
.card-title-bold {
    font-size: 1.12rem !important;
    font-weight: 800 !important;
    color: #000000;
    margin-bottom: 3px;
}
.big-route-banner {
    background-color: #F8FAFC;
    border: 1.5px solid #000000;
    border-radius: 14px;
    padding: 14px 20px;
    margin-bottom: 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
}
.big-route-text {
    font-size: 1.08rem !important;
    font-weight: 800 !important;
    color: #000000;
}
.big-distance-pill {
    background-color: #000000;
    color: #FFFFFF !important;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 0.9rem !important;
    font-weight: 800 !important;
}
.big-price-highlight {
    font-size: 1.45rem !important;
    font-weight: 800 !important;
    color: #000000;
    line-height: 1.15;
}
.category-title-highlight {
    font-size: 1.2rem !important;
    font-weight: 800 !important;
    color: #000000;
}
.meta-bold {
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    color: #475569;
}
.status-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.78rem !important;
    font-weight: 800 !important;
    background-color: #E2E8F0;
    color: #0F172A;
}

/* Top Welcome Bar */
.top-black-bar {
    background-color: #000000;
    color: #FFFFFF !important;
    padding: 13px 22px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 14px;
    margin-bottom: 22px;
    font-weight: 700 !important;
}
.top-black-bar span {
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 1.0rem !important;
}
.top-black-bar span.badge {
    background-color: #262626;
    padding: 5px 13px;
    border-radius: 999px;
    font-size: 0.84rem !important;
    font-weight: 700 !important;
    color: #FFFFFF !important;
}

/* Form Labels & Captions */
div[data-testid="stWidgetLabel"] p {
    font-size: 0.92rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
}
div[data-testid="stCaptionContainer"] p {
    font-size: 0.84rem !important;
    font-weight: 600 !important;
    color: #475569 !important;
}

/* Buttons */
div.stButton > button {
    font-weight: 700 !important;
    font-size: 0.92rem !important;
    border-radius: 10px !important;
    padding: 0.5rem 1rem !important;
    border: 1.5px solid #CBD5E1 !important;
}
div.stButton > button[kind="primary"] {
    background-color: #000000 !important;
    color: #FFFFFF !important;
    border: 1.5px solid #000000 !important;
}
div.stButton > button[kind="primary"] * {
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #222222 !important;
    border-color: #222222 !important;
}

/* 4. CAR ON PROGRESS BAR TRACKER */
.progress-wrapper {
    background: #FFFFFF;
    border: 1.5px solid #000000;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 20px;
}
.progress-headline {
    font-size: 1.35rem !important;
    font-weight: 800 !important;
    color: #000000;
    margin-bottom: 4px;
}
.progress-subtext {
    font-size: 0.92rem !important;
    font-weight: 600 !important;
    color: #475569;
    margin-bottom: 30px;
}
.road-container {
    position: relative;
    margin: 24px 14px 20px 14px;
    height: 32px;
}
.road-track {
    width: 100%;
    height: 10px;
    background-color: #E2E8F0;
    border-radius: 999px;
    overflow: hidden;
    position: absolute;
    top: 12px;
}
.road-fill {
    height: 100%;
    border-radius: 999px;
    transition: width 0.5s ease;
}
.car-marker {
    position: absolute;
    top: -10px;
    transition: left 0.5s ease;
    filter: drop-shadow(0 3px 5px rgba(0,0,0,0.18));
}
.steps-row {
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
}
.step-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    width: 24%;
}
.step-dot {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800 !important;
    font-size: 0.85rem !important;
    margin-bottom: 6px;
}
.step-active .step-dot {
    background-color: #000000;
    color: #FFFFFF !important;
}
.step-inactive .step-dot {
    background-color: #E2E8F0;
    color: #64748B !important;
}
.step-label {
    font-size: 0.88rem !important;
    font-weight: 700 !important;
}
.step-active .step-label {
    color: #000000 !important;
}
.step-inactive .step-label {
    color: #94A3B8 !important;
}
.progress-alert-box {
    background-color: #FEE2E2;
    border: 1.5px solid #EF4444;
    color: #991B1B !important;
    padding: 14px 18px;
    border-radius: 12px;
    font-size: 1.05rem !important;
    font-weight: 800 !important;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "passenger_auth"
if "passenger" not in st.session_state:
    st.session_state.passenger = None
if "driver" not in st.session_state:
    st.session_state.driver = None
if "passenger_view" not in st.session_state:
    st.session_state.passenger_view = "ride"  # 'ride', 'select_category', 'ride_progress', 'activity', 'account'
if "driver_view" not in st.session_state:
    st.session_state.driver_view = "dashboard"
if "selected_ride_details" not in st.session_state:
    st.session_state.selected_ride_details = None
if "selected_driver_ride_details" not in st.session_state:
    st.session_state.selected_driver_ride_details = None
if "booking_draft" not in st.session_state:
    st.session_state.booking_draft = None
if "active_booking_id" not in st.session_state:
    st.session_state.active_booking_id = None


# ==========================================
# 1. PASSENGER LOGIN / SIGNUP SCREEN
# ==========================================
def render_passenger_auth():
    _, center_col, _ = st.columns([1.2, 1.6, 1.2])
    with center_col:
        render_brand_logo("Cab Booking", "Move anywhere. Boldly and reliably.")

        tab_mode = st.radio(
            "Auth Mode",
            ["Log In", "Sign Up"],
            horizontal=True,
            label_visibility="collapsed"
        )

        with st.container(border=True):
            if tab_mode == "Log In":
                st.markdown('<div class="card-title-bold">What\'s your phone number?</div>', unsafe_allow_html=True)
                phone = st.text_input("10-digit mobile number", placeholder="Enter your registered 10-digit phone number")
                if st.button("Continue", type="primary", use_container_width=True):
                    try:
                        user = get_passenger_by_phone(phone)
                        if user:
                            st.session_state.passenger = {
                                "id": user[0],
                                "name": user[1],
                                "phone": user[2],
                                "email": user[3],
                                "created_at": user[4],
                            }
                            st.session_state.passenger_view = "ride"
                            st.rerun()
                        else:
                            st.error("Phone number not found. Please Sign Up first.")
                    except psycopg.OperationalError:
                        st.error("Database connection error: Unable to reach Neon server.")
            else:
                st.markdown('<div class="card-title-bold">Create your Passenger Account</div>', unsafe_allow_html=True)
                full_name = st.text_input("Full Name", placeholder="Enter your full name")
                phone = st.text_input("10-digit Mobile Number", placeholder="e.g. 9876543210")
                email = st.text_input("Email Address", placeholder="name@example.com")
                if st.button("Continue", type="primary", use_container_width=True):
                    if not full_name.strip() or not phone.strip() or not email.strip():
                        st.error("All fields are required.")
                    elif not phone.strip().isdigit() or len(phone.strip()) != 10:
                        st.error("Phone number must be exactly 10 digits.")
                    else:
                        try:
                            new_id = register_passenger(full_name, phone, email)
                            if new_id:
                                user = get_passenger_by_phone(phone)
                                st.session_state.passenger = {
                                    "id": user[0],
                                    "name": user[1],
                                    "phone": user[2],
                                    "email": user[3],
                                    "created_at": user[4],
                                }
                                st.session_state.passenger_view = "ride"
                                st.rerun()
                            else:
                                st.error("Phone number or email is already registered.")
                        except psycopg.OperationalError:
                            st.error("Database connection error: Unable to reach Neon server.")

        st.write("")
        if st.button("Driver Partner Login / Registration →", use_container_width=True):
            st.session_state.auth_mode = "driver_auth"
            st.rerun()


# ==========================================
# 2. SEPARATE DRIVER LOGIN / SIGNUP SCREEN
# ==========================================
def render_driver_auth():
    _, center_col, _ = st.columns([1.15, 1.7, 1.15])
    with center_col:
        render_brand_logo("Driver Partner", "Drive when you want. Earn on your terms.")

        d_mode = st.radio(
            "Driver Auth Mode",
            ["Driver Log In", "Driver Sign Up"],
            horizontal=True,
            label_visibility="collapsed"
        )

        with st.container(border=True):
            if d_mode == "Driver Log In":
                st.markdown('<div class="card-title-bold">Driver Sign In</div>', unsafe_allow_html=True)
                d_phone = st.text_input("Registered 10-digit Driver Phone Number", placeholder="Enter 10-digit phone number")
                if st.button("Continue to Driver Portal", type="primary", use_container_width=True):
                    try:
                        drv = login_driver(d_phone)
                        if drv:
                            st.session_state.driver = {
                                "id": drv[0],
                                "name": drv[1],
                                "license_no": drv[2],
                                "status": drv[3],
                                "plate_no": drv[4],
                                "model": drv[5],
                                "category": drv[6],
                                "phone": d_phone.strip(),
                            }
                            st.session_state.driver_view = "dashboard"
                            st.rerun()
                        else:
                            st.error("Driver account not found. Please Sign Up first.")
                    except psycopg.OperationalError:
                        st.error("Database connection error: Unable to reach Neon server.")
            else:
                st.markdown('<div class="card-title-bold">Register as a Driver Partner</div>', unsafe_allow_html=True)
                try:
                    categories = get_cab_categories()
                except psycopg.OperationalError:
                    categories = []
                cat_map = {f"{c[1]} (ID: {c[0]})": c[0] for c in categories} if categories else {"Sedan (ID: 1)": 1}

                d_name = st.text_input("Full Name", placeholder="Driver's full name")
                d_phone = st.text_input("10-digit Mobile Number", placeholder="10-digit phone number")
                d_license = st.text_input("Driving License Number", placeholder="e.g. TN0120230012345")
                c_plate = st.text_input("Cab Plate Number", placeholder="e.g. TN 07 AB 1234")
                c_model = st.text_input("Cab Vehicle Model", placeholder="e.g. Maruti Dzire / Hyundai Creta")
                selected_cat_label = st.selectbox("Cab Category", list(cat_map.keys()))

                if st.button("Register & Open Driver Portal", type="primary", use_container_width=True):
                    if not all([d_name.strip(), d_phone.strip(), d_license.strip(), c_plate.strip(), c_model.strip()]):
                        st.error("Please fill in all driver and vehicle details.")
                    elif not d_phone.strip().isdigit() or len(d_phone.strip()) != 10:
                        st.error("Phone number must be exactly 10 digits.")
                    else:
                        cat_id = cat_map[selected_cat_label]
                        new_drv_id = signup_driver(d_name, d_phone, d_license, c_plate, c_model, cat_id)
                        if new_drv_id:
                            drv = login_driver(d_phone)
                            st.session_state.driver = {
                                "id": drv[0],
                                "name": drv[1],
                                "license_no": drv[2],
                                "status": drv[3],
                                "plate_no": drv[4],
                                "model": drv[5],
                                "category": drv[6],
                                "phone": d_phone.strip(),
                            }
                            st.session_state.driver_view = "dashboard"
                            st.rerun()
                        else:
                            st.error("Phone number, license number, or plate number already exists.")

        st.write("")
        if st.button("← Back to Passenger Login", use_container_width=True):
            st.session_state.auth_mode = "passenger_auth"
            st.rerun()


# ==========================================
# 3. PASSENGER PORTAL (MULTI-PAGE FLOW)
# ==========================================
def render_passenger_portal():
    p = st.session_state.passenger
    rides = get_passenger_rides(p["id"])
    active_rides = [r for r in rides if r[5] in ("REQUESTED", "ACCEPTED", "ONGOING")]
    active_count = len(active_rides)

    # Top Navigation Header (Single clean profile pill without double arrows)
    h_col1, _, h_col3 = st.columns([3.5, 4.0, 1.5])
    with h_col1:
        render_top_nav_logo("Cab Booking")

    with h_col3:
        with st.popover(f"👤 {p['name']}", use_container_width=True):
            st.markdown(f'<div class="card-title-bold">{p["name"]}</div>', unsafe_allow_html=True)
            st.caption(f"Phone: {p['phone']}")
            st.divider()
            if st.button("Ride Home", use_container_width=True):
                st.session_state.passenger_view = "ride"
                st.rerun()
            if active_rides:
                if st.button("Live Ride Progress", use_container_width=True):
                    st.session_state.active_booking_id = active_rides[0][0]
                    st.session_state.passenger_view = "ride_progress"
                    st.rerun()
            if st.button("Activity & Past Trips", use_container_width=True):
                st.session_state.passenger_view = "activity"
                st.rerun()
            if st.button("Manage Account", use_container_width=True):
                st.session_state.passenger_view = "account"
                st.rerun()
            st.divider()
            if st.button("Logout", use_container_width=True):
                st.session_state.passenger = None
                st.session_state.selected_ride_details = None
                st.session_state.booking_draft = None
                st.session_state.active_booking_id = None
                st.rerun()

    st.markdown(
        f'<div class="top-black-bar"><span>Welcome back, {p["name"]}</span>'
        f'<span class="badge">You have {active_count} active ride request(s)</span></div>',
        unsafe_allow_html=True,
    )

    unfulfilled_rides = [r for r in rides if r[5] == "NO_DRIVERS"]
    for ur in unfulfilled_rides:
        st.error(f"🚨 **Ride Alert:** Booking #{ur[0]} ({ur[1]} → {ur[2]}) could not be fulfilled because all drivers were busy.")

    # =================================-------------------------
    # PAGE A: HOME SCREEN (Select Route & Click "See prices")
    # =================================-------------------------
    if st.session_state.passenger_view == "ride":
        left_col, right_col = st.columns([1.05, 1.35], gap="large")

        with left_col:
            st.markdown('<div class="section-heading">Request a ride</div>', unsafe_allow_html=True)
            with st.container(border=True):
                location_list = sorted(list(LOCATIONS_COORDS.keys()))

                pickup_loc = st.selectbox(
                    "Pickup Location",
                    options=location_list,
                    index=None,
                    placeholder="Choose pickup city or landmark..."
                )
                drop_loc = st.selectbox(
                    "Destination Location",
                    options=location_list,
                    index=None,
                    placeholder="Choose destination city or landmark..."
                )

                calc_distance = 0.0
                if pickup_loc and drop_loc:
                    if pickup_loc == drop_loc:
                        st.warning("Pickup and destination cannot be the same location.")
                    else:
                        calc_distance = calculate_road_distance_km(pickup_loc, drop_loc)
                        st.markdown(f'<div class="big-route-text" style="margin: 8px 0;">📏 Estimated Road Distance: {calc_distance} km</div>', unsafe_allow_html=True)

                if st.button("See prices →", type="primary", use_container_width=True):
                    if not pickup_loc or not drop_loc or pickup_loc == drop_loc:
                        st.error("Please select valid, distinct Pickup and Destination locations.")
                    else:
                        st.session_state.booking_draft = {
                            "pickup": pickup_loc,
                            "drop": drop_loc,
                            "distance": calc_distance,
                        }
                        st.session_state.passenger_view = "select_category"
                        st.rerun()

            if active_rides:
                latest_active = active_rides[0]
                with st.container(border=True):
                    st.markdown(f'<div class="card-title-bold">🚖 Active Ride #{latest_active[0]} ({latest_active[5]})</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="meta-bold" style="margin-bottom:8px;">{latest_active[1]} → {latest_active[2]}</div>', unsafe_allow_html=True)
                    if st.button("Open Live Ride Progress Bar →", type="primary", use_container_width=True):
                        st.session_state.active_booking_id = latest_active[0]
                        st.session_state.passenger_view = "ride_progress"
                        st.rerun()

        with right_col:
            st.markdown('<div class="section-heading">Your account and activity</div>', unsafe_allow_html=True)

            with st.container(border=True):
                ac1, ac2 = st.columns([3, 1.3], vertical_alignment="center")
                with ac1:
                    st.markdown(f'<div class="card-title-bold">{p["name"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="meta-bold">📞 {p["phone"]} &nbsp;|&nbsp; ✉️ {p["email"]}</div>', unsafe_allow_html=True)
                with ac2:
                    if st.button("Manage account", key="home_manage_btn", use_container_width=True):
                        st.session_state.passenger_view = "account"
                        st.rerun()

            st.markdown('<div class="card-title-bold" style="margin: 14px 0 8px 0;">Recent & Past Trips</div>', unsafe_allow_html=True)
            if not rides:
                st.info("No trips booked yet. Use the form on the left to request your first ride!")
            else:
                for r in rides[:4]:
                    with st.container(border=True):
                        rc1, rc2, rc3 = st.columns([2.5, 1.2, 1.3], vertical_alignment="center")
                        with rc1:
                            st.markdown(f'<div class="card-title-bold">{r[1]} → {r[2]}</div>', unsafe_allow_html=True)
                            st.caption(f"Booking #{r[0]} • {str(r[6])[:16]}")
                        with rc2:
                            st.markdown(f'<div class="big-price-highlight">₹{float(r[4]):,.2f}</div>', unsafe_allow_html=True)
                            st.markdown(f'<span class="status-pill">{r[5]}</span>', unsafe_allow_html=True)
                        with rc3:
                            if r[5] in ("REQUESTED", "ACCEPTED", "ONGOING"):
                                if st.button("Track Ride →", key=f"trk_{r[0]}", type="primary", use_container_width=True):
                                    st.session_state.active_booking_id = r[0]
                                    st.session_state.passenger_view = "ride_progress"
                                    st.rerun()
                            else:
                                if st.button("View Activity", key=f"home_detail_{r[0]}", use_container_width=True):
                                    st.session_state.passenger_view = "activity"
                                    st.rerun()

    # =================================-------------------------
    # PAGE B: DEDICATED CAB CATEGORY SELECTION PAGE
    # =================================-------------------------
    elif st.session_state.passenger_view == "select_category":
        draft = st.session_state.booking_draft
        if not draft:
            st.session_state.passenger_view = "ride"
            st.rerun()

        top_c1, top_c2 = st.columns([3.5, 1.2], vertical_alignment="center")
        with top_c1:
            st.markdown('<div class="section-heading">Choose a Cab Category</div>', unsafe_allow_html=True)
        with top_c2:
            if st.button("← Change Route", use_container_width=True):
                st.session_state.passenger_view = "ride"
                st.rerun()

        st.markdown(
            f'<div class="big-route-banner">'
            f'<span class="big-route-text">📍 {draft["pickup"]} &nbsp;→&nbsp; 🏁 {draft["drop"]}</span>'
            f'<span class="big-distance-pill">Road Distance: {draft["distance"]} km</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        all_categories = get_cab_categories()
        available_cabs = get_available_cabs()

        cabs_by_cat = {}
        seats_by_cat = {}
        for cab in available_cabs:
            c_type = cab[3]
            cabs_by_cat.setdefault(c_type, []).append(cab)
            seats_by_cat[c_type] = cab[6]

        if not all_categories:
            st.warning("No cab categories configured in the database.")
        else:
            for cat_row in all_categories:
                cat_id, type_name, base_fare, rate_km = cat_row
                est_fare = round(float(base_fare) + (draft["distance"] * float(rate_km)), 2)
                matching_cabs = cabs_by_cat.get(type_name, [])
                seats = seats_by_cat.get(type_name, 4)

                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([0.6, 2.4, 1.3, 1.3], vertical_alignment="center")
                    with c1:
                        st.markdown(CAR_SVG, unsafe_allow_html=True)
                    with c2:
                        st.markdown(f'<div class="category-title-highlight">{type_name}</div>', unsafe_allow_html=True)
                        st.markdown(
                            f'<div class="meta-bold">💺 Up to {seats} Seats &nbsp;•&nbsp; '
                            f'Base ₹{float(base_fare):.0f} + ₹{float(rate_km):.0f}/km</div>',
                            unsafe_allow_html=True,
                        )
                    with c3:
                        st.markdown(f'<div class="big-price-highlight">₹{est_fare:,.2f}</div>', unsafe_allow_html=True)
                        st.caption("Total Estimated Fare")
                    with c4:
                        if st.button(f"Select {type_name}", key=f"sel_cat_{cat_id}", type="primary", use_container_width=True):
                            if not matching_cabs:
                                st.error(f"No drivers are currently online in {type_name}. Please select another category.")
                            else:
                                chosen_cab = random.choice(matching_cabs)
                                chosen_cab_id = chosen_cab[0]
                                res = book_ride(
                                    p["id"],
                                    chosen_cab_id,
                                    draft["pickup"],
                                    draft["drop"],
                                    draft["distance"],
                                )
                                if res:
                                    st.session_state.active_booking_id = res[0]
                                    st.session_state.passenger_view = "ride_progress"
                                    st.rerun()
                                else:
                                    st.error("Could not complete booking. Please try again.")

    # =================================-------------------------
    # PAGE C: DEDICATED LIVE RIDE PROGRESS BAR PAGE
    # =================================-------------------------
    elif st.session_state.passenger_view == "ride_progress":
        top_p1, top_p2, top_p3 = st.columns([3.2, 1.2, 1.2], vertical_alignment="center")
        with top_p1:
            st.markdown('<div class="section-heading">Live Ride Progress</div>', unsafe_allow_html=True)
        with top_p2:
            if st.button("🔄 Refresh Status", type="primary", use_container_width=True):
                st.rerun()
        with top_p3:
            if st.button("← Back to Home", use_container_width=True):
                st.session_state.passenger_view = "ride"
                st.rerun()

        target_ride = None
        if st.session_state.active_booking_id:
            for r in rides:
                if r[0] == st.session_state.active_booking_id:
                    target_ride = r
                    break
        if not target_ride and rides:
            target_ride = rides[0]

        if not target_ride:
            st.info("No active ride found.")
        else:
            b_id, pickup, drop, dist, fare, status, b_time, model, plate, driver_name = target_ride

            render_ride_progress_bar(status)

            with st.container(border=True):
                d_col1, d_col2 = st.columns([2.3, 1.1], vertical_alignment="center")
                with d_col1:
                    st.markdown(f'<div class="category-title-highlight">Booking #{b_id}: {pickup} → {drop}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="meta-bold" style="margin-top:4px;">📏 Distance: {dist} km &nbsp;|&nbsp; 🕒 Booked at: {str(b_time)[:19]}</div>', unsafe_allow_html=True)
                    st.write("")
                    if status == "REQUESTED":
                        st.markdown('<div class="card-title-bold">🔍 Contacting Driver...</div>', unsafe_allow_html=True)
                        st.markdown(
                            f'<div class="meta-bold">Currently pinging nearby driver: {driver_name}. '
                            f'If declined, another available driver in your category will be contacted automatically.</div>',
                            unsafe_allow_html=True,
                        )
                    elif status in ("ACCEPTED", "ONGOING", "COMPLETED"):
                        st.markdown(f'<div class="card-title-bold">👨‍✈️ Assigned Driver: {driver_name}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="big-route-text">🚖 Vehicle: {model} &nbsp;•&nbsp; Plate: {plate}</div>', unsafe_allow_html=True)
                    elif status == "NO_DRIVERS":
                        st.error("All drivers in this category were unavailable or declined the request.")
                    elif status == "CANCELLED":
                        st.warning("This booking was cancelled.")

                with d_col2:
                    st.markdown('<div class="meta-bold">Total Ride Fare</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="big-price-highlight" style="font-size:1.85rem !important;">₹{float(fare):,.2f}</div>', unsafe_allow_html=True)
                    st.write("")
                    if status == "REQUESTED":
                        if st.button("Cancel Ride Request", use_container_width=True):
                            cancel_ride(b_id, p["id"])
                            st.rerun()
                    elif status in ("CANCELLED", "NO_DRIVERS"):
                        if st.button("Delete Cancelled Record", use_container_width=True):
                            delete_cancelled_ride(b_id, p["id"])
                            st.session_state.passenger_view = "ride"
                            st.rerun()

    # =================================-------------------------
    # PAGE D: ACTIVITY & PAST TRIPS
    # =================================-------------------------
    elif st.session_state.passenger_view == "activity":
        st.markdown('<div class="section-heading">Activity & Past Trips</div>', unsafe_allow_html=True)
        if st.button("← Back to Home"):
            st.session_state.passenger_view = "ride"
            st.rerun()
        if not rides:
            st.info("You have no recorded trips.")
        else:
            for r in rides:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1.5, 1.5], vertical_alignment="center")
                    with c1:
                        st.markdown(f'<div class="card-title-bold">Booking #{r[0]}: {r[1]} → {r[2]}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="meta-bold">Booked on {str(r[6])[:19]} | Cab: {r[7]} ({r[8]}) | Driver: {r[9]}</div>', unsafe_allow_html=True)
                    with c2:
                        st.markdown(f'<div class="big-price-highlight">₹{float(r[4]):,.2f}</div>', unsafe_allow_html=True)
                        st.markdown(f'<span class="meta-bold">Distance: {r[3]} km</span> &nbsp;|&nbsp; <span class="status-pill">{r[5]}</span>', unsafe_allow_html=True)
                    with c3:
                        if r[5] in ("REQUESTED", "ACCEPTED", "ONGOING"):
                            if st.button("View Progress Bar →", key=f"act_prog_{r[0]}", type="primary", use_container_width=True):
                                st.session_state.active_booking_id = r[0]
                                st.session_state.passenger_view = "ride_progress"
                                st.rerun()
                            if r[5] == "REQUESTED":
                                if st.button("Cancel Ride", key=f"act_can_{r[0]}", use_container_width=True):
                                    cancel_ride(r[0], p["id"])
                                    st.rerun()
                        elif r[5] in ("CANCELLED", "NO_DRIVERS"):
                            if st.button("Delete Cancelled Ride", key=f"act_del_{r[0]}", use_container_width=True):
                                delete_cancelled_ride(r[0], p["id"])
                                st.rerun()

    # =================================-------------------------
    # PAGE E: MANAGE ACCOUNT
    # =================================-------------------------
    elif st.session_state.passenger_view == "account":
        st.markdown('<div class="section-heading">Manage Account</div>', unsafe_allow_html=True)
        if st.button("← Back to Home"):
            st.session_state.passenger_view = "ride"
            st.rerun()
        with st.container(border=True):
            new_name = st.text_input("Full Name", value=p["name"])
            new_phone = st.text_input("Phone Number (10 digits)", value=p["phone"])
            new_email = st.text_input("Email Address", value=p["email"] or "")

            if st.button("Save Changes", type="primary"):
                updated = update_passenger_details(p["id"], new_name, new_phone, new_email)
                if updated:
                    st.session_state.passenger["name"] = updated[1]
                    st.session_state.passenger["phone"] = updated[2]
                    st.session_state.passenger["email"] = updated[3]
                    st.success("Profile updated successfully!")
                    st.rerun()
                else:
                    st.error("Could not update profile. Check phone format or duplicate credentials.")


# ==========================================
# 4. DRIVER PORTAL
# ==========================================
def render_driver_portal():
    d = st.session_state.driver
    avg_rating, total_reviews = get_driver_rating_stats(d["id"])
    all_driver_rides = get_driver_rides(d["id"])

    fresh_drv = login_driver(d["phone"])
    if fresh_drv:
        d["name"] = fresh_drv[1]
        d["license_no"] = fresh_drv[2]
        d["status"] = fresh_drv[3]
        d["plate_no"] = fresh_drv[4]
        d["model"] = fresh_drv[5]
        d["category"] = fresh_drv[6]

    active_rides = [r for r in all_driver_rides if r[7] in ("REQUESTED", "ACCEPTED", "ONGOING")]
    past_rides = [r for r in all_driver_rides if r[7] in ("COMPLETED", "CANCELLED", "NO_DRIVERS")]

    h_col1, _, h_col3 = st.columns([3.5, 4.0, 1.5])
    with h_col1:
        render_top_nav_logo("Cab Booking • Driver")

    with h_col3:
        with st.popover(f"👤 {d['name']}", use_container_width=True):
            st.markdown(f'<div class="card-title-bold">{d["name"]}</div>', unsafe_allow_html=True)
            st.caption(f"Rating: ★ {avg_rating:.2f} ({total_reviews} reviews)")
            st.caption(f"Vehicle: {d['model']} ({d['plate_no']})")
            st.divider()
            if st.button("Dashboard", use_container_width=True):
                st.session_state.driver_view = "dashboard"
                st.rerun()
            if st.button("Manage Profile", use_container_width=True):
                st.session_state.driver_view = "profile"
                st.rerun()
            if st.button("Past Rides & Ratings", use_container_width=True):
                st.session_state.driver_view = "history"
                st.rerun()
            st.divider()
            if st.button("Logout", use_container_width=True):
                st.session_state.driver = None
                st.session_state.selected_driver_ride_details = None
                st.rerun()

    st.markdown(
        f'<div class="top-black-bar">'
        f'<span>Welcome back, {d["name"]}</span>'
        f'<span class="badge">Status: {d["status"]}</span>'
        f'<span class="badge">★ {avg_rating:.2f} ({total_reviews} reviews)</span>'
        f'<span class="badge">{d["model"]} ({d["plate_no"]}) • {d["category"]}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.driver_view == "dashboard":
        left_col, right_col = st.columns([1.05, 1.35], gap="large")

        with left_col:
            st.markdown('<div class="section-heading">Shift & Dispatch</div>', unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown(f'<div class="card-title-bold">Current Availability: {d["status"]}</div>', unsafe_allow_html=True)
                st.caption("Go Online to receive random category dispatch requests from passengers.")
                on_trip = d["status"] == "ON_TRIP"
                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    if st.button("Go Online (AVAILABLE)", type="primary", use_container_width=True, disabled=on_trip):
                        update_driver_status(d["id"], "AVAILABLE")
                        st.rerun()
                with btn_c2:
                    if st.button("Go Offline (OFFLINE)", use_container_width=True, disabled=on_trip):
                        update_driver_status(d["id"], "OFFLINE")
                        st.rerun()

            st.markdown('<div class="card-title-bold" style="margin: 14px 0 8px 0;">Incoming & Active Ride Requests</div>', unsafe_allow_html=True)
            if not active_rides:
                with st.container(border=True):
                    st.info("No active ride requests right now. Stay AVAILABLE to receive bookings.")
            else:
                for r in active_rides:
                    with st.container(border=True):
                        st.markdown(f'<div class="card-title-bold">Booking #{r[0]} — Passenger: {r[1]} ({r[2]})</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="big-route-text" style="margin-top:4px;">📍 {r[3]} &nbsp;→&nbsp; 🏁 {r[4]}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="meta-bold" style="margin:6px 0 10px 0;">Distance: {r[5]} km &nbsp;|&nbsp; Fare: ₹{float(r[6]):,.2f} &nbsp;|&nbsp; Status: {r[7]}</div>', unsafe_allow_html=True)

                        if r[7] == "REQUESTED":
                            col_a, col_b = st.columns(2)
                            with col_a:
                                if st.button("Accept Ride", key=f"drv_acc_{r[0]}", type="primary", use_container_width=True, disabled=(d["status"] == "ON_TRIP")):
                                    driver_update_ride_status(r[0], d["id"], "ACCEPTED")
                                    st.rerun()
                            with col_b:
                                if st.button("Decline & Pass to Next Driver", key=f"drv_dec_{r[0]}", use_container_width=True):
                                    outcome = reassign_ride_to_next_driver(r[0], d["id"])
                                    if outcome == "REASSIGNED":
                                        st.toast("Ride declined and automatically passed to another available driver!")
                                    else:
                                        st.toast("Ride declined. No other driver available in this category.")
                                    st.rerun()
                        elif r[7] == "ACCEPTED":
                            if st.button("Start Trip (Move Car to ONGOING)", key=f"drv_start_{r[0]}", type="primary", use_container_width=True):
                                driver_update_ride_status(r[0], d["id"], "ONGOING")
                                st.rerun()
                        elif r[7] == "ONGOING":
                            if st.button("Complete Trip (Move Car to COMPLETED)", key=f"drv_comp_{r[0]}", type="primary", use_container_width=True):
                                driver_update_ride_status(r[0], d["id"], "COMPLETED")
                                st.rerun()

        with right_col:
            st.markdown('<div class="section-heading">Your profile and activity</div>', unsafe_allow_html=True)

            with st.container(border=True):
                dc1, dc2 = st.columns([3.1, 1.3], vertical_alignment="center")
                with dc1:
                    st.markdown(f'<div class="card-title-bold">{d["name"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="meta-bold">📞 {d["phone"]} &nbsp;|&nbsp; 🪪 License: {d["license_no"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="meta-bold">🚖 {d["model"]} ({d["plate_no"]}) • {d["category"]}</div>', unsafe_allow_html=True)
                with dc2:
                    if st.button("Manage profile", key="drv_home_profile_btn", use_container_width=True):
                        st.session_state.driver_view = "profile"
                        st.rerun()

            st.markdown('<div class="card-title-bold" style="margin: 14px 0 8px 0;">Recent Completed Rides & Ratings</div>', unsafe_allow_html=True)
            if not past_rides:
                st.info("No completed or past rides yet.")
            else:
                for r in past_rides[:5]:
                    with st.container(border=True):
                        rc1, rc2 = st.columns([2.8, 1.4], vertical_alignment="center")
                        with rc1:
                            st.markdown(f'<div class="card-title-bold">Booking #{r[0]}: {r[3]} → {r[4]}</div>', unsafe_allow_html=True)
                            st.caption(f"Passenger: {r[1]} ({r[2]}) • {str(r[8])[:16]}")
                        with rc2:
                            st.markdown(f'<div class="big-price-highlight">₹{float(r[6]):,.2f}</div>', unsafe_allow_html=True)
                            st.markdown(f'<span class="status-pill">{r[7]}</span>', unsafe_allow_html=True)

    elif st.session_state.driver_view == "profile":
        st.markdown('<div class="section-heading">Manage Driver & Vehicle Profile</div>', unsafe_allow_html=True)
        if st.button("← Back to Driver Dashboard"):
            st.session_state.driver_view = "dashboard"
            st.rerun()

        categories = get_cab_categories()
        cat_map = {c[1]: c[0] for c in categories} if categories else {"Sedan": 1}
        cat_names = list(cat_map.keys())
        default_idx = cat_names.index(d["category"]) if d["category"] in cat_names else 0

        with st.container(border=True):
            u_name = st.text_input("Driver Full Name", value=d["name"])
            u_phone = st.text_input("Driver Phone Number (10 digits)", value=d["phone"])
            st.text_input("Driving License Number (Verified)", value=d["license_no"], disabled=True)
            u_plate = st.text_input("Cab Plate Number", value=d["plate_no"] or "")
            u_model = st.text_input("Cab Vehicle Model", value=d["model"] or "")
            u_cat_name = st.selectbox("Cab Category", cat_names, index=default_idx)

            if st.button("Save Profile Changes", type="primary"):
                if u_phone and (not u_phone.strip().isdigit() or len(u_phone.strip()) != 10):
                    st.error("Phone number must be exactly 10 digits.")
                else:
                    ok = update_driver_profile(
                        driver_id=d["id"],
                        full_name=u_name,
                        phone=u_phone,
                        plate_no=u_plate,
                        model=u_model,
                        category_id=cat_map[u_cat_name],
                    )
                    if ok:
                        st.session_state.driver["phone"] = u_phone.strip()
                        st.success("Driver and vehicle profile updated successfully!")
                        st.rerun()
                    else:
                        st.error("Phone number or number plate is already registered to another driver.")

    elif st.session_state.driver_view == "history":
        st.markdown('<div class="section-heading">Past Rides & Passenger Ratings</div>', unsafe_allow_html=True)
        if st.button("← Back to Driver Dashboard"):
            st.session_state.driver_view = "dashboard"
            st.rerun()

        if not past_rides:
            st.info("No past rides recorded yet.")
        else:
            for r in past_rides:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2.8, 1.3, 1.4], vertical_alignment="center")
                    with c1:
                        st.markdown(f'<div class="card-title-bold">Booking #{r[0]}: {r[3]} → {r[4]}</div>', unsafe_allow_html=True)
                        st.caption(f"Passenger: {r[1]} ({r[2]}) • {str(r[8])[:19]}")
                    with c2:
                        st.markdown(f'<div class="big-price-highlight">₹{float(r[6]):,.2f}</div>', unsafe_allow_html=True)
                        st.caption(f"Distance: {r[5]} km • Status: {r[7]}")
                    with c3:
                        if r[9]:
                            st.markdown(f'<div class="card-title-bold">★ {r[9]}/5</div>', unsafe_allow_html=True)
                            if r[10]:
                                st.caption(f'"{r[10]}"')
                        else:
                            st.caption("No rating submitted")


# ==========================================
# MAIN ROUTER
# ==========================================
if st.session_state.passenger:
    render_passenger_portal()
elif st.session_state.driver:
    render_driver_portal()
else:
    if st.session_state.auth_mode == "driver_auth":
        render_driver_auth()
    else:
        render_passenger_auth()
