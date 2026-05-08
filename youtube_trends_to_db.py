import re
import time
from collections import Counter
from datetime import datetime, timedelta

import psycopg2
from googleapiclient.discovery import build


# =========================
# CONFIG
# =========================
API_KEY = "AIzaSyBa8nj7q6VAVd9j1b9uL1CTTom5omIBFNo"

DB_CONFIG = {
    "host": "localhost",
    "database": "YouTube_Data",
    "user": "postgres",
    "password": "Ironblooded2319!"
}

YOUTUBE = build("youtube", "v3", developerKey=API_KEY)

RUN_DURATION_HOURS = 1
PULL_INTERVAL_SECONDS = 600  # 10 minutes

# =========================
# HELPERS
# =========================
def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_game_library(conn):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT g.game_name, a.alias
        FROM games g
        JOIN game_aliases a ON g.id = a.game_id;
    """)

    rows = cursor.fetchall()
    cursor.close()

    game_library = {}

    for game_name, alias in rows:
        if game_name not in game_library:
            game_library[game_name] = []

        game_library[game_name].append(clean_text(alias))

    return game_library


def fetch_gaming_titles():
    request = YOUTUBE.videos().list(
        part="snippet",
        chart="mostPopular",
        regionCode="US",
        videoCategoryId="20",
        maxResults=25
    )

    response = request.execute()

    return [item["snippet"]["title"] for item in response.get("items", [])]


def match_games(video_titles, game_library):
    matches = Counter()

    for title in video_titles:
        cleaned_title = clean_text(title)

        for game_name, aliases in game_library.items():
            for alias in aliases:
                if alias in cleaned_title:
                    matches[game_name] += 1
                    break

    return matches


def save_unknown_terms(video_titles, game_library, conn):
    cursor = conn.cursor()

    stop_words = {
    "the", "and", "for", "with", "this", "that",
    "from", "your", "you", "are", "was", "have",
    "has", "had", "get", "got", "new", "best",
    "top", "today", "video", "videos", "gaming",
    "game", "games", "play", "playing", "player",
    "players", "stream", "streamer", "live",
    "update", "updates", "official", "review",
    "friends", "friend", "block", "life",
    "free", "every", "there", "episode",
    "world", "lucky", "crazy", "funny",
    "insane", "clips", "moments", "wins",
    "fails", "challenge", "shorts", "short",
    "vs", "win", "lose", "loses", "lost",
    "using", "use", "make", "made", "making",
    "watch", "watching", "shows", "show",
    "react", "reaction", "trailer"
}

    all_known_aliases = set()
    for aliases in game_library.values():
        all_known_aliases.update(aliases)

    for title in video_titles:
        words = clean_text(title).split()

        for word in words:
            if len(word) < 4 or word in stop_words or word in all_known_aliases:
                continue

            cursor.execute("""
                INSERT INTO unknown_terms (term, count)
                VALUES (%s, 1)
                ON CONFLICT (term)
                DO UPDATE SET
                    count = unknown_terms.count + 1,
                    last_seen = CURRENT_TIMESTAMP
            """, (word,))

    conn.commit()
    cursor.close()


def save_to_db(game_matches, total_videos, conn):
    cursor = conn.cursor()
    run_time = datetime.now()

    for game, count in game_matches.items():
        percentage = round((count / total_videos) * 100, 2)

        cursor.execute("""
            INSERT INTO trending_games 
            (run_time, game_name, mentions, total_videos, percentage)
            VALUES (%s, %s, %s, %s, %s)
        """, (run_time, game, count, total_videos, percentage))

    conn.commit()
    cursor.close()


def compare_latest_runs(conn):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT run_time
        FROM trending_games
        ORDER BY run_time DESC
        LIMIT 2;
    """)

    runs = cursor.fetchall()

    if len(runs) < 2:
        print("\nNot enough data yet to compare.")
        cursor.close()
        return

    current_run, previous_run = runs[0][0], runs[1][0]

    cursor.execute("""
        SELECT 
            current.game_name,
            current.mentions,
            current.percentage,
            COALESCE(previous.mentions, 0),
            current.mentions - COALESCE(previous.mentions, 0)
        FROM trending_games current
        LEFT JOIN trending_games previous
            ON current.game_name = previous.game_name
            AND previous.run_time = %s
        WHERE current.run_time = %s
        ORDER BY current.mentions DESC;
    """, (previous_run, current_run))

    print("\nMost Popular Games Right Now:\n")

    for game, mentions, pct, prev, change in cursor.fetchall():
        trend = "Trending Up" if change > 0 else "Declining" if change < 0 else "Stable"
        print(f"{game} — {mentions} videos ({pct}%) | Change: {change} — {trend}")

    cursor.close()


def run_single_pull():
    # Logging
    with open("run_log.txt", "a") as f:
        f.write(f"Run at {datetime.now()}\n")

    conn = None

    try:
        conn = psycopg2.connect(**DB_CONFIG)

        game_library = load_game_library(conn)
        titles = fetch_gaming_titles()

        matches = match_games(titles, game_library)

        save_unknown_terms(titles, game_library, conn)
        save_to_db(matches, len(titles), conn)
        compare_latest_runs(conn)

    except Exception as e:
        print(f"Script error: {e}")

    finally:
        if conn:
            conn.close()


def main():
    end_time = datetime.now() + timedelta(hours=RUN_DURATION_HOURS)

    print("Collector started\n")

    while datetime.now() < end_time:
        print(f"\nRunning pull at {datetime.now()}")
        run_single_pull()

        if datetime.now() < end_time:
            time.sleep(PULL_INTERVAL_SECONDS)

    print("\nFinished 1-hour session.")


if __name__ == "__main__":
    main()