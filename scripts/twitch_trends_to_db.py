import os
from collections import defaultdict
from datetime import datetime

import psycopg2
import requests
from dotenv import load_dotenv

from security_logger import log_security_event


load_dotenv()

DB_NAME = os.getenv("DB_NAME", "Gaming_Trend_Tracker")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")


def get_connection():
    log_security_event("DB_CONNECT", "Opening PostgreSQL connection for Twitch trends")

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
            CREATE TABLE IF NOT EXISTS twitch_trends (
                id SERIAL PRIMARY KEY,
                platform VARCHAR(50) DEFAULT 'Twitch',
                game_name TEXT NOT NULL,
                viewer_count INTEGER,
                stream_count INTEGER,
                captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    conn.commit()

    log_security_event("DB_TABLE_CHECK", "Verified twitch_trends table exists")


def get_twitch_access_token():
    log_security_event("TWITCH_AUTH", "Requesting Twitch app access token")

    url = "https://id.twitch.tv/oauth2/token"

    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }

    response = requests.post(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    token = data.get("access_token")

    if not token:
        raise ValueError("Twitch access token was not returned")

    log_security_event("TWITCH_AUTH_SUCCESS", "Twitch app access token received")

    return token


def fetch_top_twitch_streams(access_token):
    log_security_event("TWITCH_API_PULL", "Requesting top Twitch live streams")

    url = "https://api.twitch.tv/helix/streams"

    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }

    params = {
        "first": 100,
        "language": "en"
    }

    response = requests.get(url, headers=headers, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    streams = data.get("data", [])

    log_security_event("TWITCH_API_SUCCESS", f"Retrieved {len(streams)} Twitch streams")

    return streams


def analyze_twitch_streams(streams):
    game_stats = defaultdict(lambda: {
        "viewer_count": 0,
        "stream_count": 0
    })

    for stream in streams:
        game_name = stream.get("game_name")

        if not game_name:
            continue

        viewers = stream.get("viewer_count", 0)

        game_key = game_name.lower().strip()

        game_stats[game_key]["viewer_count"] += viewers
        game_stats[game_key]["stream_count"] += 1

    log_security_event("TWITCH_ANALYSIS", f"Matched {len(game_stats)} Twitch games")

    return game_stats


def save_results(conn, game_stats):
    captured_at = datetime.now()

    with conn.cursor() as cur:
        for game_name, stats in game_stats.items():
            cur.execute("""
                INSERT INTO twitch_trends
                (platform, game_name, viewer_count, stream_count, captured_at)
                VALUES (%s, %s, %s, %s, %s);
            """, (
                "Twitch",
                game_name,
                stats["viewer_count"],
                stats["stream_count"],
                captured_at
            ))

    conn.commit()

    log_security_event("TWITCH_DB_SAVE", f"Saved {len(game_stats)} Twitch game records")


def main():
    log_security_event("TWITCH_RUN", "Twitch trend pull started")

    conn = None

    try:
        if not TWITCH_CLIENT_ID:
            raise ValueError("Missing TWITCH_CLIENT_ID in .env file")

        if not TWITCH_CLIENT_SECRET:
            raise ValueError("Missing TWITCH_CLIENT_SECRET in .env file")

        if not DB_PASSWORD:
            raise ValueError("Missing DB_PASSWORD in .env file")

        conn = get_connection()
        create_table(conn)

        access_token = get_twitch_access_token()
        streams = fetch_top_twitch_streams(access_token)
        game_stats = analyze_twitch_streams(streams)

        save_results(conn, game_stats)

        print("Twitch trend pull complete.")
        print(f"Games tracked: {len(game_stats)}")

        for game, stats in sorted(
            game_stats.items(),
            key=lambda item: item[1]["viewer_count"],
            reverse=True
        )[:10]:
            print(
                f"{game.title()}: "
                f"{stats['viewer_count']:,} viewers across "
                f"{stats['stream_count']} streams"
            )

        log_security_event(
            "TWITCH_RUN_SUCCESS",
            f"Twitch trend pull complete. Games tracked: {len(game_stats)}"
        )

    except Exception as e:
        log_security_event("TWITCH_RUN_ERROR", str(e))
        print(f"Twitch trend pull failed: {e}")
        raise

    finally:
        if conn:
            conn.close()
            log_security_event("DB_CLOSE", "Closed PostgreSQL connection for Twitch trends")


if __name__ == "__main__":
    main()