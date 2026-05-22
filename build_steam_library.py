import os
import re
import requests
import psycopg2
from dotenv import load_dotenv


load_dotenv()

STEAM_API_KEY = os.getenv("STEAM_API_KEY")

DB_NAME = os.getenv("DB_NAME", "Gaming_Trend_Tracker")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")


def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )


def create_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS steam_games (
                id SERIAL PRIMARY KEY,
                steam_appid INTEGER UNIQUE,
                game_name TEXT,
                normalized_name TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.commit()


def fetch_steam_apps():
    if not STEAM_API_KEY:
        raise ValueError("Missing STEAM_API_KEY in .env file.")

    url = "https://api.steampowered.com/IStoreService/GetAppList/v1/"

    params = {
        "key": STEAM_API_KEY,
        "max_results": 50000
    }

    response = requests.get(
        url,
        params=params,
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    print("STATUS:", response.status_code)
    print(response.text[:200])

    response.raise_for_status()

    data = response.json()

    return data["response"]["apps"]


def save_apps(conn, apps):
    inserted = 0

    with conn.cursor() as cur:
        for app in apps:
            appid = app.get("appid")
            name = app.get("name", "").strip()

            if not appid or not name:
                continue

            normalized = normalize(name)

            cur.execute("""
                INSERT INTO steam_games
                (steam_appid, game_name, normalized_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (steam_appid)
                DO UPDATE SET
                    game_name = EXCLUDED.game_name,
                    normalized_name = EXCLUDED.normalized_name;
            """, (
                appid,
                name,
                normalized
            ))

            inserted += 1

    conn.commit()
    print(f"Saved/updated {inserted} Steam apps.")


def main():
    print("Pulling Steam app list...")

    apps = fetch_steam_apps()

    print(f"Fetched {len(apps)} Steam apps.")

    conn = get_connection()
    create_table(conn)
    save_apps(conn, apps)
    conn.close()

    print("Steam library build complete.")


if __name__ == "__main__":
    main()