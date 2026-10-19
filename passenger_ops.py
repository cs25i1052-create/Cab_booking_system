import psycopg
from db import get_connection

def register_passenger(full_name, phone, email):
    full_name = full_name.strip()
    phone = phone.strip()
    email = email.strip()

    if not phone.isdigit() or len(phone) != 10:
        print("Error: Phone number must be exactly 10 digits.")
        return None

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO passenger (full_name, phone, email)
                    VALUES (%s, %s, %s);
                 """, (full_name, phone, email))

                cur.execute("""
                    SELECT passenger_id
                    FROM passenger
                    WHERE phone = %s;
                """, (phone,))

                new_id = cur.fetchone()[0]
                return new_id

    except psycopg.errors.UniqueViolation:
        return None



def get_passenger_by_phone(phone):
    phone = phone.strip()  
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT passenger_id, full_name, phone, email, created_at
                FROM passenger
                WHERE phone = %s;
            """, (phone,))
            return cur.fetchone()
   



def get_available_cabs(category_type=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if category_type:
                
                cur.execute("""
                    SELECT c.cab_id, c.model, c.plate_no, cat.type_name, 
                           cat.base_fare, cat.rate_per_km, cat.seating_capacity, d.full_name
                    FROM cab c
                    JOIN driver d ON c.driver_id = d.driver_id
                    JOIN cab_category cat ON c.category_id = cat.category_id
                    WHERE d.status = 'AVAILABLE' AND cat.type_name ILIKE %s;
                """, (category_type,))
            else:
                cur.execute("""
                    SELECT c.cab_id, c.model, c.plate_no, cat.type_name, 
                           cat.base_fare, cat.rate_per_km, cat.seating_capacity, d.full_name
                    FROM cab c
                    JOIN driver d ON c.driver_id = d.driver_id
                    JOIN cab_category cat ON c.category_id = cat.category_id
                    WHERE d.status = 'AVAILABLE';
                """)
            
            return cur.fetchall()

def book_ride(passenger_id, cab_id, pickup_loc, drop_loc, distance_km):
    if float(distance_km) <= 0:
        print("Error: Distance must be greater than 0 km.")
        return None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT cat.base_fare, cat.rate_per_km
                    FROM cab c
                    JOIN cab_category cat ON c.category_id = cat.category_id
                    JOIN driver d ON c.driver_id = d.driver_id
                    WHERE c.cab_id = %s AND d.status = 'AVAILABLE';
                """, (cab_id,))

                pricing = cur.fetchone()

                if not pricing:
                    return None 

                base_fare = float(pricing[0])
                rate_per_km = float(pricing[1])
                total_fare = base_fare + (float(distance_km) * rate_per_km)

                cur.execute("""
                    INSERT INTO ride_booking 
                    (passenger_id, cab_id, pickup_loc, drop_loc, distance_km, total_fare, ride_status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'REQUESTED')
                    RETURNING booking_id, total_fare;
                """, (passenger_id, cab_id, pickup_loc, drop_loc, distance_km, total_fare))

                return cur.fetchone()

    except psycopg.errors.ForeignKeyViolation:
        print(f"Error: Passenger ID {passenger_id} does not exist!")
        return None


def get_passenger_rides(passenger_id):
  with get_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
          """
                SELECT rb.booking_id, rb.pickup_loc, rb.drop_loc, rb.distance_km, 
                       rb.total_fare, rb.ride_status, rb.booking_time, 
                       c.model, c.plate_no, d.full_name
                FROM ride_booking rb
                JOIN cab c ON rb.cab_id = c.cab_id
                JOIN driver d ON c.driver_id = d.driver_id
                WHERE rb.passenger_id = %s
                ORDER BY rb.booking_time DESC;
            """,
          (passenger_id,),
      )
      return cur.fetchall()


def cancel_ride(booking_id, passenger_id):
  with get_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
          """
                UPDATE ride_booking
                SET ride_status = 'CANCELLED'
                WHERE booking_id = %s AND passenger_id = %s AND ride_status = 'REQUESTED'
                RETURNING booking_id;
            """,
          (booking_id, passenger_id),
      )
      return cur.fetchone()


def delete_cancelled_ride(booking_id, passenger_id):
  with get_connection() as conn:
    with conn.cursor() as cur:
      cur.execute(
          """
                DELETE FROM ride_booking
                WHERE booking_id = %s AND passenger_id = %s AND ride_status IN ('CANCELLED', 'NO_DRIVERS')
                RETURNING booking_id;
            """,
          (booking_id, passenger_id),
      )
      return cur.fetchone()

def update_passenger_details(passenger_id, full_name="", phone="", email=""):
    clean_name = full_name.strip() if full_name else ""
    clean_phone = phone.strip() if phone else ""
    clean_email = email.strip() if email else ""

   
    if not clean_name and not clean_phone and not clean_email:
        print("Error: Provide at least one new detail (name, phone, or email) to update.")
        return None

    if clean_phone and (not clean_phone.isdigit() or len(clean_phone) != 10):
        print("Error: New phone number must be exactly 10 digits.")
        return None

 
    if clean_email and ("@" not in clean_email or "." not in clean_email):
        print("Error: Invalid email format.")
        return None

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
        
                cur.execute("""
                    UPDATE passenger
                    SET full_name = COALESCE(NULLIF(%s, ''), full_name),
                        phone     = COALESCE(NULLIF(%s, ''), phone),
                        email     = COALESCE(NULLIF(%s, ''), email)
                    WHERE passenger_id = %s
                    RETURNING passenger_id, full_name, phone, email;
                """, (clean_name, clean_phone, clean_email, passenger_id))

                updated_user = cur.fetchone()
                if not updated_user:
                    print(f"Error: Passenger ID {passenger_id} not found.")
                    return None

                return updated_user

    except psycopg.errors.UniqueViolation:
        print("Error: That phone number or email is already registered to another passenger!")
        return None

def get_cab_categories():

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT category_id, type_name FROM cab_category;")
            return cur.fetchall()

def signup_driver(full_name, phone, license_no, plate_no, model, category_id):

    if not phone.isdigit() or len(phone) != 10:
        print("Error: Phone number must be exactly 10 digits.")
        return None

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
    
                cur.execute("""
                    INSERT INTO driver (full_name, phone, license_no, status) 
                    VALUES (%s, %s, %s, 'AVAILABLE') RETURNING driver_id;
                """, (full_name.strip(), phone.strip(), license_no.strip()))
                driver_id = cur.fetchone()[0]

                # 2. Insert their Cab
                cur.execute("""
                    INSERT INTO cab (plate_no, model, category_id, driver_id) 
                    VALUES (%s, %s, %s, %s);
                """, (plate_no.strip(), model.strip(), category_id, driver_id))
                
                conn.commit()
                return driver_id

    except psycopg.errors.UniqueViolation:
        print("Error: A driver with this phone number, license number, or plate number already exists.")
        return None

def login_driver(phone):

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
        print("Error: The new phone number or number plate is already used by another driver.")
        return False

def update_driver_status(driver_id, new_status):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE driver SET status = %s WHERE driver_id = %s;", (new_status, driver_id))
            conn.commit()
