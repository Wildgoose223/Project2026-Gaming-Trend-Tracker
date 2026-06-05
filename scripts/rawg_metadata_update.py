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


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_games():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, game_name
        FROM games
        WHERE background_image IS NULL
        LIMIT 200;
    """)

    games = cur.fetchall()

    cur.close()
    conn.close()

    return games


def search_rawg(game_name):
    url = "https://api.rawg.io/api/games"

    params = {
        "key": RAWG_API_KEY,
        "search": game_name,
        "page_size": 1
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    results = response.json().get("results", [])

    if not results:
        return None

    return results[0]


def update_game(game_id, rawg_game):
    background_image = rawg_game.get("background_image")
    metacritic = rawg_game.get("metacritic")

    genres = ", ".join(
        g.get("name")
        for g in rawg_game.get("genres", [])
        if g.get("name")
    )

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE games
        SET
            background_image = %s,
            metacritic = %s,
            genres = %s
        WHERE id = %s;
    """, (
        background_image,
        metacritic,
        genres,
        game_id
    ))

    conn.commit()

    cur.close()
    conn.close()


def main():
    if not RAWG_API_KEY:
        raise ValueError("RAWG_API_KEY missing in .env")

    games = get_games()

    print(f"Found {len(games)} games needing metadata")

    updated = 0

    for game_id, game_name in games:
        try:
            rawg_game = search_rawg(game_name)

            if rawg_game:
                update_game(game_id, rawg_game)

                updated += 1

                print(f"Updated: {game_name}")

            else:
                print(f"No RAWG match: {game_name}")

            time.sleep(1)

        except Exception as e:
            print(f"Failed: {game_name} -> {e}")

    print(f"\nDone. Updated {updated} games.")


if __name__ == "__main__":
    main()