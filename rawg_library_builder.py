import os
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

RAWG_API_KEY = os.getenv("RAWG_API_KEY")

DB_NAME = os.getenv("DB_NAME", "Gaming_Trend_Tracker")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")


def get_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )


def create_tables(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS games_library (
                id SERIAL PRIMARY KEY,
                rawg_id INTEGER UNIQUE,
                game_name TEXT NOT NULL,
                slug TEXT,
                source TEXT DEFAULT 'RAWG'
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_aliases (
                id SERIAL PRIMARY KEY,
                game_name TEXT NOT NULL,
                alias TEXT NOT NULL,
                source TEXT DEFAULT 'RAWG'
            );
        """)

    conn.commit()


def clean_alias(name):
    return name.lower().strip()


def save_game(conn, rawg_id, name, slug):
    alias = clean_alias(name)

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO games_library (rawg_id, game_name, slug)
            VALUES (%s, %s, %s)
            ON CONFLICT (rawg_id) DO NOTHING;
        """, (rawg_id, name, slug))

        cur.execute("""
            INSERT INTO game_aliases (game_name, alias)
            VALUES (%s, %s)
            ON CONFLICT (alias) DO NOTHING;
        """, (name, alias))

    conn.commit()


def fetch_rawg_games(page=1, page_size=40):
    url = "https://api.rawg.io/api/games"

    params = {
        "key": RAWG_API_KEY,
        "page": page,
        "page_size": page_size,
        "ordering": "-added"
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    return response.json()


def main():
    if not RAWG_API_KEY:
        raise ValueError("Missing RAWG_API_KEY in .env file.")

    conn = get_connection()
    create_tables(conn)

    pages_to_pull = 10

    total_saved = 0

    for page in range(1, pages_to_pull + 1):
        data = fetch_rawg_games(page=page)
        games = data.get("results", [])

        for game in games:
            rawg_id = game.get("id")
            name = game.get("name")
            slug = game.get("slug")

            if rawg_id and name:
                save_game(conn, rawg_id, name, slug)
                total_saved += 1

        print(f"Page {page} complete. Total saved/checks: {total_saved}")

    conn.close()
    print("RAWG library build complete.")


if __name__ == "__main__":
    main()