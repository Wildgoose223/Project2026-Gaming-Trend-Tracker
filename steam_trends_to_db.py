import os
from datetime import datetime

import requests
import psycopg2
from dotenv import load_dotenv


load_dotenv()

DB_NAME = os.getenv("DB_NAME", "Gaming_Trend_Tracker")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")


STEAM_GAMES = {
    "counter-strike 2": 730,
    "dota 2": 570,
    "pubg": 578080,
    "apex legends": 1172470,
    "rust": 252490,
    "destiny 2": 1085660,
    "grand theft auto": 271590,
    "warframe": 230410,
    "team fortress 2": 440,
    "rainbow six siege": 359550,
    "elden ring": 1245620,
    "baldur's gate 3": 1086940,
    "stardew valley": 413150,
    "terraria": 105600,
    "palworld": 1623730,
    "helldivers 2": 553850,
    "marvel rivals": 2767030
}


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
            CREATE TABLE IF NOT EXISTS steam_trends (
                id SERIAL PRIMARY KEY,
                platform VARCHAR(50) DEFAULT 'Steam',
                game_name TEXT NOT NULL,
                steam_appid INTEGER NOT NULL,
                current_players INTEGER,
                captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.commit()


def get_current_players(appid):
    url = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"

    params = {
        "appid": appid,
        "format": "json"
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()

    return data.get("response", {}).get("player_count")


def save_result(conn, game_name, appid, current_players):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO steam_trends
            (platform, game_name, steam_appid, current_players, captured_at)
            VALUES (%s, %s, %s, %s, %s);
        """, (
            "Steam",
            game_name,
            appid,
            current_players,
            datetime.now()
        ))

    conn.commit()


def main():
    conn = get_connection()
    create_table(conn)

    for game_name, appid in STEAM_GAMES.items():
        try:
            players = get_current_players(appid)
            save_result(conn, game_name, appid, players)
            print(f"{game_name}: {players} current players")

        except Exception as e:
            print(f"Failed for {game_name}: {e}")

    conn.close()
    print("Steam trend pull complete.")


if __name__ == "__main__":
    main()