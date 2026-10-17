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
