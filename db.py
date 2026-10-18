import time
import psycopg

DATABASE_URL = "postgresql://cab_booking_system_owner:npg_2EswB7gzPCvm@ep-winter-cake-b47x83z4-pooler.c-6.us-east-2.aws.neon.tech/cab_booking_system?sslmode=require&channel_binding=require"
def get_connection(retries=3, delay=1.0):
    last_err = None
    for attempt in range(retries):
        try:
            return psycopg.connect(DATABASE_URL, connect_timeout=10)
        except psycopg.OperationalError as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(delay)
    raise last_err