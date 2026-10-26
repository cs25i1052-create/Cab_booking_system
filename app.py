"""
Cab Booking - Streamlit front end.

Behaviour (session state, routing, validation, database calls) is the same as before.
All presentation lives in ui.py: theme CSS, SVG artwork and HTML components.

Files   app.py (this file) + ui.py (theme/components) + .streamlit/config.toml (optional light theme)
Needs   Streamlit 1.39+ for the full styling (tested on 1.41 and 1.66):  pip install -U streamlit
"""
import math
import random

import psycopg
import streamlit as st

import ui
from ui import esc, icon, md, money_html, panel

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

st.set_page_config(page_title="Cab Booking", page_icon=ui.favicon(), layout="wide", initial_sidebar_state="collapsed")
ui.inject_css()

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

ACTIVE_STATUSES = ("REQUESTED", "ACCEPTED", "ONGOING")
DB_DOWN = "Database connection error: Unable to reach Neon server."


# ==========================================
# SMALL UI HELPERS
# ==========================================
def page_head(title, back_label, back_key, on_back, trailing=None):
    """Back link, page title and an optional trailing action (e.g. Refresh)."""
    with panel("pagehead"):
        if st.button(back_label, key=f"back_{back_key}"):
            on_back()
            st.rerun()
        ui.heading(title)
        if trailing:
            trailing()


def flash(message):
    """Queue a toast for the next run (a toast raised right before st.rerun() is discarded by the rerun)."""
    st.session_state["_flash"] = message


def person_html(name, sub_items, size=48):
    subs = "".join(f"<span>{ic}{esc(txt)}</span>" for ic, txt in sub_items)
    return (
        f'<div class="person">{ui.avatar(name, size)}'
        f'<div style="min-width:0"><div class="person-name">{esc(name)}</div><div class="person-sub">{subs}</div></div></div>'
    )


def ride_alerts(rides):
    """Red banner for every booking that ended with NO_DRIVERS."""
    for ur in [r for r in rides if r[5] == "NO_DRIVERS"]:
        ui.notice("error", f"Booking #{ur[0]} ({ur[1]} → {ur[2]}) could not be fulfilled because all drivers were busy.", title="Ride Alert:")


def trip_meta(*items):
    return '<div class="trip-meta">' + "".join(f"<span>{i}</span>" for i in items) + "</div>"


# ==========================================
# 1. PASSENGER LOGIN / SIGNUP SCREEN
# ==========================================
def render_passenger_auth():
    with panel("auth"):
        hero_col, form_col = st.columns([1.12, 1], gap="small")
        with hero_col:
            ui.auth_hero("Move anywhere. Boldly and reliably.")

        with form_col:
            with panel("auth_card"):
                md(
                    f'<div class="auth-mbrand">{ui.brand(on_dark=False)}'
                    f'<div class="auth-sub" style="margin-top:14px">Move anywhere. Boldly and reliably.</div></div>'
                )

                tab_mode = st.radio(
                    "Auth Mode",
                    ["Log In", "Sign Up"],
                    horizontal=True,
                    label_visibility="collapsed"
                )

                if tab_mode == "Log In":
                    md("<div class=\"auth-title\" role=\"heading\" aria-level=\"1\">What's your phone number?</div>")
                    phone = st.text_input("10-digit mobile number", placeholder="Enter your registered phone number")
                    if st.button("Continue", type="primary", use_container_width=True, key="cta_login"):
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
                                ui.notice("error", "Phone number not found. Please Sign Up first.")
                        except psycopg.OperationalError:
                            ui.notice("error", DB_DOWN)
                else:
                    md('<div class="auth-title" role="heading" aria-level="1">Create your Passenger Account</div>')
                    full_name = st.text_input("Full Name", placeholder="Enter your full name")
                    phone = st.text_input("10-digit Mobile Number", placeholder="e.g. 9876543210")
                    email = st.text_input("Email Address", placeholder="name@example.com")
                    if st.button("Continue", type="primary", use_container_width=True, key="cta_signup"):
                        if not full_name.strip() or not phone.strip() or not email.strip():
                            ui.notice("error", "All fields are required.")
                        elif not phone.strip().isdigit() or len(phone.strip()) != 10:
                            ui.notice("error", "Phone number must be exactly 10 digits.")
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
                                    ui.notice("error", "Phone number or email is already registered.")
                            except psycopg.OperationalError:
                                ui.notice("error", DB_DOWN)

                md('<div class="or-rule">or</div>')
                if st.button("Driver Partner Login / Registration", use_container_width=True, key="alt_to_driver"):
                    st.session_state.auth_mode = "driver_auth"
                    st.rerun()


# ==========================================
# 2. SEPARATE DRIVER LOGIN / SIGNUP SCREEN
# ==========================================
def render_driver_auth():
    with panel("auth"):
        hero_col, form_col = st.columns([1.12, 1], gap="small")
        with hero_col:
            ui.auth_hero("Drive when you want. Earn on your terms.", tag="Driver Partner")

        with form_col:
            with panel("auth_card"):
                md(
                    f'<div class="auth-mbrand">{ui.brand("Driver Partner", on_dark=False)}'
                    f'<div class="auth-sub" style="margin-top:14px">Drive when you want. Earn on your terms.</div></div>'
                )

                d_mode = st.radio(
                    "Driver Auth Mode",
                    ["Driver Log In", "Driver Sign Up"],
                    horizontal=True,
                    label_visibility="collapsed"
                )

                if d_mode == "Driver Log In":
                    md('<div class="auth-title" role="heading" aria-level="1">Driver Sign In</div>')
                    d_phone = st.text_input("Registered 10-digit Driver Phone Number", placeholder="Enter 10-digit phone number")
                    if st.button("Continue to Driver Portal", type="primary", use_container_width=True, key="cta_driver_login"):
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
                                ui.notice("error", "Driver account not found. Please Sign Up first.")
                        except psycopg.OperationalError:
                            ui.notice("error", DB_DOWN)
                else:
                    md('<div class="auth-title" role="heading" aria-level="1">Register as a Driver Partner</div>')
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

                    if st.button("Register & Open Driver Portal", type="primary", use_container_width=True, key="cta_driver_signup"):
                        if not all([d_name.strip(), d_phone.strip(), d_license.strip(), c_plate.strip(), c_model.strip()]):
                            ui.notice("error", "Please fill in all driver and vehicle details.")
                        elif not d_phone.strip().isdigit() or len(d_phone.strip()) != 10:
                            ui.notice("error", "Phone number must be exactly 10 digits.")
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
                                ui.notice("error", "Phone number, license number, or plate number already exists.")

                md('<div class="or-rule">or</div>')
                if st.button("Back to Passenger Login", use_container_width=True, key="alt_to_passenger"):
                    st.session_state.auth_mode = "passenger_auth"
                    st.rerun()


# ==========================================
# 3. PASSENGER PORTAL (MULTI-PAGE FLOW)
# ==========================================
def render_passenger_portal():
    p = st.session_state.passenger
    rides = get_passenger_rides(p["id"])
    active_rides = [r for r in rides if r[5] in ACTIVE_STATUSES]
    active_count = len(active_rides)
    view = st.session_state.passenger_view

    # ---------- Top navigation: brand, tabs, profile menu ----------
    tabs = [("ride", "Ride")]
    if active_rides:
        tabs.append(("live", "Live ride"))
    tabs += [("activity", "Activity"), ("account", "Account")]
    current_tab = {
        "ride": "ride",
        "select_category": "ride",
        "ride_progress": "live" if active_rides else "ride",
        "activity": "activity",
        "account": "account",
    }.get(view, "ride")

    with panel("appbar"):
        md(ui.brand())
        with panel("appnav"):
            for tab_id, label in tabs:
                if st.button(label, key=f"{'navon' if tab_id == current_tab else 'nav'}_{tab_id}"):
                    if tab_id == "live":
                        st.session_state.active_booking_id = active_rides[0][0]
                        st.session_state.passenger_view = "ride_progress"
                    else:
                        st.session_state.passenger_view = {"ride": "ride", "activity": "activity", "account": "account"}[tab_id]
                    st.rerun()

        with st.popover(p["name"]):
            md(
                f'<div class="menu-head">{ui.avatar(p["name"], 46)}<div><div class="menu-name">{esc(p["name"])}</div>'
                f'<div class="menu-sub">Phone: {esc(p["phone"])}</div></div></div><div class="menu-sep"></div>'
            )
            if st.button("Ride Home", use_container_width=True, key="menu_home"):
                st.session_state.passenger_view = "ride"
                st.rerun()
            if active_rides:
                if st.button("Live Ride Progress", use_container_width=True, key="menu_live"):
                    st.session_state.active_booking_id = active_rides[0][0]
                    st.session_state.passenger_view = "ride_progress"
                    st.rerun()
            if st.button("Activity & Past Trips", use_container_width=True, key="menu_activity"):
                st.session_state.passenger_view = "activity"
                st.rerun()
            if st.button("Manage Account", use_container_width=True, key="menu_account"):
                st.session_state.passenger_view = "account"
                st.rerun()
            md('<div class="menu-sep"></div>')
            if st.button("Logout", use_container_width=True, key="menu_logout"):
                st.session_state.passenger = None
                st.session_state.selected_ride_details = None
                st.session_state.booking_draft = None
                st.session_state.active_booking_id = None
                st.rerun()

    with panel("page"):
        if view == "ride":
            live_chip = (
                f'<span class="chip chip--live"><i class="chip-dot"></i>You have {active_count} active ride request(s)</span>'
                if active_count
                else f'<span class="chip chip--plain">You have {active_count} active ride request(s)</span>'
            )
            md(
                f'<div class="greet"><div class="h1" role="heading" aria-level="1">Welcome back, {esc(p["name"])}</div>'
                f'<div class="chips">{live_chip}</div></div>'
            )
            ride_alerts(rides)

        # =================================-------------------------
        # PAGE A: HOME SCREEN (Select Route & Click "See prices")
        # =================================-------------------------
        if view == "ride":
            if active_rides:
                latest_active = active_rides[0]
                with panel("panel_active"):
                    a1, a2 = st.columns([3, 1.25], vertical_alignment="center")
                    with a1:
                        md(
                            f'<div class="on-dark"><div class="inline" style="margin-bottom:14px">'
                            f'<span class="h4">Active Ride #{latest_active[0]}</span>{ui.chip(latest_active[5], True)}</div>'
                            f'{ui.stops(latest_active[1], latest_active[2], True)}</div>'
                        )
                    with a2:
                        if st.button("Open Live Ride Progress Bar", type="primary", use_container_width=True, key="open_live"):
                            st.session_state.active_booking_id = latest_active[0]
                            st.session_state.passenger_view = "ride_progress"
                            st.rerun()

            left_col, right_col = st.columns([1, 1.2], gap="large")

            with left_col:
                with panel("panel_request"):
                    ui.heading("Request a ride")
                    location_list = sorted(list(LOCATIONS_COORDS.keys()))

                    with panel("fields_route"):
                        pickup_loc = st.selectbox(
                            "Pickup Location",
                            options=location_list,
                            index=None,
                            placeholder="Pickup city or landmark",
                            label_visibility="collapsed",
                        )
                        drop_loc = st.selectbox(
                            "Destination Location",
                            options=location_list,
                            index=None,
                            placeholder="Destination city or landmark",
                            label_visibility="collapsed",
                        )

                    calc_distance = 0.0
                    if pickup_loc and drop_loc:
                        if pickup_loc == drop_loc:
                            ui.notice("warn", "Pickup and destination cannot be the same location.")
                        else:
                            calc_distance = calculate_road_distance_km(pickup_loc, drop_loc)
                            md(
                                f'<div class="dist"><span class="dist-l">{icon("route", 18)}Estimated Road Distance</span>'
                                f'<span class="dist-v">{calc_distance} km</span></div>'
                            )

                    if st.button("See prices", type="primary", use_container_width=True, key="cta_prices"):
                        if not pickup_loc or not drop_loc or pickup_loc == drop_loc:
                            ui.notice("error", "Please select valid, distinct Pickup and Destination locations.")
                        else:
                            st.session_state.booking_draft = {
                                "pickup": pickup_loc,
                                "drop": drop_loc,
                                "distance": calc_distance,
                            }
                            st.session_state.passenger_view = "select_category"
                            st.rerun()

                route_ok = bool(pickup_loc and drop_loc and pickup_loc != drop_loc)
                ui.route_card(
                    LOCATIONS_COORDS[pickup_loc] if route_ok else None,
                    LOCATIONS_COORDS[drop_loc] if route_ok else None,
                    pickup_loc or "", drop_loc or "",
                    km=calc_distance if route_ok else None,
                    uid="home",
                )

            with right_col:
                ui.heading("Your account and activity", 3)

                with panel("panel_account"):
                    ac1, ac2 = st.columns([3, 1.45], vertical_alignment="center")
                    with ac1:
                        md(person_html(p["name"], [(icon("phone", 15), p["phone"]), (icon("mail", 15), p["email"])]))
                    with ac2:
                        if st.button("Manage account", key="home_manage_btn", use_container_width=True):
                            st.session_state.passenger_view = "account"
                            st.rerun()

                ui.heading("Recent & Past Trips", 3)
                if not rides:
                    ui.empty("No trips booked yet", "Use the form on the left to request your first ride!", "car")
                else:
                    for r in rides[:4]:
                        with panel(f"row_home_{r[0]}"):
                            rc1, rc2, rc3 = st.columns([2.7, 1.2, 1.35], vertical_alignment="center")
                            with rc1:
                                md(ui.stops(r[1], r[2], True) + trip_meta(f"Booking #{r[0]}", ui.fmt_dt(r[6])))
                            with rc2:
                                md(f'<div class="trip-price">{money_html(r[4], "sm")}{ui.chip(r[5], True)}</div>')
                            with rc3:
                                if r[5] in ACTIVE_STATUSES:
                                    if st.button("Track Ride", key=f"trk_{r[0]}", type="primary", use_container_width=True):
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
        elif view == "select_category":
            draft = st.session_state.booking_draft
            if not draft:
                st.session_state.passenger_view = "ride"
                st.rerun()

            def _back_to_route():
                st.session_state.passenger_view = "ride"

            page_head("Choose a Cab Category", "Change Route", "route", _back_to_route)

            all_categories = get_cab_categories()
            available_cabs = get_available_cabs()

            cabs_by_cat = {}
            seats_by_cat = {}
            for cab in available_cabs:
                c_type = cab[3]
                cabs_by_cat.setdefault(c_type, []).append(cab)
                seats_by_cat[c_type] = cab[6]

            list_col, summary_col = st.columns([1.6, 1], gap="large")

            with summary_col:
                ui.route_card(
                    LOCATIONS_COORDS.get(draft["pickup"]), LOCATIONS_COORDS.get(draft["drop"]),
                    draft["pickup"], draft["drop"], km=draft["distance"], uid="summary",
                )
                with panel("panel_summary"):
                    ui.heading("Trip summary", 4)
                    md(ui.stops(draft["pickup"], draft["drop"]))
                    md(
                        f'<div class="dist"><span class="dist-l">{icon("route", 18)}Road Distance</span>'
                        f'<span class="dist-v">{draft["distance"]} km</span></div>'
                    )

            with list_col:
                if not all_categories:
                    ui.notice("warn", "No cab categories configured in the database.")
                else:
                    fares = [round(float(c[2]) + (draft["distance"] * float(c[3])), 2) for c in all_categories]
                    lowest = min(fares)
                    for cat_row in all_categories:
                        cat_id, type_name, base_fare, rate_km = cat_row
                        est_fare = round(float(base_fare) + (draft["distance"] * float(rate_km)), 2)
                        matching_cabs = cabs_by_cat.get(type_name, [])
                        seats = seats_by_cat.get(type_name, 4)
                        online = len(matching_cabs)
                        online_txt = f"{online} {'driver' if online == 1 else 'drivers'} online" if online else '<b class="cat-off">No drivers online</b>'
                        tag = '<span class="chip chip--sm chip--completed">Lowest fare</span>' if (len(fares) > 1 and est_fare == lowest) else ""
                        select_error = None

                        with panel(f"cat_{cat_id}"):
                            c1, c2, c3 = st.columns([3.3, 1.5, 1.1], vertical_alignment="center")
                            with c1:
                                md(
                                    f'<div class="cat"><div class="cat-ic">{ui.car_svg(ui.car_kind(type_name), 104)}</div>'
                                    f'<div style="min-width:0"><div class="cat-name">{esc(type_name)}{tag}</div>'
                                    f'<div class="cat-meta"><span>{icon("user", 15)}Up to {seats} Seats</span><span>{online_txt}</span></div>'
                                    f'<div class="cat-meta" style="margin-top:2px">Base ₹{float(base_fare):.0f} + ₹{float(rate_km):.0f}/km</div></div></div>'
                                )
                            with c2:
                                md(f'<div class="cat-fare">{money_html(est_fare, "md")}<div class="meta">Total Estimated Fare</div></div>')
                            with c3:
                                if st.button("Select", key=f"sel_cat_{cat_id}", type="primary", use_container_width=True, help=f"Book a {type_name}"):
                                    if not matching_cabs:
                                        select_error = f"No drivers are currently online in {type_name}. Please select another category."
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
                                            select_error = "Could not complete booking. Please try again."
                            if select_error:
                                ui.notice("error", select_error)

        # =================================-------------------------
        # PAGE C: DEDICATED LIVE RIDE PROGRESS BAR PAGE
        # =================================-------------------------
        elif view == "ride_progress":
            def _back_home():
                st.session_state.passenger_view = "ride"

            def _refresh():
                if st.button("Refresh Status", type="primary", use_container_width=True, key="refresh_status"):
                    st.rerun()

            page_head("Live Ride Progress", "Back to Home", "home", _back_home, trailing=_refresh)
            ride_alerts(rides)

            target_ride = None
            if st.session_state.active_booking_id:
                for r in rides:
                    if r[0] == st.session_state.active_booking_id:
                        target_ride = r
                        break
            if not target_ride and rides:
                target_ride = rides[0]

            if not target_ride:
                ui.empty("No active ride found.", icon_name="car")
            else:
                b_id, pickup, drop, dist, fare, status, b_time, model, plate, driver_name = target_ride

                tracker_col, detail_col = st.columns([1.5, 1], gap="large")

                with tracker_col:
                    ui.tracker(status)

                    with panel("panel_driver"):
                        if status == "REQUESTED":
                            md(
                                f'<div class="inline"><span class="chip chip--live"><i class="chip-dot"></i>Contacting Driver...</span></div>'
                                f'<div class="meta" style="margin-top:10px">Currently pinging nearby driver: <b>{esc(driver_name)}</b>. '
                                f'If declined, another available driver in your category will be contacted automatically.</div>'
                            )
                        elif status in ("ACCEPTED", "ONGOING", "COMPLETED"):
                            md(
                                '<div class="stack">'
                                f'<div class="vehicle">{ui.avatar(driver_name, 54)}<div style="min-width:0">'
                                f'<div class="lbl">Assigned Driver</div><div class="person-name">{esc(driver_name)}</div></div></div>'
                                + ui.kv([("Vehicle", esc(model)), ("Plate", ui.plate(plate))])
                                + '</div>'
                            )
                        elif status == "NO_DRIVERS":
                            ui.notice("error", "All drivers in this category were unavailable or declined the request.")
                        elif status == "CANCELLED":
                            ui.notice("warn", "This booking was cancelled.")

                with detail_col:
                    progress = {"ACCEPTED": 0.2, "ONGOING": 0.5, "COMPLETED": 0.8}.get(status)
                    ui.route_card(
                        LOCATIONS_COORDS.get(pickup), LOCATIONS_COORDS.get(drop), pickup, drop,
                        progress=progress, searching=(status == "REQUESTED"), uid=f"ride{b_id}",
                    )
                    with panel("panel_trip"):
                        md(
                            '<div class="stack">'
                            f'<div class="inline inline--between"><div class="h3">Booking #{b_id}</div>{ui.chip(status)}</div>'
                            + ui.stops(pickup, drop)
                            + ui.kv([("Distance", f"{esc(dist)} km"), ("Booked at", ui.fmt_dt(b_time, seconds=True))])
                            + f'<div class="fare-block" style="text-align:left"><div class="meta">Total Ride Fare</div>{money_html(fare, "lg")}</div>'
                            '</div>'
                        )
                        if status == "REQUESTED":
                            if st.button("Cancel Ride Request", use_container_width=True, key="cancel_request"):
                                cancel_ride(b_id, p["id"])
                                st.rerun()
                        elif status in ("CANCELLED", "NO_DRIVERS"):
                            if st.button("Delete Cancelled Record", use_container_width=True, key="delete_record"):
                                delete_cancelled_ride(b_id, p["id"])
                                st.session_state.passenger_view = "ride"
                                st.rerun()

        # =================================-------------------------
        # PAGE D: ACTIVITY & PAST TRIPS
        # =================================-------------------------
        elif view == "activity":
            def _back_home():
                st.session_state.passenger_view = "ride"

            with panel("narrow"):
                page_head("Activity & Past Trips", "Back to Home", "activity", _back_home)
                ride_alerts(rides)
                if not rides:
                    ui.empty("You have no recorded trips.", icon_name="car")
                else:
                    for r in rides:
                        with panel(f"row_act_{r[0]}"):
                            c1, c2, c3 = st.columns([3, 1.35, 1.5], vertical_alignment="center")
                            with c1:
                                md(
                                    ui.stops(r[1], r[2], True)
                                    + trip_meta(
                                        f"Booking #{r[0]}",
                                        f"Booked on {ui.fmt_dt(r[6])}",
                                        f"Cab: {esc(r[7])} ({esc(r[8])})",
                                        f"Driver: {esc(r[9])}",
                                    )
                                )
                            with c2:
                                md(
                                    f'<div class="trip-price">{money_html(r[4], "sm")}{ui.chip(r[5], True)}'
                                    f'<span class="meta">Distance: {esc(r[3])} km</span></div>'
                                )
                            with c3:
                                if r[5] in ACTIVE_STATUSES:
                                    if st.button("View Progress Bar", key=f"act_prog_{r[0]}", type="primary", use_container_width=True):
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
        elif view == "account":
            def _back_home():
                st.session_state.passenger_view = "ride"

            with panel("narrow-sm"):
                page_head("Manage Account", "Back to Home", "account", _back_home)
                with panel("panel_form"):
                    since = p.get("created_at")
                    since_txt = f"Member since {since.strftime('%B %Y')}" if hasattr(since, "strftime") else "Passenger account"
                    md(
                        f'<div class="person">{ui.avatar(p["name"], 56)}<div><div class="person-name">{esc(p["name"])}</div>'
                        f'<div class="person-sub"><span>{esc(since_txt)}</span></div></div></div>'
                    )
                    new_name = st.text_input("Full Name", value=p["name"])
                    new_phone = st.text_input("Phone Number (10 digits)", value=p["phone"])
                    new_email = st.text_input("Email Address", value=p["email"] or "")

                    if st.button("Save Changes", type="primary", use_container_width=True, key="cta_save_account"):
                        updated = update_passenger_details(p["id"], new_name, new_phone, new_email)
                        if updated:
                            st.session_state.passenger["name"] = updated[1]
                            st.session_state.passenger["phone"] = updated[2]
                            st.session_state.passenger["email"] = updated[3]
                            flash("Profile updated successfully!")
                            st.rerun()
                        else:
                            ui.notice("error", "Could not update profile. Check phone format or duplicate credentials.")


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

    active_rides = [r for r in all_driver_rides if r[7] in ACTIVE_STATUSES]
    past_rides = [r for r in all_driver_rides if r[7] in ("COMPLETED", "CANCELLED", "NO_DRIVERS")]
    view = st.session_state.driver_view

    # ---------- Top navigation: brand, tabs, profile menu ----------
    tabs = [("dashboard", "Dashboard"), ("profile", "Profile"), ("history", "History")]
    with panel("appbar"):
        md(ui.brand("Driver"))
        with panel("appnav"):
            for tab_id, label in tabs:
                if st.button(label, key=f"{'navon' if tab_id == view else 'nav'}_{tab_id}"):
                    st.session_state.driver_view = tab_id
                    st.rerun()

        with st.popover(d["name"]):
            md(
                f'<div class="menu-head">{ui.avatar(d["name"], 46)}<div><div class="menu-name">{esc(d["name"])}</div>'
                f'<div class="menu-sub">Rating: ★ {avg_rating:.2f} ({total_reviews} reviews)</div>'
                f'<div class="menu-sub">Vehicle: {esc(d["model"])} ({esc(d["plate_no"])})</div></div></div><div class="menu-sep"></div>'
            )
            if st.button("Dashboard", use_container_width=True, key="menu_dashboard"):
                st.session_state.driver_view = "dashboard"
                st.rerun()
            if st.button("Manage Profile", use_container_width=True, key="menu_profile"):
                st.session_state.driver_view = "profile"
                st.rerun()
            if st.button("Past Rides & Ratings", use_container_width=True, key="menu_history"):
                st.session_state.driver_view = "history"
                st.rerun()
            md('<div class="menu-sep"></div>')
            if st.button("Logout", use_container_width=True, key="menu_logout_driver"):
                st.session_state.driver = None
                st.session_state.selected_driver_ride_details = None
                st.rerun()

    with panel("page"):
        if view == "dashboard":
            md(
                f'<div class="greet"><div class="h1" role="heading" aria-level="1">Welcome back, {esc(d["name"])}</div>'
                f'<div class="chips">{ui.chip(d["status"])}'
                f'<span class="chip chip--plain">{icon("star", 14, fill=True, sw=1.5)}{avg_rating:.2f} ({total_reviews} reviews)</span>'
                f'<span class="chip chip--plain">{icon("car", 16)}{esc(d["model"])} ({esc(d["plate_no"])}) • {esc(d["category"])}</span>'
                f'</div></div>'
            )

        if view == "dashboard":
            left_col, right_col = st.columns([1.05, 1.35], gap="large")

            with left_col:
                ui.heading("Shift & Dispatch", 3)

                with panel("panel_shift"):
                    dot = {"AVAILABLE": "available", "ON_TRIP": "on-trip"}.get(d["status"], "")
                    md(
                        f'<div class="lbl" style="margin-bottom:10px">Current Availability</div>'
                        f'<div class="shift"><span class="shift-dot {dot}"></span><span class="shift-t">{esc(ui.status_label(d["status"]))}</span></div>'
                        f'<div class="meta" style="margin-top:10px">Go Online to receive random category dispatch requests from passengers.</div>'
                    )
                    on_trip = d["status"] == "ON_TRIP"
                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        if st.button("Go Online", type="primary", use_container_width=True, disabled=on_trip, key="go_online"):
                            update_driver_status(d["id"], "AVAILABLE")
                            st.rerun()
                    with btn_c2:
                        if st.button("Go Offline", use_container_width=True, disabled=on_trip, key="go_offline"):
                            update_driver_status(d["id"], "OFFLINE")
                            st.rerun()

                ui.heading("Incoming & Active Ride Requests", 3)
                if not active_rides:
                    ui.empty("No active ride requests right now", "Stay available to receive bookings.", "inbox")
                else:
                    for r in active_rides:
                        with panel(f"req_{r[0]}"):
                            md(
                                '<div class="stack">'
                                f'<div class="req-top"><div><div class="h3">Booking #{r[0]}</div>'
                                f'<div class="meta" style="margin-top:2px">Passenger: <b>{esc(r[1])}</b> ({esc(r[2])})</div></div>{ui.chip(r[7])}</div>'
                                + ui.stops(r[3], r[4])
                                + f'<div class="req-grid"><div><div class="lbl">Distance</div><div class="v">{esc(r[5])} km</div></div>'
                                f'<div><div class="lbl">Fare</div><div class="v">{money_html(r[6], "sm")}</div></div>'
                                f'<div><div class="lbl">Status</div><div class="v">{esc(ui.status_label(r[7]))}</div></div></div>'
                                '</div>'
                            )

                            if r[7] == "REQUESTED":
                                if st.button("Accept Ride", key=f"drv_acc_{r[0]}", type="primary", use_container_width=True, disabled=(d["status"] == "ON_TRIP")):
                                    driver_update_ride_status(r[0], d["id"], "ACCEPTED")
                                    st.rerun()
                                if st.button("Decline & Pass to Next Driver", key=f"drv_dec_{r[0]}", use_container_width=True):
                                    outcome = reassign_ride_to_next_driver(r[0], d["id"])
                                    if outcome == "REASSIGNED":
                                        flash("Ride declined and automatically passed to another available driver!")
                                    else:
                                        flash("Ride declined. No other driver available in this category.")
                                    st.rerun()
                            elif r[7] == "ACCEPTED":
                                if st.button("Start Trip", key=f"drv_start_{r[0]}", type="primary", use_container_width=True):
                                    driver_update_ride_status(r[0], d["id"], "ONGOING")
                                    st.rerun()
                            elif r[7] == "ONGOING":
                                if st.button("Complete Trip", key=f"drv_comp_{r[0]}", type="primary", use_container_width=True):
                                    driver_update_ride_status(r[0], d["id"], "COMPLETED")
                                    st.rerun()

            with right_col:
                ui.heading("Your profile and activity", 3)

                with panel("panel_profile"):
                    dc1, dc2 = st.columns([3.1, 1.4], vertical_alignment="center")
                    with dc1:
                        md(
                            f'<div class="person">{ui.avatar(d["name"], 52)}<div style="min-width:0"><div class="person-name">{esc(d["name"])}</div>'
                            f'<div class="person-sub"><span>{icon("phone", 15)}{esc(d["phone"])}</span>'
                            f'<span>{icon("id", 15)}License: {esc(d["license_no"])}</span></div></div></div>'
                            f'<div class="vehicle" style="margin-top:16px">{ui.car_svg(ui.car_kind(d["category"]), 84)}'
                            f'<div><div class="h4">{esc(d["model"])}</div>'
                            f'<div class="inline" style="margin-top:6px">{ui.plate(d["plate_no"])}<span class="meta">{esc(d["category"])}</span></div></div></div>'
                        )
                    with dc2:
                        if st.button("Manage profile", key="drv_home_profile_btn", use_container_width=True):
                            st.session_state.driver_view = "profile"
                            st.rerun()

                ui.heading("Recent Completed Rides & Ratings", 3)
                if not past_rides:
                    ui.empty("No completed or past rides yet.", icon_name="clock")
                else:
                    for r in past_rides[:5]:
                        with panel(f"row_drv_{r[0]}"):
                            rc1, rc2 = st.columns([2.6, 1.3], vertical_alignment="center")
                            with rc1:
                                md(
                                    ui.stops(r[3], r[4], True)
                                    + trip_meta(f"Booking #{r[0]}", f"Passenger: {esc(r[1])} ({esc(r[2])})", ui.fmt_dt(r[8]))
                                )
                            with rc2:
                                rating_html = f'<span class="rating-n">{ui.stars(r[9], 13)}</span>' if r[9] else ""
                                md(f'<div class="trip-price">{money_html(r[6], "sm")}{ui.chip(r[7], True)}{rating_html}</div>')

        elif view == "profile":
            def _back_dash():
                st.session_state.driver_view = "dashboard"

            with panel("narrow-sm"):
                page_head("Manage Driver & Vehicle Profile", "Back to Driver Dashboard", "dash_profile", _back_dash)

                categories = get_cab_categories()
                cat_map = {c[1]: c[0] for c in categories} if categories else {"Sedan": 1}
                cat_names = list(cat_map.keys())
                default_idx = cat_names.index(d["category"]) if d["category"] in cat_names else 0

                with panel("panel_form"):
                    md(
                        f'<div class="person">{ui.avatar(d["name"], 56)}<div><div class="person-name">{esc(d["name"])}</div>'
                        f'<div class="person-sub"><span>{icon("star", 14, fill=True, sw=1.5)}{avg_rating:.2f} ({total_reviews} reviews)</span></div></div></div>'
                    )
                    u_name = st.text_input("Driver Full Name", value=d["name"])
                    u_phone = st.text_input("Driver Phone Number (10 digits)", value=d["phone"])
                    st.text_input("Driving License Number (Verified)", value=d["license_no"], disabled=True)
                    u_plate = st.text_input("Cab Plate Number", value=d["plate_no"] or "")
                    u_model = st.text_input("Cab Vehicle Model", value=d["model"] or "")
                    u_cat_name = st.selectbox("Cab Category", cat_names, index=default_idx)

                    if st.button("Save Profile Changes", type="primary", use_container_width=True, key="cta_save_profile"):
                        if u_phone and (not u_phone.strip().isdigit() or len(u_phone.strip()) != 10):
                            ui.notice("error", "Phone number must be exactly 10 digits.")
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
                                flash("Driver and vehicle profile updated successfully!")
                                st.rerun()
                            else:
                                ui.notice("error", "Phone number or number plate is already registered to another driver.")

        elif view == "history":
            def _back_dash():
                st.session_state.driver_view = "dashboard"

            with panel("narrow"):
                page_head("Past Rides & Passenger Ratings", "Back to Driver Dashboard", "dash_history", _back_dash)

                if not past_rides:
                    ui.empty("No past rides recorded yet.", icon_name="clock")
                else:
                    for r in past_rides:
                        with panel(f"row_hist_{r[0]}"):
                            c1, c2, c3 = st.columns([2.8, 1.3, 1.4], vertical_alignment="center")
                            with c1:
                                md(
                                    ui.stops(r[3], r[4], True)
                                    + trip_meta(f"Booking #{r[0]}", f"Passenger: {esc(r[1])} ({esc(r[2])})", ui.fmt_dt(r[8], seconds=True))
                                )
                            with c2:
                                md(
                                    f'<div class="trip-price">{money_html(r[6], "sm")}{ui.chip(r[7], True)}'
                                    f'<span class="meta">Distance: {esc(r[5])} km</span></div>'
                                )
                            with c3:
                                if r[9]:
                                    comment = f'<div class="review">"{esc(r[10])}"</div>' if r[10] else ""
                                    md(f'<div class="rating-box">{ui.stars(r[9], 15)}<span class="rating-n">{esc(r[9])}/5</span>{comment}</div>')
                                else:
                                    md('<div class="meta">No rating submitted</div>')


# ==========================================
# MAIN ROUTER
# ==========================================
if st.session_state.get("_flash"):
    st.toast(st.session_state.pop("_flash"))

if st.session_state.passenger:
    render_passenger_portal()
elif st.session_state.driver:
    render_driver_portal()
else:
    if st.session_state.auth_mode == "driver_auth":
        render_driver_auth()
    else:
        render_passenger_auth()
