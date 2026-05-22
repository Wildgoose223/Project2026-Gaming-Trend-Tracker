import os
import re

import psycopg2
import pandas as pd
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
        "metacritic": "83"
    },
    "roblox": {
        "platforms": "PC, Xbox, PlayStation, Mobile",
        "genres": "Platform, Sandbox, Creation",
        "released": "2006-09-01",
        "rating": "3.8",
        "metacritic": "N/A"
    },
    "destiny 2": {
        "platforms": "PC, PlayStation, Xbox",
        "genres": "Shooter, Action, MMO",
        "released": "2017-09-06",
        "rating": "3.2",
        "metacritic": "82"
    },
    "grand theft auto": {
        "platforms": "PC, Xbox, PlayStation",
        "genres": "Action, Open World, Crime",
        "released": "2013-09-17",
        "rating": "4.5",
        "metacritic": "97"
    },
    "subnautica": {
        "platforms": "PC, Xbox, PlayStation, Switch",
        "genres": "Survival, Adventure",
        "released": "2018-01-23",
        "rating": "4.3",
        "metacritic": "87"
    },
    "call of duty": {
        "platforms": "PC, Xbox, PlayStation",
        "genres": "Shooter, Action",
        "released": "2003-10-29",
        "rating": "4.0",
        "metacritic": "N/A"
    },
    "rainbow six siege": {
        "platforms": "PC, Xbox, PlayStation",
        "genres": "Shooter, Tactical",
        "released": "2015-12-01",
        "rating": "3.8",
        "metacritic": "73"
    },
    "marvel rivals": {
        "platforms": "PC, Xbox, PlayStation",
        "genres": "Hero Shooter, Action",
        "released": "2024-12-06",
        "rating": "N/A",
        "metacritic": "N/A"
    },
    "league of legends": {
        "platforms": "PC",
        "genres": "MOBA, Strategy",
        "released": "2009-10-27",
        "rating": "3.6",
        "metacritic": "78"
    },
    "among us": {
        "platforms": "PC, Xbox, PlayStation, Switch, Mobile",
        "genres": "Party, Social Deduction",
        "released": "2018-06-15",
        "rating": "3.7",
        "metacritic": "85"
    },
    "rust": {
        "platforms": "PC, Xbox, PlayStation",
        "genres": "Survival, Multiplayer",
        "released": "2018-02-08",
        "rating": "3.7",
        "metacritic": "69"
    },
    "counter strike 2": {
        "platforms": "PC",
        "genres": "Shooter, Competitive",
        "released": "2023-09-27",
        "rating": "N/A",
        "metacritic": "N/A"
    },
    "dota 2": {
        "platforms": "PC",
        "genres": "MOBA, Strategy",
        "released": "2013-07-09",
        "rating": "3.0",
        "metacritic": "90"
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


def fmt_number(value):
    if value is None:
        return "N/A"

    try:
        if pd.isna(value):
            return "N/A"

        return f"{int(value):,}"

    except Exception:
        return "N/A"


def get_top_games(conn, days=7, limit=10):
    query = """
        WITH top_games AS (
            SELECT
                LOWER(game_name) AS game_name,
                SUM(mentions) AS mentions
            FROM trending_games
            WHERE run_timestamp >= NOW() - INTERVAL %s
            GROUP BY LOWER(game_name)
            ORDER BY mentions DESC
            LIMIT %s
        ),
        totals AS (
            SELECT SUM(mentions) AS total_mentions
            FROM top_games
        )
        SELECT
            t.game_name,
            t.mentions,
            ROUND(
                (t.mentions::numeric / NULLIF((SELECT total_mentions FROM totals), 0)) * 100,
                2
            ) AS share_of_top_10,
            COUNT(g.*) AS times_detected
        FROM top_games t
        JOIN trending_games g
            ON LOWER(g.game_name) = t.game_name
        WHERE g.run_timestamp >= NOW() - INTERVAL %s
        GROUP BY t.game_name, t.mentions
        ORDER BY t.mentions DESC;
    """

    return pd.read_sql(query, conn, params=(f"{days} days", limit, f"{days} days"))


def get_summary(conn, days):
    query = """
        SELECT
            COUNT(DISTINCT LOWER(game_name)) AS games_tracked,
            COALESCE(SUM(mentions), 0) AS total_mentions,
            COUNT(DISTINCT run_timestamp) AS saved_pulls
        FROM trending_games
        WHERE run_timestamp >= NOW() - INTERVAL %s;
    """

    return pd.read_sql(query, conn, params=(f"{days} days",))


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

    return pd.read_sql(query, conn)


def get_latest_steam_players(conn):
    query = """
        SELECT DISTINCT ON (LOWER(game_name))
            LOWER(game_name) AS game_name,
            current_players
        FROM steam_trends
        ORDER BY LOWER(game_name), captured_at DESC;
    """

    try:
        return pd.read_sql(query, conn)

    except Exception:
        return pd.DataFrame(columns=["game_name", "current_players"])


def trend_label(change):
    if change > 0:
        return "Trending Up", "up"

    if change < 0:
        return "Declining", "down"

    return "Stable", "stable"


def build_trend_summary(top_games, changes, steam_map, days):
    if top_games.empty:
        return "Not enough data has been collected yet."

    leader = top_games.iloc[0]["game_name"].title()
    mentions = int(top_games.iloc[0]["mentions"])

    period = "today" if days == 1 else f"the last {days} days"

    summary = f"In {period}, {leader} is leading YouTube activity with {mentions} matched mentions. "

    if not changes.empty:
        up = changes.sort_values("change", ascending=False).iloc[0]
        down = changes.sort_values("change", ascending=True).iloc[0]

        if int(up["change"]) > 0:
            summary += f"{up['game_name'].title()} gained the most since the previous pull. "

        if int(down["change"]) < 0:
            summary += f"{down['game_name'].title()} cooled off the most since the previous pull. "

    steam_candidates = []

    for _, row in top_games.iterrows():
        game = row["game_name"]
        players = steam_map.get(game)

        if players is not None and not pd.isna(players):
            steam_candidates.append((game, int(players)))

    if steam_candidates:
        steam_leader = sorted(steam_candidates, key=lambda x: x[1], reverse=True)[0]
        summary += (
            f"On Steam, {steam_leader[0].title()} currently has the strongest active-player signal "
            f"among these tracked games with {steam_leader[1]:,} players."
        )

    return summary


def clean_table(df):
    return df.rename(columns={
        "game_name": "Game",
        "mentions": "YouTube Mentions",
        "share_of_top_10": "Share of Top 10",
        "times_detected": "Times Detected"
    }).to_html(index=False)


def build_dashboard(days=7):
    conn = get_connection()

    top_games = get_top_games(conn, days, 10)
    summary = get_summary(conn, days)
    changes = get_latest_change(conn)
    steam_players_df = get_latest_steam_players(conn)

    weekly_games = get_top_games(conn, 7, 10)
    monthly_games = get_top_games(conn, 30, 10)

    conn.close()

    change_map = {
        row["game_name"]: int(row["change"])
        for _, row in changes.iterrows()
    }

    steam_map = {
        row["game_name"]: row["current_players"]
        for _, row in steam_players_df.iterrows()
    }

    trend_summary = build_trend_summary(
        top_games,
        changes,
        steam_map,
        days
    )

    cards = ""

    for index, row in top_games.iterrows():
        game = row["game_name"]
        game_title = game.title()
        mentions = int(row["mentions"])
        share = row["share_of_top_10"]
        times_detected = int(row["times_detected"])
        change = change_map.get(game, 0)
        steam_players = steam_map.get(game)

        status, status_class = trend_label(change)
        img = image_for_game(game)

        meta = GAME_META.get(game, {
            "platforms": "Metadata not loaded yet",
            "genres": "Metadata not loaded yet",
            "released": "N/A",
            "rating": "N/A",
            "metacritic": "N/A"
        })

        if img:
            image_html = f'<img src="{img}" class="game-img">'
        else:
            image_html = f'<div class="game-img placeholder">{game_title}</div>'

        steam_display = fmt_number(steam_players)

        cards += f"""
        <div class="game-card">
            {image_html}

            <div class="card-body">
                <div class="rank">#{index + 1}</div>
                <h3>{game_title}</h3>
                <p class="desc">Matched from YouTube Gaming titles, tags, RAWG titles, Steam titles, and aliases.</p>

                <div class="stats">
                    <div><strong>{mentions}</strong><span>YouTube Mentions</span></div>
                    <div><strong>{share}%</strong><span>Share of Top 10</span></div>
                    <div><strong>{change:+}</strong><span>Vs Last Pull</span></div>
                    <div><strong>{steam_display}</strong><span>Steam Players</span></div>
                </div>

                <div class="status {status_class}">{status}</div>

                <p class="callout">
                    {game_title} made up {share}% of the top 10 tracked YouTube mentions in this view.
                    Steam players are shown separately because they represent active player demand, not YouTube activity.
                </p>

                <div class="meta">
                    <p><strong>Platforms:</strong> {meta["platforms"]}</p>
                    <p><strong>Genres:</strong> {meta["genres"]}</p>
                    <p><strong>Released:</strong> {meta["released"]}</p>
                    <p><strong>RAWG Rating:</strong> {meta["rating"]}</p>
                    <p><strong>Metacritic:</strong> {meta["metacritic"]}</p>
                    <p><strong>Times Detected:</strong> {times_detected}</p>
                </div>
            </div>
        </div>
        """

    s = summary.iloc[0]

    bar_fig = px.bar(
        top_games,
        x="game_name",
        y="mentions",
        text="mentions",
        title=f"Top 10 YouTube Mentions - Last {days} Days"
    )

    bar_fig.update_layout(
        height=320,
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=30, r=30, t=55, b=40)
    )

    bar_html = bar_fig.to_html(full_html=False, include_plotlyjs="cdn")

    filename = {
        1: "dashboard_today.html",
        7: "dashboard_week.html",
        30: "dashboard_month.html"
    }.get(days, "dashboard_custom.html")

    current_view = "Today" if days == 1 else f"Last {days} Days"

    html = f"""
<!DOCTYPE html>
<html>
<head>
<title>Project2026 Gaming Trend Dashboard</title>
<style>
body {{
    background:
        radial-gradient(circle at top left, rgba(56,189,248,.18), transparent 30%),
        radial-gradient(circle at top right, rgba(99,102,241,.14), transparent 28%),
        linear-gradient(135deg, #020617, #0f172a 50%, #111827);
    color: #e5e7eb;
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 24px;
}}

h1 {{
    color: #38bdf8;
    margin-bottom: 4px;
}}

.subtitle {{
    color: #94a3b8;
    margin-bottom: 18px;
}}

.buttons a,
.custom-btn {{
    display: inline-block;
    background: #1e293b;
    color: white;
    padding: 10px 16px;
    margin-right: 8px;
    border-radius: 8px;
    text-decoration: none;
    border: 1px solid #334155;
    cursor: pointer;
}}

.view-label {{
    margin-top: 14px;
    color: #dbeafe;
    font-weight: bold;
}}

.summary {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-top: 20px;
}}

.summary-card,
.panel,
.game-card {{
    background: rgba(15,23,42,.94);
    border: 1px solid #334155;
    border-radius: 16px;
    box-shadow: 0 12px 30px rgba(0,0,0,.28);
}}

.summary-card {{
    padding: 18px;
    text-align: center;
}}

.summary-card strong {{
    display: block;
    font-size: 30px;
    color: #38bdf8;
}}

.summary-card span {{
    color: #94a3b8;
    font-size: 13px;
}}

.panel {{
    padding: 18px;
    margin-top: 22px;
}}

.trend-summary {{
    font-size: 17px;
    line-height: 1.6;
    color: #dbeafe;
    background: rgba(2,6,23,.45);
    border-left: 4px solid #38bdf8;
    padding: 14px;
    border-radius: 10px;
}}

.grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-top: 20px;
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

.rank {{
    color: #38bdf8;
    font-weight: bold;
}}

h3 {{
    margin: 6px 0;
    font-size: 22px;
}}

.desc {{
    color: #94a3b8;
    font-size: 13px;
    line-height: 1.45;
}}

.stats {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin: 14px 0;
}}

.stats div {{
    background: #020617;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 10px;
    text-align: center;
}}

.stats strong {{
    display: block;
    color: white;
    font-size: 15px;
}}

.stats span {{
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
}}

.up {{
    background: rgba(34,197,94,.15);
    color: #4ade80;
}}

.down {{
    background: rgba(239,68,68,.15);
    color: #f87171;
}}

.stable {{
    background: rgba(234,179,8,.15);
    color: #facc15;
}}

.callout {{
    background: #020617;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 10px;
    color: #dbeafe;
    font-size: 13px;
}}

.meta p {{
    color: #cbd5e1;
    font-size: 12px;
    margin: 6px 0;
}}

.meta strong {{
    color: #38bdf8;
}}

.explainer {{
    color: #94a3b8;
    font-size: 13px;
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
</style>
</head>

<body>

<h1>Project2026 Gaming Trend Dashboard</h1>

<p class="subtitle">
A gaming trend dashboard using YouTube Gaming titles, tags, RAWG titles, Steam titles, aliases, player counts, and PostgreSQL history.
</p>

<div class="buttons">
    <a href="dashboard_today.html">Today</a>
    <a href="dashboard_week.html">7 Days</a>
    <a href="dashboard_month.html">30 Days</a>
    <button class="custom-btn" onclick="alert('Custom range coming soon.')">Custom Range</button>
</div>

<div class="view-label">Current View: {current_view}</div>

<div class="summary">
    <div class="summary-card">
        <strong>{int(s['games_tracked'])}</strong>
        <span>Games Tracked</span>
    </div>

    <div class="summary-card">
        <strong>{int(s['total_mentions'])}</strong>
        <span>YouTube Mentions</span>
    </div>

    <div class="summary-card">
        <strong>{int(s['saved_pulls'])}</strong>
        <span>Saved Pulls</span>
    </div>

    <div class="summary-card">
        <strong>{top_games.iloc[0]["game_name"].title() if not top_games.empty else "N/A"}</strong>
        <span>Top YouTube Game</span>
    </div>
</div>

<div class="panel">
    <h2>Trend Summary</h2>
    <div class="trend-summary">{trend_summary}</div>
</div>

<div class="panel">
    <h2>Top 10 YouTube Mentions</h2>
    {bar_html}
    <p class="explainer">
        YouTube Mentions show content attention. Steam Players show active player demand.
        These are separate signals and should not be added together.
    </p>
</div>

<div class="grid">
    {cards}
</div>

<div class="panel">
    <h2>Weekly Top 10</h2>
    <p class="explainer">
        YouTube Mentions = how often the game appeared in matched YouTube Gaming data.
        Share of Top 10 = that game’s share compared only to the top 10 shown.
    </p>
    {clean_table(weekly_games)}
</div>

<div class="panel">
    <h2>Monthly Top 10</h2>
    <p class="explainer">
        YouTube Mentions = how often the game appeared in matched YouTube Gaming data.
        Share of Top 10 = that game’s share compared only to the top 10 shown.
    </p>
    {clean_table(monthly_games)}
</div>

</body>
</html>
"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Created {filename}")


if __name__ == "__main__":
    build_dashboard(1)
    build_dashboard(7)
    build_dashboard(30)

    print("Dashboard rebuilt with Steam player counts.")