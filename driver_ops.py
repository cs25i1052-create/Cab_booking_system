import psycopg
from db import get_connection

# ==========================================
# 1. DRIVER AUTH & PROFILE (Used by app.py UI)
# ==========================================

def get_cab_categories():
    """Fetches cab categories for dropdowns."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT category_id, type_name, base_fare, rate_per_km 
                FROM cab_category 
                ORDER BY category_id ASC;
            """)
            return cur.fetchall()

def signup_driver(full_name, phone, license_no, plate_no, model, category_id):
    """Registers both a new driver and their cab in a single transaction."""
    if not phone.isdigit() or len(phone) != 10:
        print("Error: Phone number must be exactly 10 digits.")
        return None

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Insert Driver
                cur.execute("""
                    INSERT INTO driver (full_name, phone, license_no, status) 
                    VALUES (%s, %s, %s, 'AVAILABLE') RETURNING driver_id;
                """, (full_name.strip(), phone.strip(), license_no.strip()))
                driver_id = cur.fetchone()[0]

                # 2. Insert Cab
                cur.execute("""
                    INSERT INTO cab (plate_no, model, category_id, driver_id) 
                    VALUES (%s, %s, %s, %s);
                """, (plate_no.strip(), model.strip(), category_id, driver_id))
                
                conn.commit()
                return driver_id

    except psycopg.errors.UniqueViolation:
        print("Error: A driver with this phone, license, or plate number already exists.")
        return None

def login_driver(phone):
    """Logs in a driver using their 10-digit phone number and fetches their cab details."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.driver_id, d.full_name, d.license_no, d.status, 
                       c.plate_no, c.model, cat.type_name
                FROM driver d
                LEFT JOIN cab c ON d.driver_id = c.driver_id
                LEFT JOIN cab_category cat ON c.category_id = cat.category_id
                WHERE d.phone = %s;
            """, (phone.strip(),))
            return cur.fetchone()

def update_driver_profile(driver_id, full_name="", phone="", plate_no="", model="", category_id=None):
    """Updates driver personal info and cab details."""
    clean_name = full_name.strip() if full_name else ""
    clean_phone = phone.strip() if phone else ""
    clean_plate = plate_no.strip() if plate_no else ""
    clean_model = model.strip() if model else ""

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if clean_name or clean_phone:
                    cur.execute("""
                        UPDATE driver
                        SET full_name = COALESCE(NULLIF(%s, ''), full_name),
                            phone     = COALESCE(NULLIF(%s, ''), phone)
                        WHERE driver_id = %s;
                    """, (clean_name, clean_phone, driver_id))

                if clean_plate or clean_model or category_id:
                    cur.execute("""
                        UPDATE cab
                        SET plate_no    = COALESCE(NULLIF(%s, ''), plate_no),
                            model       = COALESCE(NULLIF(%s, ''), model),
                            category_id = COALESCE(%s, category_id)
                        WHERE driver_id = %s;
                    """, (clean_plate, clean_model, category_id, driver_id))

                conn.commit()
                return True
                
    except psycopg.errors.UniqueViolation:
        print("Error: Phone number or number plate is already used by another driver.")
        return False


# ==========================================
# 2. RIDE & STATUS OPERATIONS (Used by app.py UI)
# ==========================================

def update_driver_status(driver_id, new_status):
    """Changes driver status (AVAILABLE, ON_TRIP, OFFLINE)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE driver SET status = %s WHERE driver_id = %s;", (new_status, driver_id))
            conn.commit()
            return cur.rowcount

# A ride may only move one step forward: REQUESTED -> ACCEPTED -> ONGOING -> COMPLETED
PREV_STATUS = {'ACCEPTED': 'REQUESTED', 'ONGOING': 'ACCEPTED', 'COMPLETED': 'ONGOING'}

def driver_update_ride_status(booking_id, driver_id, new_ride_status):
    """Moves a ride one step forward (ACCEPTED, ONGOING, COMPLETED) and syncs driver status.
    Returns 1 if updated, 0 if the change was not allowed."""
    prev = PREV_STATUS.get(new_ride_status)
    if prev is None:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            if new_ride_status == 'ACCEPTED':
                cur.execute("SELECT 1 FROM driver WHERE driver_id = %s AND status = 'ON_TRIP';", (driver_id,))
                if cur.fetchone():
                    return 0          # already on a trip: cannot accept another ride
            cur.execute("""
                UPDATE ride_booking rb
                SET ride_status = %s
                FROM cab c
                WHERE rb.cab_id = c.cab_id
                  AND rb.booking_id = %s
                  AND c.driver_id = %s
                  AND rb.ride_status = %s;
            """, (new_ride_status, booking_id, driver_id, prev))
            updated = cur.rowcount
            if updated == 1:
                if new_ride_status in ('ACCEPTED', 'ONGOING'):
                    cur.execute("UPDATE driver SET status = 'ON_TRIP' WHERE driver_id = %s;", (driver_id,))
                elif new_ride_status == 'COMPLETED':
                    cur.execute("UPDATE driver SET status = 'AVAILABLE' WHERE driver_id = %s;", (driver_id,))
            conn.commit()
            return updated

def get_driver_rating_stats(driver_id):
    """Calculates average rating and total reviews for a driver."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(ROUND(AVG(rf.rating)::numeric, 2), 5.0), COUNT(rf.feedback_id)
                FROM cab c
                LEFT JOIN ride_booking rb ON c.cab_id = rb.cab_id
                LEFT JOIN ride_feedback rf ON rb.booking_id = rf.booking_id
                WHERE c.driver_id = %s;
            """, (driver_id,))
            row = cur.fetchone()
            return (float(row[0]), int(row[1])) if row else (5.0, 0)

def get_driver_rides(driver_id):
    """Fetches all active and past rides (with ratings) for a driver."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rb.booking_id, p.full_name, p.phone, rb.pickup_loc, rb.drop_loc,
                       rb.distance_km, rb.total_fare, rb.ride_status, rb.booking_time,
                       rf.rating, rf.review_comment
                FROM ride_booking rb
                JOIN cab c ON rb.cab_id = c.cab_id
                JOIN passenger p ON rb.passenger_id = p.passenger_id
                LEFT JOIN ride_feedback rf ON rb.booking_id = rf.booking_id
                WHERE c.driver_id = %s
                ORDER BY rb.booking_time DESC;
            """, (driver_id,))
            return cur.fetchall()


# ==========================================
# 3. WATERFALL DISPATCH: REASSIGN ON DECLINE / CANCEL
# ==========================================

def reassign_ride_to_next_driver(booking_id, declining_driver_id):
    """Logs a driver decline/cancel and randomly reassigns the ride to another available driver in the same category."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Ensure ride_declines table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ride_declines (
                    booking_id INT,
                    driver_id INT,
                    PRIMARY KEY (booking_id, driver_id)
                );
            """)

            # 1. Log that this driver declined/cancelled this booking
            cur.execute("""
                INSERT INTO ride_declines (booking_id, driver_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING;
            """, (booking_id, declining_driver_id))

            # 2. Find the category of this booking
            cur.execute("""
                SELECT c.category_id 
                FROM ride_booking rb
                JOIN cab c ON rb.cab_id = c.cab_id
                WHERE rb.booking_id = %s;
            """, (booking_id,))
            row = cur.fetchone()
            if not row:
                return "ERROR"
            category_id = row[0]

            # 3. Randomly pick the NEXT available driver in that category who hasn't declined yet
            cur.execute("""
                SELECT c.cab_id, d.driver_id
                FROM cab c
                JOIN driver d ON c.driver_id = d.driver_id
                WHERE c.category_id = %s 
                  AND d.status = 'AVAILABLE'
                  AND d.driver_id != %s
                  AND d.driver_id NOT IN (
                      SELECT driver_id FROM ride_declines WHERE booking_id = %s
                  )
                ORDER BY RANDOM()
                LIMIT 1;
            """, (category_id, declining_driver_id, booking_id))

            next_cab = cur.fetchone()

            if next_cab:
                # 4a. Reassign ride to the next random driver
                new_cab_id = next_cab[0]
                cur.execute("""
                    UPDATE ride_booking
                    SET cab_id = %s, ride_status = 'REQUESTED'
                    WHERE booking_id = %s;
                """, (new_cab_id, booking_id))
                
                cur.execute("UPDATE driver SET status = 'AVAILABLE' WHERE driver_id = %s;", (declining_driver_id,))
                conn.commit()
                return "REASSIGNED"
            else:
                # 4b. No drivers left! Mark ride as NO_DRIVERS
                cur.execute("""
                    UPDATE ride_booking
                    SET ride_status = 'NO_DRIVERS'
                    WHERE booking_id = %s;
                """, (booking_id,))
                cur.execute("UPDATE driver SET status = 'AVAILABLE' WHERE driver_id = %s;", (declining_driver_id,))
                conn.commit()
                return "NO_DRIVERS_LEFT"


# ==========================================
# 4. CORE ADMIN / FLEET OPERATIONS
# ==========================================

def add_driver(full_name, phone, license_no, status="AVAILABLE"):
    """Registers a new driver."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO driver (full_name, phone, license_no, status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING driver_id;
                """, (full_name, phone, license_no, status))
                new_driver_id = cur.fetchone()[0]
                conn.commit()
                return new_driver_id
    except psycopg.errors.UniqueViolation:
        raise ValueError("Error: This phone number or license is already registered.")

def assign_cab(plate_no, model, category_id, driver_id):
    """Assigns a new cab to a driver and a specific category."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO cab (plate_no, model, category_id, driver_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING cab_id;
                """, (plate_no, model, category_id, driver_id))
                new_cab_id = cur.fetchone()[0]
                conn.commit()
                return new_cab_id
    except psycopg.errors.UniqueViolation:
        raise ValueError("Error: This Cab Plate or Driver ID is already assigned.")

def update_ride_status(booking_id, new_status):
    """Changes ride status (ACCEPTED, ONGOING, COMPLETED)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE ride_booking SET ride_status = %s WHERE booking_id = %s;", (new_status, booking_id))
            conn.commit()
            return cur.rowcount

def get_all_drivers_and_cabs():
    """Fetches the entire fleet."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.driver_id, d.full_name, d.phone, d.status,
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
            cur.execute("""
                SELECT rb.booking_id, p.full_name AS passenger_name, p.phone AS passenger_phone,
                       rb.pickup_loc, rb.drop_loc, rb.distance_km, rb.total_fare,
                       rb.ride_status, rb.booking_time
                FROM ride_booking rb
                JOIN cab c ON rb.cab_id = c.cab_id
                JOIN passenger p ON rb.passenger_id = p.passenger_id
                WHERE c.driver_id = %s
                ORDER BY rb.booking_time DESC;
            """, (driver_id,))
            return cur.fetchall()

def get_active_rides_for_driver(driver_id):
    """Fetches only active requests so the driver can Accept or Complete them."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rb.booking_id, p.full_name AS passenger_name,
                       rb.pickup_loc, rb.drop_loc, rb.total_fare, rb.ride_status
                FROM ride_booking rb
                JOIN cab c ON rb.cab_id = c.cab_id
                JOIN passenger p ON rb.passenger_id = p.passenger_id
                WHERE c.driver_id = %s AND rb.ride_status IN ('REQUESTED', 'ACCEPTED', 'ONGOING')
                ORDER BY rb.booking_time ASC;
            """, (driver_id,))
            return cur.fetchall()