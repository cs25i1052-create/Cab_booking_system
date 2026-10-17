import psycopg

DATABASE_URL = "postgresql://cab_booking_system_owner:npg_2EswB7gzPCvm@ep-winter-cake-b47x83z4-pooler.c-6.us-east-2.aws.neon.tech/cab_booking_system?sslmode=require&channel_binding=require"


def get_connection():
  return psycopg.connect(DATABASE_URL)

"""if __name__ == "__main__":
  try:
    with get_connection() as conn:
      print("Successfully connected to the cab booking database!")
  except Exception as e:
    print("Connection failed:", e)"""
