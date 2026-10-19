import math
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
# GLOBAL CSS & SINGLE-LINE HTML HELPERS (PREVENTS RAW CODE BLOCKS)
# ==========================================
CAR_SVG = '<svg width="52" height="26" viewBox="0 0 64 32" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 20L14 9C15.2 6.8 17.5 5.5 20 5.5H44C46.5 5.5 48.8 6.8 50 9L56 20H8Z" fill="#111111"/><rect x="4" y="18" width="56" height="9" rx="4.5" fill="#000000"/><path d="M16 10H29V17H12L16 10Z" fill="#E2E8F0"/><path d="M33 10H46L50 17H33V10Z" fill="#E2E8F0"/><circle cx="16" cy="26" r="5" fill="#1E293B" stroke="#FFFFFF" stroke-width="2"/><circle cx="48" cy="26" r="5" fill="#1E293B" stroke="#FFFFFF" stroke-width="2"/></svg>'

def render_brand_logo(title_text, subtitle_text=None):
    html = f'<div class="brand-header">{CAR_SVG}<h1 class="brand-title">{title_text}</h1></div>'
    if subtitle_text:
        html += f'<div class="login-bold-tagline">{subtitle_text}</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_top_nav_logo(title_text):
    html = f'<div class="brand-header">{CAR_SVG}<span class="nav-title">{title_text}</span></div>'
    st.markdown(html, unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
.brand-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 4px;
}
.brand-title {
    font-size: 2.35rem;
    font-weight: 900;
    letter-spacing: -0.04em;
    color: #000000;
    margin: 0;
    line-height: 1.1;
}
.nav-title {
    font-size: 1.75rem;
    font-weight: 900;
    letter-spacing: -0.03em;
    color: #000000;
}
.login-bold-tagline {
    font-size: 1.25rem;
    font-weight: 800;
    color: #111111;
    letter-spacing: -0.02em;
    margin-top: 4px;
    margin-bottom: 20px;
}
.top-black-bar {
    background-color: #000000;
    color: #FFFFFF;
    padding: 16px 26px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 18px;
    margin-bottom: 26px;
    font-weight: 700;
}
.top-black-bar span.badge {
    background-color: #222222;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.88rem;
    font-weight: 700;
    color: #F8FAFC;
}
.section-heading {
    font-size: 2.0rem;
    font-weight: 900;
    letter-spacing: -0.03em;
    color: #000000;
    margin-bottom: 14px;
}
/* Make all buttons bold and override default red primary button with Uber Black */
div.stButton > button {
    font-weight: 800 !important;
    border-radius: 10px !important;
    padding: 0.55rem 1rem !important;
}
div.stButton > button[kind="primary"] {
    background-color: #000000 !important;
    color: #FFFFFF !important;
    border: 1px solid #000000 !important;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #222222 !important;
    border-color: #222222 !important;
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
    st.session_state.passenger_view = "ride"  # 'ride', 'activity', 'account'
if "driver_view" not in st.session_state:
    st.session_state.driver_view = "dashboard"  # 'dashboard', 'history', 'profile'
if "selected_ride_details" not in st.session_state:
    st.session_state.selected_ride_details = None
if "selected_driver_ride_details" not in st.session_state:
    st.session_state.selected_driver_ride_details = None
if "search_triggered" not in st.session_state:
    st.session_state.search_triggered = False


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
                st.markdown("### **What's your phone number?**")
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
                        st.error("Database connection error: Unable to reach Neon server. Please check your Wi-Fi/DNS or DATABASE_URL in db.py.")
            else:
                st.markdown("### **Create your Passenger Account**")
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
                                st.rerun()
                            else:
                                st.error("Phone number or email is already registered.")
                        except psycopg.OperationalError:
                            st.error("Database connection error: Unable to reach Neon server. Check your internet or db.py.")

        st.write("")
        if st.button("Driver Partner Login / Registration →", use_container_width=True):
            st.session_state.auth_mode = "driver_auth"
            st.rerun()


# ==========================================
# 2. SEPARATE DRIVER LOGIN / SIGNUP SCREEN
# ==========================================
def render_driver_auth():
    _, center_col, _ = st.columns([1.1, 1.8, 1.1])
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
                st.markdown("### **Driver Sign In**")
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
                st.markdown("### **Register as a Driver Partner**")
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
# 3. PASSENGER PORTAL
# ==========================================
def render_passenger_portal():
    p = st.session_state.passenger
    rides = get_passenger_rides(p["id"])
    active_count = sum(1 for r in rides if r[5] in ("REQUESTED", "ACCEPTED", "ONGOING"))

    h_col1, _, h_col3 = st.columns([3.5, 4.0, 1.5])
    with h_col1:
        render_top_nav_logo("Cab Booking")

    with h_col3:
        with st.popover(f"{p['name']} ⌄", use_container_width=True):
            st.markdown(f"### **{p['name']}**")
            st.caption(f"Phone: {p['phone']}")
            st.divider()
            if st.button("Manage account", use_container_width=True):
                st.session_state.passenger_view = "account"
                st.rerun()
            if st.button("Ride", use_container_width=True):
                st.session_state.passenger_view = "ride"
                st.rerun()
            if st.button("Activity", use_container_width=True):
                st.session_state.passenger_view = "activity"
                st.rerun()
            st.divider()
            if st.button("Logout", use_container_width=True):
                st.session_state.passenger = None
                st.session_state.selected_ride_details = None
                st.rerun()

    st.markdown(
        f'<div class="top-black-bar"><span style="font-size:1.08rem;">Welcome back, {p["name"]}</span>'
        f'<span class="badge">You have {active_count} active ride request(s)</span></div>',
        unsafe_allow_html=True,
    )

    if st.session_state.passenger_view == "ride":
        left_col, right_col = st.columns([1.05, 1.35], gap="large")

        with left_col:
            st.markdown('<div class="section-heading">Request a ride</div>', unsafe_allow_html=True)
            with st.container(border=True):
                location_list = sorted(list(LOCATIONS_COORDS.keys()))

                pickup_loc = st.selectbox(
                    "Pickup Location (Type e.g. 'ch' to search cities)",
                    options=location_list,
                    index=None,
                    placeholder="Type pickup city or landmark..."
                )
                drop_loc = st.selectbox(
                    "Destination Location (Type e.g. 'ba' or 'ch' to search)",
                    options=location_list,
                    index=None,
                    placeholder="Type destination city or landmark..."
                )

                calc_distance = 0.0
                if pickup_loc and drop_loc:
                    if pickup_loc == drop_loc:
                        st.warning("Pickup and destination cannot be the same location.")
                    else:
                        calc_distance = calculate_road_distance_km(pickup_loc, drop_loc)
                        st.info(f"**Estimated Road Distance:** {calc_distance} km")

                categories = get_cab_categories()
                cat_names = ["All Categories"] + [c[1] for c in categories]
                chosen_cat = st.selectbox("Filter Cab Category", cat_names)

                if st.button("See prices", type="primary", use_container_width=True):
                    if not pickup_loc or not drop_loc or pickup_loc == drop_loc:
                        st.error("Please select valid, distinct Pickup and Destination locations.")
                    else:
                        st.session_state.search_triggered = True

            if st.session_state.search_triggered and pickup_loc and drop_loc and pickup_loc != drop_loc:
                st.markdown("#### **Available Cabs Near You**")
                filter_arg = None if chosen_cat == "All Categories" else chosen_cat
                available_cabs = get_available_cabs(filter_arg)

                if not available_cabs:
                    st.warning("No available cabs found for this category right now.")
                else:
                    for cab in available_cabs:
                        cab_id, model, plate_no, type_name, base_fare, rate_km, seats, drv_name = cab
                        est_fare = round(float(base_fare) + (calc_distance * float(rate_km)), 2)

                        with st.container(border=True):
                            c1, c2, c3 = st.columns([2.2, 1.3, 1.2])
                            with c1:
                                st.markdown(f"**{type_name} • {model}** (`{plate_no}`)")
                                st.caption(f"Driver: **{drv_name}** | Seats: {seats}")
                            with c2:
                                st.markdown(f"### **₹{est_fare:,.2f}**")
                                st.caption(f"Base ₹{base_fare} + ₹{rate_km}/km")
                            with c3:
                                if st.button("Book Ride", key=f"book_{cab_id}", type="primary", use_container_width=True):
                                    res = book_ride(p["id"], cab_id, pickup_loc, drop_loc, calc_distance)
                                    if res:
                                        st.success(f"Ride Requested! Booking #{res[0]} (₹{float(res[1]):,.2f})")
                                        st.session_state.search_triggered = False
                                        st.rerun()
                                    else:
                                        st.error("Could not book ride. Cab may no longer be available.")

        with right_col:
            st.markdown('<div class="section-heading">Your account and activity</div>', unsafe_allow_html=True)

            with st.container(border=True):
                ac1, ac2 = st.columns([3, 1.3])
                with ac1:
                    st.markdown(f"**{p['name']}**  |  {p['phone']}  |  {p['email']}")
                with ac2:
                    if st.button("Manage account", key="home_manage_btn", use_container_width=True):
                        st.session_state.passenger_view = "account"
                        st.rerun()

            if st.session_state.selected_ride_details:
                sel = st.session_state.selected_ride_details
                with st.container(border=True):
                    st.markdown(f"#### **Ride Details — Booking #{sel[0]}**")
                    st.markdown(f"**Route:** {sel[1]} → {sel[2]}")
                    st.markdown(f"**Distance:** {sel[3]} km  |  **Total Fare:** ₹{float(sel[4]):,.2f}")
                    st.markdown(f"**Status:** `{sel[5]}`  |  **Booked At:** {str(sel[6])[:19]}")
                    st.markdown(f"**Vehicle:** {sel[7]} (`{sel[8]}`)  |  **Driver:** {sel[9]}")

                    b_col1, _, b_col3 = st.columns(3)
                    with b_col1:
                        if sel[5] == "REQUESTED":
                            if st.button("Cancel Ride", key=f"det_cancel_{sel[0]}", use_container_width=True):
                                cancel_ride(sel[0], p["id"])
                                st.session_state.selected_ride_details = None
                                st.rerun()
                        elif sel[5] == "CANCELLED":
                            if st.button("Delete Record", key=f"det_del_{sel[0]}", use_container_width=True):
                                delete_cancelled_ride(sel[0], p["id"])
                                st.session_state.selected_ride_details = None
                                st.rerun()
                    with b_col3:
                        if st.button("Close details", key="close_det_btn", use_container_width=True):
                            st.session_state.selected_ride_details = None
                            st.rerun()

            st.markdown("#### **Recent & Past Trips**")
            if not rides:
                st.info("No trips booked yet. Use the form on the left to request your first ride!")
            else:
                for r in rides[:5]:
                    with st.container(border=True):
                        rc1, rc2, rc3 = st.columns([2.6, 1.2, 1.2])
                        with rc1:
                            st.markdown(f"**{r[2]}**")
                            st.caption(f"From: {r[1]} • {str(r[6])[:16]}")
                        with rc2:
                            st.markdown(f"**₹{float(r[4]):,.2f}**")
                            st.caption(f"Status: **{r[5]}**")
                        with rc3:
                            if st.button("See details", key=f"home_detail_{r[0]}", use_container_width=True):
                                st.session_state.selected_ride_details = r
                                st.rerun()

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
                    c1, c2, c3 = st.columns([3, 1.5, 1.5])
                    with c1:
                        st.markdown(f"#### **Booking #{r[0]}: {r[1]} → {r[2]}**")
                        st.caption(f"Booked on {str(r[6])[:19]} | Cab: {r[7]} ({r[8]}) | Driver: {r[9]}")
                    with c2:
                        st.markdown(f"### **₹{float(r[4]):,.2f}**")
                        st.markdown(f"Distance: **{r[3]} km** | Status: `{r[5]}`")
                    with c3:
                        if r[5] == "REQUESTED":
                            if st.button("Cancel Ride", key=f"act_can_{r[0]}", use_container_width=True):
                                cancel_ride(r[0], p["id"])
                                st.rerun()
                        elif r[5] == "CANCELLED":
                            if st.button("Delete Cancelled Ride", key=f"act_del_{r[0]}", use_container_width=True):
                                delete_cancelled_ride(r[0], p["id"])
                                st.rerun()

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
# 4. REDESIGNED DRIVER PORTAL (MATCHES PASSENGER PORTAL)
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
    past_rides = [r for r in all_driver_rides if r[7] in ("COMPLETED", "CANCELLED")]

    # Top Header Bar with Driver Popover Menu (Matches Passenger Header)
    h_col1, _, h_col3 = st.columns([3.5, 4.0, 1.5])
    with h_col1:
        render_top_nav_logo("Cab Booking • Driver")

    with h_col3:
        with st.popover(f"{d['name']} ⌄", use_container_width=True):
            st.markdown(f"### **{d['name']}**")
            st.caption(f"Rating: ★ {avg_rating:.2f} ({total_reviews} reviews)")
            st.caption(f"Vehicle: {d['model']} ({d['plate_no']})")
            st.divider()
            if st.button("Manage profile", use_container_width=True):
                st.session_state.driver_view = "profile"
                st.rerun()
            if st.button("Dashboard", use_container_width=True):
                st.session_state.driver_view = "dashboard"
                st.rerun()
            if st.button("Past rides & ratings", use_container_width=True):
                st.session_state.driver_view = "history"
                st.rerun()
            st.divider()
            if st.button("Logout", use_container_width=True):
                st.session_state.driver = None
                st.session_state.selected_driver_ride_details = None
                st.rerun()

    # Sleek Black Summary Bar
    st.markdown(
        f'<div class="top-black-bar">'
        f'<span style="font-size:1.08rem;">Welcome back, {d["name"]}</span>'
        f'<span class="badge">Status: {d["status"]}</span>'
        f'<span class="badge">★ {avg_rating:.2f} ({total_reviews} reviews)</span>'
        f'<span class="badge">{d["model"]} ({d["plate_no"]}) • {d["category"]}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ---- VIEW A: DRIVER HOME DASHBOARD (2-COLUMN PREMIUM LAYOUT) ----
    if st.session_state.driver_view == "dashboard":
        left_col, right_col = st.columns([1.05, 1.35], gap="large")

        # Left Column: Shift Control + Active Ride Requests
        with left_col:
            st.markdown('<div class="section-heading">Shift & Dispatch</div>', unsafe_allow_html=True)

            with st.container(border=True):
                st.markdown(f"#### **Current Availability: `{d['status']}`**")
                st.caption("Go Online to appear in passenger cab searches and receive live booking requests.")
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
                if on_trip:
                    st.caption("You are on a trip. Complete it to change your availability.")

            st.markdown("#### **Incoming & Active Ride Requests**")
            if not active_rides:
                with st.container(border=True):
                    st.info("No active ride requests right now. Stay AVAILABLE to receive bookings.")
            else:
                for r in active_rides:
                    # (booking_id, passenger_name, passenger_phone, pickup, drop, distance, fare, status, time, rating, comment)
                    with st.container(border=True):
                        st.markdown(f"#### **Booking #{r[0]} — {r[1]}** (`{r[2]}`)")
                        st.markdown(f"**Pickup:** {r[3]}  \n**Drop-off:** {r[4]}")
                        st.markdown(f"**Distance:** {r[5]} km  |  **Fare:** ₹{float(r[6]):,.2f}  |  **Status:** `{r[7]}`")
                        st.caption(f"Requested at {str(r[8])[:19]}")

                        if r[7] == "REQUESTED":
                            col_a, col_b = st.columns(2)
                            with col_a:
                                if st.button("Accept Ride", key=f"drv_acc_{r[0]}", type="primary", use_container_width=True, disabled=(d["status"] == "ON_TRIP")):
                                    driver_update_ride_status(r[0], d["id"], "ACCEPTED")
                                    st.rerun()
                            with col_b:
                                if st.button("Decline & Pass", key=f"drv_dec_{r[0]}", use_container_width=True):
                                    outcome = reassign_ride_to_next_driver(r[0], d["id"])
                                    if outcome == "REASSIGNED":
                                        st.toast("Ride declined and passed to the next available driver.")
                                    else:
                                        st.toast("Ride declined. No other driver available, so it was cancelled.")
                                    st.rerun()
                        elif r[7] == "ACCEPTED":
                            if st.button("Start Trip (ONGOING)", key=f"drv_start_{r[0]}", type="primary", use_container_width=True):
                                driver_update_ride_status(r[0], d["id"], "ONGOING")
                                st.rerun()
                        elif r[7] == "ONGOING":
                            if st.button("Complete Trip", key=f"drv_comp_{r[0]}", type="primary", use_container_width=True):
                                driver_update_ride_status(r[0], d["id"], "COMPLETED")
                                st.rerun()

        # Right Column: Driver Account Summary + Past Rides & Ratings (Matches Passenger Home Screen)
        with right_col:
            st.markdown('<div class="section-heading">Your profile and activity</div>', unsafe_allow_html=True)

            # Quick Profile & Vehicle Card with "Manage profile" button
            with st.container(border=True):
                dc1, dc2 = st.columns([3.1, 1.3])
                with dc1:
                    st.markdown(f"**{d['name']}**  |  Phone: `{d['phone']}`  |  License: `{d['license_no']}`")
                    st.caption(f"Assigned Cab: **{d['model']}** (`{d['plate_no']}`) • Category: **{d['category']}** • Rating: **★ {avg_rating:.2f}**")
                with dc2:
                    if st.button("Manage profile", key="drv_home_profile_btn", use_container_width=True):
                        st.session_state.driver_view = "profile"
                        st.rerun()

            # Selected Past Ride Details Box
            if st.session_state.selected_driver_ride_details:
                sel = st.session_state.selected_driver_ride_details
                with st.container(border=True):
                    st.markdown(f"#### **Trip Summary — Booking #{sel[0]}**")
                    st.markdown(f"**Passenger:** {sel[1]} (Phone: `{sel[2]}`)")
                    st.markdown(f"**Route:** {sel[3]} → {sel[4]}")
                    st.markdown(f"**Distance:** {sel[5]} km  |  **Total Fare:** ₹{float(sel[6]):,.2f}  |  **Status:** `{sel[7]}`")
                    if sel[9]:
                        st.markdown(f"**Passenger Rating:** ★ {sel[9]}/5  |  **Review:** {sel[10] or 'No written comment'}")
                    else:
                        st.caption("No passenger rating submitted for this trip yet.")
                    if st.button("Close details", key="close_drv_det"):
                        st.session_state.selected_driver_ride_details = None
                        st.rerun()

            st.markdown("#### **Recent Completed Rides & Ratings**")
            if not past_rides:
                st.info("No completed or past rides yet.")
            else:
                for r in past_rides[:5]:
                    with st.container(border=True):
                        rc1, rc2, rc3 = st.columns([2.5, 1.3, 1.2])
                        with rc1:
                            st.markdown(f"**{r[4]}**")
                            st.caption(f"From: {r[3]} • Passenger: {r[1]}")
                        with rc2:
                            st.markdown(f"**₹{float(r[6]):,.2f}**")
                            rating_str = f"★ {r[9]}/5" if r[9] else r[7]
                            st.caption(f"{rating_str}")
                        with rc3:
                            if st.button("See details", key=f"drv_det_{r[0]}", use_container_width=True):
                                st.session_state.selected_driver_ride_details = r
                                st.rerun()

    # ---- VIEW B: SEPARATE DRIVER PROFILE PAGE (MATCHES PASSENGER MANAGE ACCOUNT) ----
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
            st.markdown("#### **Personal & Cab Details**")
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

    # ---- VIEW C: FULL DRIVER PAST RIDES & RATINGS PAGE ----
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
                    c1, c2, c3 = st.columns([2.8, 1.3, 1.4])
                    with c1:
                        st.markdown(f"#### **Booking #{r[0]}: {r[3]} → {r[4]}**")
                        st.caption(f"Passenger: {r[1]} ({r[2]}) • {str(r[8])[:19]}")
                    with c2:
                        st.markdown(f"### **₹{float(r[6]):,.2f}**")
                        st.caption(f"Distance: {r[5]} km • Status: {r[7]}")
                    with c3:
                        if r[9]:
                            st.markdown(f"**Rating: ★ {r[9]}/5**")
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