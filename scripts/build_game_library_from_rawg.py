import os
import time
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

RAWG_API_KEY = os.getenv("RAWG_API_KEY")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT", "5432")
}

RAWG_URL = "https://api.rawg.io/api/games"


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


def create_tables():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id SERIAL PRIMARY KEY,
            rawg_id INTEGER UNIQUE,
            game_name TEXT NOT NULL,
            released TEXT,
            rating NUMERIC,
            category TEXT DEFAULT 'unknown_review'
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS game_platforms (
            platform_id SERIAL PRIMARY KEY,
            rawg_id INTEGER,
            platform_name TEXT
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


def fetch_rawg_games(pages=5):
    all_games = []

    for page in range(1, pages + 1):
        params = {
            "key": RAWG_API_KEY,
            "page": page,
            "page_size": 40,
            "ordering": "-added"
        }

        response = requests.get(RAWG_URL, params=params)
        response.raise_for_status()

        data = response.json()
        games = data.get("results", [])
        all_games.extend(games)

        print(f"Fetched page {page}: {len(games)} games")
        time.sleep(1)

    return all_games


def save_games(games):
    conn = connect_db()
    cur = conn.cursor()

    for game in games:
        rawg_id = game.get("id")
        name = game.get("name")
        released = game.get("released")
        rating = game.get("rating")

        if not rawg_id or not name:
            continue

        cur.execute("""
            INSERT INTO games (rawg_id, game_name, released, rating)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (rawg_id)
            DO UPDATE SET
                game_name = EXCLUDED.game_name,
                released = EXCLUDED.released,
                rating = EXCLUDED.rating;
        """, (rawg_id, name, released, rating))

        platforms = game.get("platforms", [])

        for item in platforms:
            platform = item.get("platform", {})
            platform_name = platform.get("name")

            if platform_name:
                cur.execute("""
                    INSERT INTO game_platforms (rawg_id, platform_name)
                    SELECT %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM game_platforms
                        WHERE rawg_id = %s AND platform_name = %s
                    );
                """, (rawg_id, platform_name, rawg_id, platform_name))

    conn.commit()
    cur.close()
    conn.close()


def main():
    if not RAWG_API_KEY:
        raise ValueError("RAWG_API_KEY is missing from your .env file.")

    create_tables()

    games = fetch_rawg_games(pages=10)
    save_games(games)

    print(f"Saved/updated {len(games)} games from RAWG.")


if __name__ == "__main__":
    main()