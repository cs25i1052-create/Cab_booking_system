import psycopg

DATABASE_URL = "postgresql://cab_booking_system_owner:npg_2EswB7gzPCvm@ep-winter-cake-b47x83z4-pooler.c-6.us-east-2.aws.neon.tech/cab_booking_system?sslmode=require&channel_binding=require"

try:
    with psycopg.connect(DATABASE_URL) as conn:
        print("Successfully connected to the cab booking database!")
except Exception as e:
    print("Connection failed:", e)
