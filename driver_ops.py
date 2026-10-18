import psycopg
from db import get_connection

# ==========================================
# 1. ADD & ASSIGN OPERATIONS (INSERT)
# ==========================================

def add_driver(full_name, phone, license_no, status="AVAILABLE"):
    """Registers a new driver. Catches duplicate phone/license errors."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO driver (full_name, phone, license_no, status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING driver_id;
                    """,
                    (full_name, phone, license_no, status),
                )
                new_driver_id = cur.fetchone()[0]
                conn.commit()
                return new_driver_id
    except psycopg.errors.UniqueViolation:
        raise ValueError("Error: This phone number or license is already registered to another driver.")

def assign_cab(plate_no, model, category_id, driver_id):
    """Assigns a new cab to a driver and a specific category."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cab (plate_no, model, category_id, driver_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING cab_id;
                    """,
                    (plate_no, model, category_id, driver_id),
                )
                new_cab_id = cur.fetchone()[0]
                conn.commit()
                return new_cab_id
    except psycopg.errors.UniqueViolation:
        raise ValueError("Error: This Cab Plate or Driver ID is already assigned.")


# ==========================================
# 2. STATUS UPDATE OPERATIONS (UPDATE)
# ==========================================

def update_driver_status(driver_id, new_status):
    """Changes driver status (AVAILABLE, ON_TRIP, OFFLINE)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE driver
                SET status = %s
                WHERE driver_id = %s;
                """,
                (new_status, driver_id),
            )
            conn.commit()
            return cur.rowcount

def update_ride_status(booking_id, new_status):
    """Changes ride status (ACCEPTED, ONGOING, COMPLETED)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ride_booking
                SET ride_status = %s
                WHERE booking_id = %s;
                """,
                (new_status, booking_id),
            )
            conn.commit()
            return cur.rowcount


# ==========================================
# 3. FETCH OPERATIONS (SELECT & JOINS)
# ==========================================

def get_all_drivers_and_cabs():
    """Fetches the entire fleet for the Admin/Fleet Overview tab."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    d.driver_id, 
                    d.full_name, 
                    d.phone, 
                    d.status,
                    COALESCE(c.plate_no, 'Unassigned') AS plate_no,
                    COALESCE(c.model, 'Unassigned') AS model,
                    COALESCE(cat.type_name, 'N/A') AS category
                FROM driver d
                LEFT JOIN cab c ON d.driver_id = c.driver_id
                LEFT JOIN cab_category cat ON c.category_id = cat.category_id
                ORDER BY d.driver_id ASC;
            """)
            return cur.fetchall()

def get_driver_trips(driver_id):
    """Fetches all historical trips for a specific driver."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    rb.booking_id,
                    p.full_name AS passenger_name,
                    p.phone AS passenger_phone,
                    rb.pickup_loc,
                    rb.drop_loc,
                    rb.distance_km,
                    rb.total_fare,
                    rb.ride_status,
                    rb.booking_time
                FROM ride_booking rb
                JOIN cab c ON rb.cab_id = c.cab_id
                JOIN passenger p ON rb.passenger_id = p.passenger_id
                WHERE c.driver_id = %s
                ORDER BY rb.booking_time DESC;
                """,
                (driver_id,),
            )
            return cur.fetchall()


# ==========================================
# 4. INTEGRATION HELPERS (For Streamlit UI)
# ==========================================

def get_cab_categories():
    """Fetches categories so Streamlit UI can show a dropdown instead of asking for IDs."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT category_id, type_name, base_fare, rate_per_km 
                FROM cab_category 
                ORDER BY category_id ASC;
            """)
            return cur.fetchall()

def get_active_rides_for_driver(driver_id):
    """Fetches only active requests so the driver can Accept or Complete them."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    rb.booking_id,
                    p.full_name AS passenger_name,
                    rb.pickup_loc,
                    rb.drop_loc,
                    rb.total_fare,
                    rb.ride_status
                FROM ride_booking rb
                JOIN cab c ON rb.cab_id = c.cab_id
                JOIN passenger p ON rb.passenger_id = p.passenger_id
                WHERE c.driver_id = %s AND rb.ride_status IN ('REQUESTED', 'ACCEPTED', 'ONGOING')
                ORDER BY rb.booking_time ASC;
                """,
                (driver_id,),
            )
            return cur.fetchall()