import os
import re
from datetime import datetime
from collections import Counter

import psycopg2
from dotenv import load_dotenv
from googleapiclient.discovery import build


load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

DB_NAME = os.getenv("DB_NAME", "Gaming_Trend_Tracker")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

REGION_CODE = "US"
VIDEO_CATEGORY_ID = "20"
MAX_RESULTS = 50


MANUAL_GAME_LIBRARY = {
    "minecraft": ["minecraft"],
    "roblox": ["roblox"],
    "fortnite": ["fortnite"],
    "call of duty": ["call of duty", "cod", "warzone", "black ops", "bo6", "modern warfare", "mw3"],
    "grand theft auto": ["grand theft auto", "gta", "gta 5", "gta v", "gta 6"],
    "marvel rivals": ["marvel rivals"],
    "garry's mod": ["garrys mod", "garry's mod", "gmod"],
    "resident evil": ["resident evil", "leon kennedy"],
    "tomodachi life": ["tomodachi life", "tomodachi"],
    "genshin impact": ["genshin impact", "genshin"],
    "rainbow six siege": ["rainbow six", "rainbow 6", "r6 siege", "siege"],
    "counter-strike 2": ["counter strike", "counter-strike", "cs2", "csgo"],
    "subnautica": ["subnautica", "subnautica 2"],
    "baldi's basics": ["baldi's basics", "baldis basics", "baldi's basics plus"],
    "clash royale": ["clash royale"],
    "brawl stars": ["brawl stars"],
    "darktide": ["darktide", "warhammer darktide"],
    "forza horizon": ["forza horizon", "forza horizon 6", "fh6"],
    "dayz": ["dayz"],
    "escape from tarkov": ["escape from tarkov", "tarkov"],
    "rust": ["rust"]
}


IGNORE_WORDS = {
    "the", "and", "for", "with", "this", "that", "from", "you", "your",
    "new", "game", "games", "gaming", "play", "playing", "live", "stream",
    "best", "worst", "update", "trailer", "official", "funny", "video",
    "how", "why", "what", "when", "where", "ranked", "season", "part",
    "episode", "challenge", "today", "insane", "crazy", "first", "time",
    "breaks", "elemental", "luna", "lily", "exist", "wheel", "entire",
    "videogames", "xbox", "special", "coconut", "mode", "secret",
    "forever", "easiest", "goob", "stage", "garbage", "tried", "hunted",
    "they", "path", "waiting", "team", "captured", "program", "winnie",
    "thursday", "revealed", "retro", "specialprogram", "walker", "ever",
    "pals", "huge", "someone", "baby", "most", "hardest", "trust",
    "looking", "week", "ridiculous", "gang", "scary", "shorts", "clips",
    "reaction", "reacts", "moments", "viral", "fails", "wins", "news",
    "beta", "alpha", "access", "early", "edition", "ultimate", "controller",
    "keyboard", "mouse", "fps", "rpg", "mmo", "lets", "let", "got", "gets",
    "will", "can", "cant", "dont", "doesnt", "just", "like", "make", "made",
    "horror", "movie", "movies", "song", "music", "full", "free", "mobile"
}


def clean_text(text):
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r"#[a-zA-Z0-9_]+", lambda m: " " + m.group(0)[1:] + " ", text)
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


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
            CREATE TABLE IF NOT EXISTS trending_games (
                id SERIAL PRIMARY KEY,
                platform VARCHAR(50) DEFAULT 'YouTube',
                game_name VARCHAR(255),
                mentions INTEGER,
                percentage NUMERIC(6,2),
                total_videos INTEGER,
                run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_youtube_videos (
                id SERIAL PRIMARY KEY,
                video_id TEXT,
                title TEXT,
                tags TEXT,
                matched_games TEXT DEFAULT 'UNMATCHED',
                run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS unknown_terms (
                id SERIAL PRIMARY KEY,
                term TEXT UNIQUE,
                source_title TEXT,
                platform VARCHAR(50) DEFAULT 'YouTube',
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    conn.commit()


def load_game_library(conn):
    game_library = {}

    with conn.cursor() as cur:
        cur.execute("""
            SELECT game_name, alias
            FROM game_aliases
            WHERE game_name IS NOT NULL
              AND alias IS NOT NULL;
        """)
        alias_rows = cur.fetchall()

        cur.execute("""
            SELECT game_name, normalized_name
            FROM steam_games
            WHERE game_name IS NOT NULL
              AND normalized_name IS NOT NULL;
        """)
        steam_rows = cur.fetchall()

    for game_name, alias in alias_rows:
        clean_game = clean_text(game_name)
        clean_alias = clean_text(alias)

        if not clean_game or not clean_alias or len(clean_alias) < 3:
            continue

        if clean_game not in game_library:
            game_library[clean_game] = set()

        game_library[clean_game].add(clean_alias)

    for game_name, normalized_name in steam_rows:
        clean_game = clean_text(game_name)
        clean_alias = clean_text(normalized_name)

        if not clean_game or not clean_alias or len(clean_alias) < 3:
            continue

        if clean_game not in game_library:
            game_library[clean_game] = set()

        game_library[clean_game].add(clean_alias)

    for game_name, aliases in MANUAL_GAME_LIBRARY.items():
        clean_game = clean_text(game_name)

        if clean_game not in game_library:
            game_library[clean_game] = set()

        for alias in aliases:
            clean_alias = clean_text(alias)

            if len(clean_alias) >= 3:
                game_library[clean_game].add(clean_alias)

    return {
        game: sorted(list(aliases), key=len, reverse=True)
        for game, aliases in game_library.items()
    }


def fetch_youtube_videos():
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    request = youtube.videos().list(
        part="snippet",
        chart="mostPopular",
        regionCode=REGION_CODE,
        videoCategoryId=VIDEO_CATEGORY_ID,
        maxResults=MAX_RESULTS
    )

    response = request.execute()
    return response.get("items", [])


def match_games(text, game_library):
    cleaned = clean_text(text)
    matched_games = []

    for game, aliases in game_library.items():
        for alias in aliases:
            pattern = r"\b" + re.escape(alias) + r"\b"

            if re.search(pattern, cleaned):
                matched_games.append(game)
                break

    return matched_games


def extract_possible_unknown_terms(text):
    cleaned = clean_text(text)
    words = cleaned.split()

    possible_terms = []

    for word in words:
        if len(word) >= 4 and word not in IGNORE_WORDS and not word.isdigit():
            possible_terms.append(word)

    return possible_terms[:10]


def save_results(conn, videos, game_counter, total_videos):
    run_timestamp = datetime.now()

    with conn.cursor() as cur:
        for game, mentions in game_counter.items():
            percentage = round((mentions / total_videos) * 100, 2) if total_videos else 0

            cur.execute("""
                INSERT INTO trending_games
                (platform, game_name, mentions, percentage, total_videos, run_timestamp)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (
                "YouTube",
                game,
                mentions,
                percentage,
                total_videos,
                run_timestamp
            ))

        for video in videos:
            matched_games_text = (
                ", ".join(video.get("matched_games", []))
                if video.get("matched_games")
                else "UNMATCHED"
            )

            cur.execute("""
                INSERT INTO raw_youtube_videos
                (video_id, title, tags, matched_games, run_timestamp)
                VALUES (%s, %s, %s, %s, %s);
            """, (
                video.get("video_id"),
                video.get("title"),
                ", ".join(video.get("tags", [])),
                matched_games_text,
                run_timestamp
            ))

            if matched_games_text == "UNMATCHED":
                unknown_terms = extract_possible_unknown_terms(
                    video.get("title", "") + " " + " ".join(video.get("tags", []))
                )

                for term in unknown_terms:
                    cur.execute("""
                        INSERT INTO unknown_terms
                        (term, source_title, platform, detected_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (term) DO NOTHING;
                    """, (
                        term,
                        video.get("title"),
                        "YouTube",
                        run_timestamp
                    ))

    conn.commit()


def main():
    if not YOUTUBE_API_KEY:
        raise ValueError("Missing YOUTUBE_API_KEY in .env file.")

    conn = get_connection()
    create_tables(conn)

    game_library = load_game_library(conn)
    print(f"Loaded {len(game_library)} games from RAWG/manual aliases + Steam library.")

    items = fetch_youtube_videos()

    processed_videos = []
    game_counter = Counter()

    for item in items:
        snippet = item.get("snippet", {})

        video_id = item.get("id")
        title = snippet.get("title", "")
        tags = snippet.get("tags", [])

        combined_text = title + " " + " ".join(tags)
        matched_games = match_games(combined_text, game_library)

        for game in matched_games:
            game_counter[game] += 1

        processed_videos.append({
            "video_id": video_id,
            "title": title,
            "tags": tags,
            "matched_games": matched_games
        })

    total_videos = len(processed_videos)

    save_results(conn, processed_videos, game_counter, total_videos)

    conn.close()

    print("YouTube trend pull complete.")
    print(f"Total videos checked: {total_videos}")
    print(f"Matched games found: {len(game_counter)}")
    print()

    print("Top matched games:")
    for game, count in game_counter.most_common(10):
        percentage = round((count / total_videos) * 100, 2) if total_videos else 0
        print(f"{game}: {count}/{total_videos} videos — {percentage}%")

    print()
    print("Check unmatched videos with:")
    print("""
SELECT title, tags
FROM raw_youtube_videos
WHERE matched_games = 'UNMATCHED'
ORDER BY run_timestamp DESC
LIMIT 25;
""")


if __name__ == "__main__":
    main()