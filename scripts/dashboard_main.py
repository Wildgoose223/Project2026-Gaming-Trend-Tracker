import os
import pandas as pd
import psycopg2
import plotly.express as px
from dotenv import load_dotenv

from security_logger import log_security_event

load_dotenv()

DB_NAME = os.getenv("DB_NAME", "Gaming_Trend_Tracker")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")


def get_connection():
    log_security_event("DB_CONNECT", "Opening PostgreSQL connection for main dashboard")
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )


def fmt_num(value):
    try:
        if value is None or pd.isna(value):
            return "N/A"
        return f"{int(value):,}"
    except Exception:
        return "N/A"


def safe_read_sql(query, conn, params=None):
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception as e:
        print(f"Query skipped: {e}")
        return pd.DataFrame()


def get_youtube_top(conn, days=7, limit=10):
    query = """
        SELECT LOWER(game_name) AS game_name, SUM(mentions) AS score
        FROM trending_games
        WHERE run_timestamp >= NOW() - (%s * INTERVAL '1 day')
        GROUP BY LOWER(game_name)
        ORDER BY score DESC
        LIMIT %s;
    """
    return safe_read_sql(query, conn, params=(days, limit))


def get_steam_top(conn, days=7, limit=10):
    query = """
        WITH ranked AS (
            SELECT LOWER(game_name) AS game_name, current_players AS score, captured_at,
            ROW_NUMBER() OVER (PARTITION BY LOWER(game_name) ORDER BY captured_at DESC) AS rn
            FROM steam_trends
            WHERE captured_at >= NOW() - (%s * INTERVAL '1 day')
        )
        SELECT game_name, score
        FROM ranked
        WHERE rn = 1
        ORDER BY score DESC
        LIMIT %s;
    """
    return safe_read_sql(query, conn, params=(days, limit))


def get_twitch_top(conn, days=7, limit=10):
    query = """
        WITH ranked AS (
            SELECT LOWER(game_name) AS game_name, viewer_count AS score, captured_at,
            ROW_NUMBER() OVER (PARTITION BY LOWER(game_name) ORDER BY captured_at DESC) AS rn
            FROM twitch_trends
            WHERE captured_at >= NOW() - (%s * INTERVAL '1 day')
        )
        SELECT game_name, score
        FROM ranked
        WHERE rn = 1
        ORDER BY score DESC
        LIMIT %s;
    """
    return safe_read_sql(query, conn, params=(days, limit))


def get_kick_top(conn, days=7, limit=10):
    query = """
        WITH ranked AS (
            SELECT LOWER(game_name) AS game_name, viewer_count AS score, captured_at,
            ROW_NUMBER() OVER (PARTITION BY LOWER(game_name) ORDER BY captured_at DESC) AS rn
            FROM kick_trends
            WHERE captured_at >= NOW() - (%s * INTERVAL '1 day')
        )
        SELECT game_name, score
        FROM ranked
        WHERE rn = 1
        ORDER BY score DESC
        LIMIT %s;
    """
    return safe_read_sql(query, conn, params=(days, limit))


def make_chart(df, title, label):
    if df.empty:
        return "<p>No data yet.</p>"

    fig = px.bar(df, x="game_name", y="score", text="score", title=title)
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(
        height=310,
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=25, r=25, t=50, b=75),
        xaxis_title="Game",
        yaxis_title=label
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def top_name(df):
    return "N/A" if df.empty else df.iloc[0]["game_name"].title()


def top_score(df):
    return "N/A" if df.empty else fmt_num(df.iloc[0]["score"])


def build_platform_table(df, label):
    if df.empty:
        return f"<p>No {label} data yet.</p>"

    rows = ""
    for rank, (_, row) in enumerate(df.iterrows(), start=1):
        rows += f"""
        <tr>
            <td>#{rank}</td>
            <td>{row["game_name"].title()}</td>
            <td>{fmt_num(row["score"])}</td>
        </tr>
        """

    return f"""
    <table>
        <tr>
            <th>Rank</th>
            <th>Game</th>
            <th>{label}</th>
        </tr>
        {rows}
    </table>
    """


def combine_popular_games(youtube_df, steam_df, twitch_df, kick_df):
    games = {}

    sources = [
        ("YouTube", youtube_df, "youtube"),
        ("Steam", steam_df, "steam"),
        ("Twitch", twitch_df, "twitch"),
        ("Kick", kick_df, "kick")
    ]

    for platform, df, key in sources:
        if df.empty:
            continue

        for _, row in df.iterrows():
            game = row["game_name"].lower().strip()

            if game not in games:
                games[game] = {
                    "Game": game.title(),
                    "Found On": [],
                    "Steam Players": 0,
                    "Twitch Viewers": 0,
                    "YouTube Mentions": 0,
                    "Kick Viewers": 0
                }

            if platform not in games[game]["Found On"]:
                games[game]["Found On"].append(platform)

            if key == "steam":
                games[game]["Steam Players"] = row["score"]
            elif key == "twitch":
                games[game]["Twitch Viewers"] = row["score"]
            elif key == "youtube":
                games[game]["YouTube Mentions"] = row["score"]
            elif key == "kick":
                games[game]["Kick Viewers"] = row["score"]

    rows = []

    for _, data in games.items():
        rows.append({
            "Game": data["Game"],
            "Found On": ", ".join(data["Found On"]),
            "Platform Count": len(data["Found On"]),
            "Steam Players": data["Steam Players"],
            "Twitch Viewers": data["Twitch Viewers"],
            "YouTube Mentions": data["YouTube Mentions"],
            "Kick Viewers": data["Kick Viewers"]
        })

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    return df.sort_values(
        ["Platform Count", "Steam Players", "Twitch Viewers", "YouTube Mentions"],
        ascending=[False, False, False, False]
    )


def build_most_popular_table(popular_df):
    if popular_df.empty:
        return "<p>No popular game data yet.</p>"

    display = popular_df.head(15).copy()

    for col in ["Steam Players", "Twitch Viewers", "YouTube Mentions", "Kick Viewers"]:
        display[col] = display[col].apply(fmt_num)

    return display.to_html(index=False)


def build_common_games_table(popular_df):
    if popular_df.empty:
        return "<p>No cross-platform matches yet.</p>"

    common = popular_df[popular_df["Platform Count"] >= 2].copy()

    if common.empty:
        return "<p>No games are currently appearing on multiple platforms.</p>"

    common = common[["Game", "Found On", "Platform Count"]].head(15)

    return common.to_html(index=False)


def find_rawg_match(conn, game_name):
    game = game_name.lower().strip()

    query = """
        SELECT game_name, rating, metacritic, released
        FROM games
        WHERE LOWER(game_name) = %s
           OR LOWER(game_name) LIKE %s
           OR %s LIKE '%%' || LOWER(game_name) || '%%'
        ORDER BY
            CASE
                WHEN LOWER(game_name) = %s THEN 1
                WHEN LOWER(game_name) LIKE %s THEN 2
                ELSE 3
            END,
            rating DESC NULLS LAST
        LIMIT 1;
    """

    df = safe_read_sql(
        query,
        conn,
        params=(game, f"%{game}%", game, game, f"%{game}%")
    )

    if df.empty:
        return None

    return df.iloc[0]


def build_rawg_match_table(conn, popular_df):
    if popular_df.empty:
        return "<p>No RAWG matches yet.</p>"

    rows = []

    for _, row in popular_df.head(15).iterrows():
        match = find_rawg_match(conn, row["Game"])

        if match is None:
            rows.append({
                "Game": row["Game"],
                "RAWG Match": "No match",
                "Rating": "N/A",
                "Metacritic": "N/A",
                "Released": "N/A"
            })
        else:
            rows.append({
                "Game": row["Game"],
                "RAWG Match": str(match["game_name"]).title(),
                "Rating": "N/A" if pd.isna(match["rating"]) else match["rating"],
                "Metacritic": "N/A" if pd.isna(match["metacritic"]) else match["metacritic"],
                "Released": "N/A" if pd.isna(match["released"]) else match["released"]
            })

    df = pd.DataFrame(rows)
    return df.to_html(index=False)


def build_dashboard(days=7):
    log_security_event("MAIN_DASHBOARD_BUILD", "Building clean Project2026 dashboard")

    conn = None

    try:
        conn = get_connection()

        youtube_df = get_youtube_top(conn, days=days)
        steam_df = get_steam_top(conn, days=days)
        twitch_df = get_twitch_top(conn, days=days)
        kick_df = get_kick_top(conn, days=days)

        popular_df = combine_popular_games(youtube_df, steam_df, twitch_df, kick_df)

        popular_html = build_most_popular_table(popular_df)
        common_html = build_common_games_table(popular_df)
        rawg_html = build_rawg_match_table(conn, popular_df)

    finally:
        if conn:
            conn.close()

    youtube_chart = make_chart(youtube_df, "YouTube Top Games", "Mentions")
    steam_chart = make_chart(steam_df, "Steam Top Games", "Players")
    twitch_chart = make_chart(twitch_df, "Twitch Top Games", "Viewers")
    kick_chart = make_chart(kick_df, "Kick Top Games", "Viewers")

    html = f"""
<!DOCTYPE html>
<html>
<head>
<title>Project2026 Main Dashboard</title>

<style>
body {{
    background:
        radial-gradient(circle at top left, rgba(56,189,248,.16), transparent 30%),
        radial-gradient(circle at top right, rgba(34,197,94,.12), transparent 28%),
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

h2 {{
    margin-top: 0;
}}

.subtitle,
.explainer {{
    color: #94a3b8;
    line-height: 1.5;
}}

.nav {{
    margin: 18px 0;
}}

.nav a {{
    display: inline-block;
    background: #1e293b;
    color: white;
    padding: 10px 16px;
    margin-right: 8px;
    margin-bottom: 8px;
    border-radius: 8px;
    text-decoration: none;
    border: 1px solid #334155;
}}

.nav a:hover {{
    background: #2563eb;
}}

.summary {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-top: 18px;
}}

.summary-card,
.panel {{
    background: rgba(15,23,42,.94);
    border: 1px solid #334155;
    border-radius: 16px;
    box-shadow: 0 12px 30px rgba(0,0,0,.28);
}}

.summary-card {{
    padding: 16px;
    text-align: center;
}}

.summary-card strong {{
    display: block;
    font-size: 18px;
    color: #38bdf8;
}}

.summary-card span {{
    display: block;
    color: #94a3b8;
    font-size: 12px;
    margin-top: 6px;
}}

.summary-card small {{
    display: block;
    color: #e5e7eb;
    margin-top: 8px;
}}

.panel {{
    padding: 18px;
    margin-top: 20px;
    overflow-x: auto;
}}

.grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 18px;
    margin-top: 20px;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
    font-size: 13px;
}}

th,
td {{
    border-bottom: 1px solid #334155;
    padding: 8px 10px;
    text-align: left;
}}

th {{
    color: #38bdf8;
}}

.badge {{
    display: inline-block;
    background: rgba(56,189,248,.12);
    color: #7dd3fc;
    border: 1px solid #2563eb;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 12px;
}}

@media (max-width: 1100px) {{
    .grid,
    .summary {{
        grid-template-columns: 1fr;
    }}
}}
</style>
</head>

<body>

<h1>Project2026 Gaming Trend Intelligence</h1>
<p class="subtitle">Main dashboard for what is popular, what overlaps, and what RAWG says about those games.</p>

<div class="nav">
    <a href="index.html">Main</a>
    <a href="dashboard_youtube.html">YouTube</a>
    <a href="dashboard_steam.html">Steam</a>
    <a href="dashboard_twitch.html">Twitch</a>
    <a href="dashboard_kick.html">Kick</a>
</div>

<div class="panel">
    <span class="badge">Last {days} days</span>
    <p class="explainer">
        This page starts with the games appearing on Steam, YouTube, Twitch, and Kick.
        RAWG is used only at the bottom to add rating, Metacritic, and release information
        for those same games.
    </p>
</div>

<div class="summary">
    <div class="summary-card">
        <strong>{top_name(youtube_df)}</strong>
        <span>Top YouTube Game</span>
        <small>{top_score(youtube_df)} mentions</small>
    </div>

    <div class="summary-card">
        <strong>{top_name(steam_df)}</strong>
        <span>Top Steam Game</span>
        <small>{top_score(steam_df)} players</small>
    </div>

    <div class="summary-card">
        <strong>{top_name(twitch_df)}</strong>
        <span>Top Twitch Game</span>
        <small>{top_score(twitch_df)} viewers</small>
    </div>

    <div class="summary-card">
        <strong>{top_name(kick_df)}</strong>
        <span>Top Kick Game</span>
        <small>{top_score(kick_df)} viewers</small>
    </div>
</div>

<div class="panel">
    <h2>Most Popular Games Across Platforms</h2>
    <p class="explainer">
        Ranked by how many platforms each game appears on, then by Steam, Twitch, and YouTube activity.
    </p>
    {popular_html}
</div>

<div class="panel">
    <h2>Games In Common Across Platforms</h2>
    <p class="explainer">
        These are the games appearing on more than one platform.
    </p>
    {common_html}
</div>

<div class="grid">
    <div class="panel">
        <h2>YouTube</h2>
        {youtube_chart}
        {build_platform_table(youtube_df, "Mentions")}
    </div>

    <div class="panel">
        <h2>Steam</h2>
        {steam_chart}
        {build_platform_table(steam_df, "Players")}
    </div>

    <div class="panel">
        <h2>Twitch</h2>
        {twitch_chart}
        {build_platform_table(twitch_df, "Viewers")}
    </div>

    <div class="panel">
        <h2>Kick</h2>
        {kick_chart}
        {build_platform_table(kick_df, "Viewers")}
    </div>
</div>

<div class="panel">
    <h2>RAWG Match Details For Popular Games</h2>
    <p class="explainer">
        RAWG is matched only against the games listed above. It is not showing a separate top-rated-games leaderboard.
    </p>
    {rawg_html}
</div>

</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Created index.html")
    print("Dashboard version: clean popular/common/RAWG-match layout")


if __name__ == "__main__":
    build_dashboard(days=7)