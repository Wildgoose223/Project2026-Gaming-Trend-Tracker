import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        database="YouTube_Data",
        user="postgres",
        password="Cheese123"
    )
    print("Connected successfully!")
    conn.close()
except Exception as e:
    print("Connection failed:")
    print(e)

input("Press Enter to close...")