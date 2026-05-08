import psycopg2
from datetime import datetime

try:
    conn = psycopg2.connect(
        dbname="youtube_data",
        user="postgres",
        password="YOUR_PW",
        host="localhost",
        port="5432"
    )

    cur = conn.cursor()

    insert_query = """
    INSERT INTO videos (title, game, views, timestamp)
    VALUES (%s, %s, %s, %s)
    """

    cur.execute(insert_query, (
        "Test YouTube Video",
        "Elden Ring",
        123456,
        datetime.now()
    ))

    conn.commit()

    print("Data inserted successfully.")

    cur.execute("SELECT * FROM videos;")
    rows = cur.fetchall()

    print("\nCurrent rows in videos table:")
    for row in rows:
        print(row)

    cur.close()
    conn.close()

except Exception as e:
    print("Error:", e)