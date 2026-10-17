from db import get_connection

def register_passenger(full_name, phone, email):
     with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO passenger (full_name, phone, email)
                VALUES (%s, %s, %s)
                RETURNING passenger_id;
            """, (full_name, phone, email))

            new_id = cur.fetchone()[0]
            return new_id

def get_passenger_by_phone(phone):
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
                    WHERE d.status = 'AVAILABLE' AND ILIKE(cat.type_name, %s);
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
    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT cat.base_fare, cat.rate_per_km
                FROM cab c
                JOIN cab_category cat ON c.category_id = cat.category_id
                WHERE c.cab_id = %s;
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
                WHERE booking_id = %s AND passenger_id = %s AND ride_status = 'CANCELLED'
                RETURNING booking_id;
            """,
          (booking_id, passenger_id),
      )
      return cur.fetchone()
