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

KICK_CLIENT_ID = os.getenv("KICK_CLIENT_ID")
KICK_CLIENT_SECRET = os.getenv("KICK_CLIENT_SECRET")


def get_connection():
    log_security_event("DB_CONNECT", "Opening PostgreSQL connection for Kick trends")

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
            CREATE TABLE IF NOT EXISTS kick_trends (
                id SERIAL PRIMARY KEY,
                platform VARCHAR(50) DEFAULT 'Kick',
                game_name TEXT NOT NULL,
                viewer_count INTEGER,
                stream_count INTEGER,
                captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    conn.commit()

    log_security_event("DB_TABLE_CHECK", "Verified kick_trends table exists")


def get_kick_access_token():
    log_security_event("KICK_AUTH", "Requesting Kick app access token")

    url = "https://id.kick.com/oauth/token"

    data = {
        "client_id": KICK_CLIENT_ID,
        "client_secret": KICK_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }

    response = requests.post(url, data=data, timeout=20)

    if response.status_code >= 400:
        print("Kick auth failed:")
        print(response.status_code)
        print(response.text)

    response.raise_for_status()

    token_data = response.json()
    token = token_data.get("access_token")

    if not token:
        raise ValueError("Kick access token was not returned")

    log_security_event("KICK_AUTH_SUCCESS", "Kick app access token received")

    return token


def fetch_kick_livestreams(access_token):
    log_security_event("KICK_API_PULL", "Requesting Kick livestream data")

    url = "https://api.kick.com/public/v1/livestreams"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    params = {
        "limit": 100
    }

    response = requests.get(url, headers=headers, params=params, timeout=20)

    if response.status_code >= 400:
        print("Kick livestream request failed:")
        print(response.status_code)
        print(response.text)

    response.raise_for_status()

    data = response.json()

    if isinstance(data, dict):
        streams = data.get("data", [])
    elif isinstance(data, list):
        streams = data
    else:
        streams = []

    log_security_event("KICK_API_SUCCESS", f"Retrieved {len(streams)} Kick livestreams")

    return streams


def extract_game_name(stream):
    possible_fields = [
        "category",
        "categories",
        "subcategory",
        "game",
        "game_name"
    ]

    for field in possible_fields:
        value = stream.get(field)

        if isinstance(value, str) and value.strip():
            return value.strip().lower()

        if isinstance(value, dict):
            name = value.get("name") or value.get("slug")
            if name:
                return str(name).strip().lower()

        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                name = first.get("name") or first.get("slug")
                if name:
                    return str(name).strip().lower()

    return "unknown"


def extract_viewer_count(stream):
    possible_fields = [
        "viewer_count",
        "viewers",
        "live_viewers",
        "current_viewers"
    ]

    for field in possible_fields:
        value = stream.get(field)

        if value is not None:
            try:
                return int(value)
            except Exception:
                pass

    return 0


def analyze_kick_streams(streams):
    game_stats = defaultdict(lambda: {
        "viewer_count": 0,
        "stream_count": 0
    })

    for stream in streams:
        game_name = extract_game_name(stream)

        if not game_name or game_name == "unknown":
            continue

        viewers = extract_viewer_count(stream)

        game_stats[game_name]["viewer_count"] += viewers
        game_stats[game_name]["stream_count"] += 1

    log_security_event("KICK_ANALYSIS", f"Matched {len(game_stats)} Kick games")

    return game_stats


def save_results(conn, game_stats):
    captured_at = datetime.now()

    with conn.cursor() as cur:
        for game_name, stats in game_stats.items():
            cur.execute("""
                INSERT INTO kick_trends
                (platform, game_name, viewer_count, stream_count, captured_at)
                VALUES (%s, %s, %s, %s, %s);
            """, (
                "Kick",
                game_name,
                stats["viewer_count"],
                stats["stream_count"],
                captured_at
            ))

    conn.commit()

    log_security_event("KICK_DB_SAVE", f"Saved {len(game_stats)} Kick game records")


def main():
    log_security_event("KICK_RUN", "Kick trend pull started")

    conn = None

    try:
        if not KICK_CLIENT_ID:
            raise ValueError("Missing KICK_CLIENT_ID in .env file")

        if not KICK_CLIENT_SECRET:
            raise ValueError("Missing KICK_CLIENT_SECRET in .env file")

        if not DB_PASSWORD:
            raise ValueError("Missing DB_PASSWORD in .env file")

        conn = get_connection()
        create_table(conn)

        access_token = get_kick_access_token()
        streams = fetch_kick_livestreams(access_token)
        game_stats = analyze_kick_streams(streams)

        save_results(conn, game_stats)

        print("Kick trend pull complete.")
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
            "KICK_RUN_SUCCESS",
            f"Kick trend pull complete. Games tracked: {len(game_stats)}"
        )

    except Exception as e:
        log_security_event("KICK_RUN_ERROR", str(e))
        print(f"Kick trend pull failed: {e}")
        raise

    finally:
        if conn:
            conn.close()
            log_security_event("DB_CLOSE", "Closed PostgreSQL connection for Kick trends")


if __name__ == "__main__":
    main()