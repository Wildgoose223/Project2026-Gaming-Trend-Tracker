import os
import re
import pandas as pd
import psycopg2
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("DB_NAME", "Gaming_Trend_Tracker")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")


GAME_META = {
    "minecraft": {
        "platforms": "PC, Xbox, PlayStation, Nintendo Switch, Mobile",
        "genres": "Sandbox, Survival, Adventure",
        "released": "2011-11-18",
        "rating": "4.4",
        "metacritic": "83",
        "description": "A sandbox survival game focused on building, crafting, exploration, and player creativity."
    },
    "roblox": {
        "platforms": "PC, Xbox, PlayStation, Mobile",
        "genres": "Platform, Sandbox, Creation",
        "released": "2006-09-01",
        "rating": "3.8",
        "metacritic": "N/A",
        "description": "A user-generated game platform where players create and play millions of different experiences."
    },
    "grand theft auto": {
        "platforms": "PC, Xbox, PlayStation",
        "genres": "Action, Open World, Crime",
        "released": "2013-09-17",
        "rating": "4.5",
        "metacritic": "97",
        "description": "An open-world action crime game known for driving, missions, online play, and sandbox chaos."
    },
    "subnautica": {
        "platforms": "PC, Xbox, PlayStation, Switch",
        "genres": "Survival, Adventure",
        "released": "2018-01-23",
        "rating": "4.3",
        "metacritic": "87",
        "description": "An underwater survival adventure game focused on exploration, crafting, and mystery."
    },
    "call of duty": {
        "platforms": "PC, Xbox, PlayStation",
        "genres": "Shooter, Action",
        "released": "2003-10-29",
        "rating": "4.0",
        "metacritic": "N/A",
        "description": "A military shooter franchise focused on multiplayer, campaigns, Warzone, and competitive action."
    },
    "rainbow six siege": {
        "platforms": "PC, Xbox, PlayStation",
        "genres": "Shooter, Tactical",
        "released": "2015-12-01",
        "rating": "3.8",
        "metacritic": "73",
        "description": "A tactical team-based shooter built around operators, gadgets, destruction, and strategy."
    },
    "marvel rivals": {
        "platforms": "PC, Xbox, PlayStation",
        "genres": "Hero Shooter, Action",
        "released": "2024-12-06",
        "rating": "N/A",
        "metacritic": "N/A",
        "description": "A superhero team shooter featuring Marvel characters, abilities, team fights, and objective play."
    },
    "league of legends": {
        "platforms": "PC",
        "genres": "MOBA, Strategy",
        "released": "2009-10-27",
        "rating": "3.6",
        "metacritic": "78",
        "description": "A competitive MOBA where two teams battle using champions, lanes, items, and objectives."
    },
    "among us": {
        "platforms": "PC, Xbox, PlayStation, Switch, Mobile",
        "genres": "Party, Social Deduction",
        "released": "2018-06-15",
        "rating": "3.7",
        "metacritic": "85",
        "description": "A social deduction party game where crewmates find impostors before being eliminated."
    },
    "counter strike 2": {
        "platforms": "PC",
        "genres": "Shooter, Competitive",
        "released": "2023-09-27",
        "rating": "N/A",
        "metacritic": "N/A",
        "description": "A competitive tactical FPS focused on precision shooting, economy, teamwork, and ranked matches."
    },
    "dota 2": {
        "platforms": "PC",
        "genres": "MOBA, Strategy",
        "released": "2013-07-09",
        "rating": "3.0",
        "metacritic": "90",
        "description": "A complex competitive MOBA built around heroes, lanes, team fights, and deep strategy."
    },
    "rust": {
        "platforms": "PC, Xbox, PlayStation",
        "genres": "Survival, Multiplayer",
        "released": "2018-02-08",
        "rating": "3.7",
        "metacritic": "69",
        "description": "A multiplayer survival game focused on gathering, base building, raids, crafting, and PvP."
    },
    "apex legends": {
        "platforms": "PC, Xbox, PlayStation, Switch",
        "genres": "Battle Royale, Shooter",
        "released": "2019-02-04",
        "rating": "3.7",
        "metacritic": "89",
        "description": "A fast battle royale hero shooter with squads, legends, abilities, and movement-heavy combat."
    },
    "stardew valley": {
        "platforms": "PC, Xbox, PlayStation, Switch, Mobile",
        "genres": "Farming, RPG, Simulation",
        "released": "2016-02-26",
        "rating": "4.4",
        "metacritic": "89",
        "description": "A farming life sim with crops, mining, fishing, relationships, crafting, and town progression."
    },
    "warframe": {
        "platforms": "PC, Xbox, PlayStation, Switch",
        "genres": "Action, Shooter, MMO",
        "released": "2013-03-25",
        "rating": "3.7",
        "metacritic": "69",
        "description": "A free-to-play sci-fi action game focused on fast combat, loot, missions, and character builds."
    },
    "pubg": {
        "platforms": "PC, Xbox, PlayStation, Mobile",
        "genres": "Battle Royale, Shooter",
        "released": "2017-12-20",
        "rating": "3.3",
        "metacritic": "86",
        "description": "A battle royale shooter where players loot, survive, and fight to be the last one standing."
    }
}


def get_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def image_for_game(game_name):
    slug = slugify(game_name)

    possible = [
        f"Images/{slug}.jpg",
        f"Images/{slug}.png",
        f"images/{slug}.jpg",
        f"images/{slug}.png"
    ]

    for path in possible:
        if os.path.exists(path):
            return path.replace("\\", "/")

    return ""


def fmt_num(value):
    try:
        if value is None or pd.isna(value):
            return "N/A"
        return f"{int(value):,}"
    except Exception:
        return "N/A"


def get_youtube_trends(conn, days=7, limit=10):
    query = """
        SELECT
            LOWER(game_name) AS game_name,
            SUM(mentions) AS youtube_mentions
        FROM trending_games
        WHERE run_timestamp >= NOW() - INTERVAL %s
        GROUP BY LOWER(game_name)
        ORDER BY youtube_mentions DESC
        LIMIT %s;
    """
    return pd.read_sql(query, conn, params=(f"{days} days", limit))


def get_steam_trends(conn, limit=10):
    query = """
        SELECT DISTINCT ON (LOWER(game_name))
            LOWER(game_name) AS game_name,
            current_players
        FROM steam_trends
        ORDER BY LOWER(game_name), captured_at DESC;
    """

    try:
        df = pd.read_sql(query, conn)
        return df.sort_values("current_players", ascending=False).head(limit)
    except Exception:
        return pd.DataFrame(columns=["game_name", "current_players"])


def get_latest_change(conn):
    query = """
        WITH latest_runs AS (
            SELECT DISTINCT run_timestamp
            FROM trending_games
            ORDER BY run_timestamp DESC
            LIMIT 2
        ),
        ranked_runs AS (
            SELECT
                run_timestamp,
                ROW_NUMBER() OVER (ORDER BY run_timestamp DESC) AS run_rank
            FROM latest_runs
        ),
        current_run AS (
            SELECT LOWER(game_name) AS game_name, SUM(mentions) AS mentions
            FROM trending_games t
            JOIN ranked_runs r ON t.run_timestamp = r.run_timestamp
            WHERE r.run_rank = 1
            GROUP BY LOWER(game_name)
        ),
        previous_run AS (
            SELECT LOWER(game_name) AS game_name, SUM(mentions) AS mentions
            FROM trending_games t
            JOIN ranked_runs r ON t.run_timestamp = r.run_timestamp
            WHERE r.run_rank = 2
            GROUP BY LOWER(game_name)
        )
        SELECT
            c.game_name,
            c.mentions - COALESCE(p.mentions, 0) AS change
        FROM current_run c
        LEFT JOIN previous_run p ON c.game_name = p.game_name;
    """

    try:
        return pd.read_sql(query, conn)
    except Exception:
        return pd.DataFrame(columns=["game_name", "change"])


def trend_label(change):
    if change > 0:
        return "Trending Up", "up"
    if change < 0:
        return "Declining", "down"
    return "Stable", "stable"


def compare_trends(youtube_df, steam_df):
    y_games = set(youtube_df["game_name"]) if not youtube_df.empty else set()
    s_games = set(steam_df["game_name"]) if not steam_df.empty else set()

    both = sorted(y_games.intersection(s_games))
    youtube_only = sorted(y_games - s_games)
    steam_only = sorted(s_games - y_games)

    return both, youtube_only, steam_only


def make_chart(df, x_col, y_col, title):
    if df.empty:
        return "<p>No chart data yet.</p>"

    fig = px.bar(
        df,
        x=x_col,
        y=y_col,
        text=y_col,
        title=title
    )

    fig.update_layout(
        height=340,
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=30, r=30, t=55, b=40)
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def youtube_table(df, change_map):
    if df.empty:
        return "<p>No YouTube data yet.</p>"

    rows = ""

    for i, row in df.iterrows():
        game = row["game_name"]
        change = change_map.get(game, 0)
        status, status_class = trend_label(change)

        rows += f"""
        <tr>
            <td>#{i + 1}</td>
            <td>{game.title()}</td>
            <td>{fmt_num(row["youtube_mentions"])}</td>
            <td class="{status_class}">{status} ({change:+})</td>
        </tr>
        """

    return f"""
    <table>
        <tr>
            <th>Rank</th>
            <th>Game</th>
            <th>YouTube Mentions</th>
            <th>Momentum</th>
        </tr>
        {rows}
    </table>
    """


def steam_table(df):
    if df.empty:
        return "<p>No Steam data yet.</p>"

    rows = ""

    for i, row in df.iterrows():
        rows += f"""
        <tr>
            <td>#{i + 1}</td>
            <td>{row["game_name"].title()}</td>
            <td>{fmt_num(row["current_players"])}</td>
        </tr>
        """

    return f"""
    <table>
        <tr>
            <th>Rank</th>
            <th>Game</th>
            <th>Current Steam Players</th>
        </tr>
        {rows}
    </table>
    """


def simple_list(items):
    if not items:
        return "<p>None found yet.</p>"

    return "<ul>" + "".join(f"<li>{x.title()}</li>" for x in items) + "</ul>"


def build_game_cards(youtube_df, steam_df, change_map):
    combined_games = []

    for game in youtube_df["game_name"].tolist():
        if game not in combined_games:
            combined_games.append(game)

    for game in steam_df["game_name"].tolist():
        if game not in combined_games:
            combined_games.append(game)

    steam_map = {
        row["game_name"]: row["current_players"]
        for _, row in steam_df.iterrows()
    }

    youtube_map = {
        row["game_name"]: row["youtube_mentions"]
        for _, row in youtube_df.iterrows()
    }

    cards = ""

    for game in combined_games[:12]:
        game_title = game.title()
        meta = GAME_META.get(game, {
            "platforms": "Metadata not loaded yet",
            "genres": "Metadata not loaded yet",
            "released": "N/A",
            "rating": "N/A",
            "metacritic": "N/A",
            "description": "Description not loaded yet. Add this game to GAME_META or connect full RAWG API metadata later."
        })

        change = change_map.get(game, 0)
        status, status_class = trend_label(change)
        img = image_for_game(game)

        if img:
            image_html = f'<img src="{img}" class="game-img">'
        else:
            image_html = f'<div class="game-img placeholder">{game_title}</div>'

        cards += f"""
        <div class="game-card">
            {image_html}
            <div class="card-body">
                <h3>{game_title}</h3>
                <p class="description">{meta["description"]}</p>

                <div class="mini-stats">
                    <div><strong>{fmt_num(youtube_map.get(game))}</strong><span>YouTube</span></div>
                    <div><strong>{fmt_num(steam_map.get(game))}</strong><span>Steam</span></div>
                    <div><strong>{change:+}</strong><span>Change</span></div>
                </div>

                <div class="status {status_class}">{status}</div>

                <div class="meta">
                    <p><strong>Platforms:</strong> {meta["platforms"]}</p>
                    <p><strong>Genres:</strong> {meta["genres"]}</p>
                    <p><strong>Released:</strong> {meta["released"]}</p>
                    <p><strong>RAWG Rating:</strong> {meta["rating"]}</p>
                    <p><strong>Metacritic:</strong> {meta["metacritic"]}</p>
                </div>
            </div>
        </div>
        """

    return cards


def build_summary(youtube_df, steam_df, both, steam_only):
    top_youtube = youtube_df.iloc[0]["game_name"].title() if not youtube_df.empty else "N/A"
    top_steam = steam_df.iloc[0]["game_name"].title() if not steam_df.empty else "N/A"

    summary = f"""
    <p>
        <strong>{top_youtube}</strong> is leading YouTube attention, while
        <strong>{top_steam}</strong> is leading Steam player demand.
    </p>
    <p>
        Games appearing on both lists are stronger trend signals because they have both content attention and active players.
        Steam-only games matter too because they may be popular with players even if YouTube is not talking about them much.
    </p>
    """

    if both:
        summary += f"<p><strong>Hot on both:</strong> {', '.join(x.title() for x in both[:5])}</p>"

    if steam_only:
        summary += f"<p><strong>Steam breakout signal:</strong> {', '.join(x.title() for x in steam_only[:5])}</p>"

    return summary


def build_dashboard(days=7):
    conn = get_connection()

    youtube_df = get_youtube_trends(conn, days, 10)
    steam_df = get_steam_trends(conn, 10)
    changes_df = get_latest_change(conn)

    conn.close()

    change_map = {
        row["game_name"]: int(row["change"])
        for _, row in changes_df.iterrows()
    }

    both, youtube_only, steam_only = compare_trends(youtube_df, steam_df)

    view_name = "Today" if days == 1 else f"Last {days} Days"

    youtube_chart = make_chart(
        youtube_df,
        "game_name",
        "youtube_mentions",
        f"YouTube Mentions - {view_name}"
    )

    steam_chart = make_chart(
        steam_df,
        "game_name",
        "current_players",
        "Steam Current Players"
    )

    cards = build_game_cards(youtube_df, steam_df, change_map)
    summary = build_summary(youtube_df, steam_df, both, steam_only)

    html = f"""
<!DOCTYPE html>
<html>
<head>
<title>Project2026 Gaming Trend Tracker</title>
<style>
body {{
    background:
        radial-gradient(circle at top left, rgba(56,189,248,.16), transparent 30%),
        radial-gradient(circle at top right, rgba(99,102,241,.14), transparent 28%),
        linear-gradient(135deg, #020617, #0f172a 50%, #111827);
    color: #e5e7eb;
    font-family: Arial, sans-serif;
    padding: 24px;
    margin: 0;
}}

h1 {{
    color: #38bdf8;
    margin-bottom: 4px;
}}

.subtitle {{
    color: #94a3b8;
    margin-bottom: 16px;
}}

.buttons a {{
    display: inline-block;
    background: #1e293b;
    color: white;
    padding: 10px 16px;
    margin-right: 8px;
    border-radius: 8px;
    text-decoration: none;
    border: 1px solid #334155;
}}

.panel,
.game-card {{
    background: rgba(15,23,42,.94);
    border: 1px solid #334155;
    border-radius: 16px;
    box-shadow: 0 12px 30px rgba(0,0,0,.28);
}}

.panel {{
    padding: 18px;
    margin-top: 18px;
}}

.grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 18px;
}}

.card-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
    margin-top: 18px;
}}

.explain {{
    color: #cbd5e1;
    line-height: 1.5;
}}

.summary-text {{
    color: #dbeafe;
    line-height: 1.6;
    background: rgba(2,6,23,.45);
    border-left: 4px solid #38bdf8;
    padding: 14px;
    border-radius: 10px;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
}}

th,
td {{
    border-bottom: 1px solid #334155;
    padding: 10px;
    text-align: left;
}}

th {{
    color: #38bdf8;
}}

.up {{
    color: #4ade80;
}}

.down {{
    color: #f87171;
}}

.stable {{
    color: #facc15;
}}

.game-card {{
    overflow: hidden;
}}

.game-img {{
    width: 100%;
    height: 145px;
    object-fit: cover;
    display: block;
}}

.placeholder {{
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #1e3a8a, #020617);
    color: #93c5fd;
    font-size: 22px;
    font-weight: bold;
}}

.card-body {{
    padding: 16px;
}}

.card-body h3 {{
    margin: 0 0 8px 0;
    font-size: 22px;
}}

.description {{
    color: #cbd5e1;
    font-size: 13px;
    line-height: 1.45;
    min-height: 58px;
}}

.mini-stats {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin: 14px 0;
}}

.mini-stats div {{
    background: #020617;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 10px;
    text-align: center;
}}

.mini-stats strong {{
    display: block;
    color: white;
    font-size: 15px;
}}

.mini-stats span {{
    font-size: 10px;
    color: #94a3b8;
}}

.status {{
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: bold;
    margin-bottom: 8px;
    background: #020617;
    border: 1px solid #334155;
}}

.meta p {{
    color: #cbd5e1;
    font-size: 12px;
    margin: 6px 0;
}}

.meta strong {{
    color: #38bdf8;
}}

li {{
    margin: 7px 0;
}}

@media (max-width: 1000px) {{
    .grid,
    .card-grid {{
        grid-template-columns: 1fr;
    }}
}}
</style>
</head>

<body>

<h1>Project2026 Gaming Trend Tracker</h1>
<p class="subtitle">Tracking gaming trends across YouTube, Steam, RAWG-style metadata, and future sources.</p>

<div class="buttons">
    <a href="dashboard_today.html">Today</a>
    <a href="dashboard_week.html">7 Days</a>
    <a href="dashboard_month.html">30 Days</a>
</div>

<div class="panel">
    <h2>Current View: {view_name}</h2>
    <p class="explain">
        YouTube shows content attention. Steam shows active player demand.
        RAWG-style cards explain what each game is, what platforms it is on, and why it matters.
    </p>
</div>

<div class="panel">
    <h2>Trend Summary</h2>
    <div class="summary-text">
        {summary}
    </div>
</div>

<div class="grid">
    <div class="panel">
        <h2>YouTube Trend Graph</h2>
        {youtube_chart}
    </div>

    <div class="panel">
        <h2>Steam Player Graph</h2>
        {steam_chart}
    </div>
</div>

<div class="grid">
    <div class="panel">
        <h2>YouTube Trends</h2>
        <p class="explain">Content attention: what people are watching and talking about.</p>
        {youtube_table(youtube_df, change_map)}
    </div>

    <div class="panel">
        <h2>Steam Trends</h2>
        <p class="explain">Player demand: what people are actively playing on Steam.</p>
        {steam_table(steam_df)}
    </div>
</div>

<div class="grid">
    <div class="panel">
        <h2>Hot on Both</h2>
        <p class="explain">Strongest signal because the game appears in both YouTube and Steam trends.</p>
        {simple_list(both)}
    </div>

    <div class="panel">
        <h2>Steam Popular, YouTube Missed</h2>
        <p class="explain">Games with strong Steam activity that may not be showing up in YouTube trends.</p>
        {simple_list(steam_only)}
    </div>
</div>

<div class="panel">
    <h2>YouTube Popular, Steam Missing</h2>
    <p class="explain">
        These games are showing content attention, but may not have Steam player data.
        This can happen with console games, mobile games, Roblox, Minecraft, or games not tracked well through Steam.
    </p>
    {simple_list(youtube_only)}
</div>

<div class="panel">
    <h2>RAWG-Style Game Cards</h2>
    <p class="explain">
        These cards make the dashboard easier to understand by showing what the game is, platforms, genres, ratings,
        YouTube attention, Steam player demand, and trend momentum.
    </p>

    <div class="card-grid">
        {cards}
    </div>
</div>

</body>
</html>
"""

    filename = {
        1: "dashboard_today.html",
        7: "dashboard_week.html",
        30: "dashboard_month.html"
    }.get(days, "index.html")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    if days == 7:
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)

    print(f"Created {filename}")


if __name__ == "__main__":
    build_dashboard(1)
    build_dashboard(7)
    build_dashboard(30)

    print("Gaming Trend Tracker dashboard updated with graphs, trend status, and RAWG-style cards.")