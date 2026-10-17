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