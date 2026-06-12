import os
import time
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

RAWG_API_KEY = os.getenv("RAWG_API_KEY")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "Gaming_Trend_Tracker"),
    "user": os.getenv("DB_USER", "postgres"),
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
            released DATE,
            rating NUMERIC,
            metacritic INTEGER,
            playtime INTEGER,
            background_image TEXT,
            website TEXT,
            rawg_slug TEXT,
            category TEXT DEFAULT 'rawg_game',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS game_platforms (
            platform_id SERIAL PRIMARY KEY,
            rawg_id INTEGER,
            platform_name TEXT,
            UNIQUE(rawg_id, platform_name)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS game_genres (
            genre_id SERIAL PRIMARY KEY,
            rawg_id INTEGER,
            genre_name TEXT,
            UNIQUE(rawg_id, genre_name)
        );
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("RAWG tables verified.")


def fetch_rawg_games(pages=10):
    all_games = []

    for page in range(1, pages + 1):
        params = {
            "key": RAWG_API_KEY,
            "page": page,
            "page_size": 40,
            "ordering": "-added"
        }

        response = requests.get(RAWG_URL, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        games = data.get("results", [])
        all_games.extend(games)

        print(f"Fetched RAWG page {page}: {len(games)} games")
        time.sleep(1)

    return all_games


def save_games(games):
    conn = connect_db()
    cur = conn.cursor()

    saved_count = 0

    for game in games:
        rawg_id = game.get("id")
        name = game.get("name")
        released = game.get("released")
        rating = game.get("rating")
        metacritic = game.get("metacritic")
        playtime = game.get("playtime")
        background_image = game.get("background_image")
        slug = game.get("slug")

        if not rawg_id or not name:
            continue

        cur.execute("""
            INSERT INTO games (
                rawg_id,
                game_name,
                released,
                rating,
                metacritic,
                playtime,
                background_image,
                rawg_slug,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (rawg_id)
            DO UPDATE SET
                game_name = EXCLUDED.game_name,
                released = EXCLUDED.released,
                rating = EXCLUDED.rating,
                metacritic = EXCLUDED.metacritic,
                playtime = EXCLUDED.playtime,
                background_image = EXCLUDED.background_image,
                rawg_slug = EXCLUDED.rawg_slug,
                updated_at = CURRENT_TIMESTAMP;
        """, (
            rawg_id,
            name,
            released,
            rating,
            metacritic,
            playtime,
            background_image,
            slug
        ))

        platforms = game.get("platforms", [])

        for item in platforms:
            platform = item.get("platform", {})
            platform_name = platform.get("name")

            if platform_name:
                cur.execute("""
                    INSERT INTO game_platforms (rawg_id, platform_name)
                    VALUES (%s, %s)
                    ON CONFLICT (rawg_id, platform_name)
                    DO NOTHING;
                """, (rawg_id, platform_name))

        genres = game.get("genres", [])

        for genre in genres:
            genre_name = genre.get("name")

            if genre_name:
                cur.execute("""
                    INSERT INTO game_genres (rawg_id, genre_name)
                    VALUES (%s, %s)
                    ON CONFLICT (rawg_id, genre_name)
                    DO NOTHING;
                """, (rawg_id, genre_name))

        saved_count += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"Saved/updated {saved_count} RAWG games.")


def main():
    if not RAWG_API_KEY:
        raise ValueError("RAWG_API_KEY is missing from your .env file.")

    create_tables()

    games = fetch_rawg_games(pages=10)
    save_games(games)

    print("RAWG pull complete.")


if __name__ == "__main__":
    main()