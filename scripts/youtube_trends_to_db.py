import os
import re
from collections import Counter
from datetime import datetime

import psycopg2
from dotenv import load_dotenv
from googleapiclient.discovery import build
import requests

from security_logger import log_security_event


# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv()


# =========================
# CONFIG
# =========================
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
RAWG_API_KEY = os.getenv("RAWG_API_KEY")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

if not YOUTUBE_API_KEY:
    log_security_event("CONFIG_ERROR", "Missing YOUTUBE_API_KEY in .env file")
    raise ValueError("Missing YOUTUBE_API_KEY in .env file")

if not RAWG_API_KEY:
    log_security_event("CONFIG_ERROR", "Missing RAWG_API_KEY in .env file")
    raise ValueError("Missing RAWG_API_KEY in .env file")

if not DB_CONFIG["password"]:
    log_security_event("CONFIG_ERROR", "Missing DB_PASSWORD in .env file")
    raise ValueError("Missing DB_PASSWORD in .env file")


# =========================
# YOUTUBE API
# =========================
YOUTUBE = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


# =========================
# GAME LIBRARY
# =========================
GAME_LIBRARY = {
    "minecraft": ["minecraft", "mc"],
    "roblox": ["roblox"],
    "fortnite": ["fortnite"],
    "call of duty": ["call of duty", "cod", "warzone", "black ops", "modern warfare"],
    "grand theft auto": ["gta", "gta v", "gta 5", "grand theft auto"],
    "valorant": ["valorant"],
    "counter-strike": ["cs2", "csgo", "counter strike"],
    "league of legends": ["league of legends", "lol"],
    "world of warcraft": ["world of warcraft", "wow"],
    "elden ring": ["elden ring"],
    "marvel rivals": ["marvel rivals"],
    "overwatch 2": ["overwatch", "overwatch 2"],
    "apex legends": ["apex legends", "apex"],
    "rocket league": ["rocket league"],
    "destiny 2": ["destiny 2", "destiny"],
    "palworld": ["palworld"],
    "rainbow six siege": ["rainbow six", "r6", "siege"],
    "helldivers 2": ["helldivers", "helldivers 2"]
}


# =========================
# CLEAN TEXT
# =========================
def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    return text


# =========================
# RAWG API LOOKUP
# =========================
def fetch_rawg_data(game_name):
    try:
        log_security_event("RAWG_LOOKUP", f"Looking up RAWG data for {game_name}")

        url = "https://api.rawg.io/api/games"

        params = {
            "key": RAWG_API_KEY,
            "search": game_name,
            "page_size": 1
        }

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if not data.get("results"):
            log_security_event("RAWG_LOOKUP_WARNING", f"No RAWG results found for {game_name}")
            return {}

        game = data["results"][0]

        platforms = ", ".join(
            p["platform"]["name"]
            for p in game.get("platforms", [])
        )

        genres = ", ".join(
            g["name"]
            for g in game.get("genres", [])
        )

        return {
            "rawg_name": game.get("name"),
            "released": game.get("released"),
            "rating": game.get("rating"),
            "metacritic": game.get("metacritic"),
            "platforms": platforms,
            "genres": genres,
            "background_image": game.get("background_image")
        }

    except Exception as e:
        log_security_event("RAWG_ERROR", f"RAWG lookup failed for {game_name}: {e}")
        print(f"RAWG lookup failed for {game_name}: {e}")
        return {}


# =========================
# FETCH TRENDING VIDEOS
# =========================
def fetch_trending_videos():
    log_security_event("API_PULL", "Requesting YouTube trending gaming videos")

    request = YOUTUBE.videos().list(
        part="snippet",
        chart="mostPopular",
        regionCode="US",
        videoCategoryId="20",
        maxResults=25
    )

    response = request.execute()

    video_titles = []

    for item in response["items"]:
        title = item["snippet"]["title"]
        video_titles.append(title)

    log_security_event("API_PULL_SUCCESS", f"Fetched {len(video_titles)} YouTube videos")

    return video_titles


# =========================
# ANALYZE GAME TRENDS
# =========================
def analyze_trends(video_titles):
    log_security_event("ANALYSIS_START", "Analyzing YouTube video titles")

    counts = Counter()

    for title in video_titles:
        cleaned_title = clean_text(title)

        for game_name, aliases in GAME_LIBRARY.items():
            for alias in aliases:
                if alias in cleaned_title:
                    counts[game_name] += 1
                    break

    log_security_event("ANALYSIS_SUCCESS", f"Matched {len(counts)} games")

    return counts


# =========================
# SAVE TO DATABASE
# =========================
def save_to_database(counts, total_videos):
    log_security_event("DB_CONNECT", "Connecting to PostgreSQL")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    current_time = datetime.now()

    for game_name, mentions in counts.items():
        percentage = round((mentions / total_videos) * 100, 2)

        rawg_data = fetch_rawg_data(game_name)

        cursor.execute("""
            INSERT INTO trending_games (
                game_name,
                mentions,
                total_videos,
                percentage,
                run_time,
                rawg_name,
                released,
                rating,
                metacritic,
                platforms,
                genres,
                background_image
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            game_name,
            mentions,
            total_videos,
            percentage,
            current_time,
            rawg_data.get("rawg_name"),
            rawg_data.get("released"),
            rawg_data.get("rating"),
            rawg_data.get("metacritic"),
            rawg_data.get("platforms"),
            rawg_data.get("genres"),
            rawg_data.get("background_image")
        ))

    conn.commit()
    cursor.close()
    conn.close()

    log_security_event("DB_SAVE_SUCCESS", f"Saved {len(counts)} game trend records to database")


# =========================
# MAIN
# =========================
def main():
    try:
        log_security_event("PROJECT_RUN", "YouTube trend collection started")

        print("Fetching trending YouTube gaming videos...")

        video_titles = fetch_trending_videos()

        print(f"Fetched {len(video_titles)} videos.")

        counts = analyze_trends(video_titles)

        print("\nTrending Games:")

        for game, mentions in counts.most_common():
            print(f"{game}: {mentions}")

        save_to_database(counts, len(video_titles))

        print("\nTrend data saved successfully.")

        log_security_event("PROJECT_RUN_SUCCESS", "YouTube trend collection completed successfully")

    except Exception as e:
        log_security_event("PROJECT_RUN_ERROR", str(e))
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()