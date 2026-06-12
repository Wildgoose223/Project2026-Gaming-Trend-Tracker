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
        SELECT
            LOWER(game_name) AS game_name,
            SUM(mentions) AS score
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
            SELECT
                LOWER(game_name) AS game_name,
                current_players AS score,
                captured_at,
                ROW_NUMBER() OVER (
                    PARTITION BY LOWER(game_name)
                    ORDER BY captured_at DESC
                ) AS rn
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
            SELECT
                LOWER(game_name) AS game_name,
                viewer_count AS score,
                captured_at,
                ROW_NUMBER() OVER (
                    PARTITION BY LOWER(game_name)
                    ORDER BY captured_at DESC
                ) AS rn
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
            SELECT
                LOWER(game_name) AS game_name,
                viewer_count AS score,
                captured_at,
                ROW_NUMBER() OVER (
                    PARTITION BY LOWER(game_name)
                    ORDER BY captured_at DESC
                ) AS rn
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


def get_rawg_top_rated(conn, limit=10):
    query = """
        SELECT
            LOWER(game_name) AS game_name,
            rating AS score,
            metacritic,
            released
        FROM games
        WHERE rating IS NOT NULL
        ORDER BY rating DESC
        LIMIT %s;
    """
    return safe_read_sql(query, conn, params=(limit,))


def get_rawg_metacritic(conn, limit=10):
    query = """
        SELECT
            LOWER(game_name) AS game_name,
            metacritic AS score,
            rating,
            released
        FROM games
        WHERE metacritic IS NOT NULL
        ORDER BY metacritic DESC
        LIMIT %s;
    """
    return safe_read_sql(query, conn, params=(limit,))


def make_chart(df, title, label):
    if df.empty:
        return "<p>No data yet.</p>"

    fig = px.bar(
        df,
        x="game_name",
        y="score",
        text="score",
        title=title
    )

    fig.update_traces(texttemplate="%{text:,}", textposition="outside")

    fig.update_layout(
        height=330,
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=30, r=30, t=55, b=80),
        xaxis_title="Game",
        yaxis_title=label
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


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


def build_rawg_table(df, label):
    if df.empty:
        return f"<p>No RAWG {label} data yet.</p>"

    rows = ""

    for rank, (_, row) in enumerate(df.iterrows(), start=1):
        released = row.get("released", "N/A")
        extra = row.get("metacritic", row.get("rating", "N/A"))

        rows += f"""
        <tr>
            <td>#{rank}</td>
            <td>{row["game_name"].title()}</td>
            <td>{row["score"]}</td>
            <td>{extra}</td>
            <td>{released}</td>
        </tr>
        """

    return f"""
    <table>
        <tr>
            <th>Rank</th>
            <th>Game</th>
            <th>{label}</th>
            <th>Other Score</th>
            <th>Released</th>
        </tr>
        {rows}
    </table>
    """


def build_cross_platform(youtube_df, steam_df, twitch_df, kick_df, rawg_df):
    platform_map = {}

    sources = [
        ("YouTube", youtube_df),
        ("Steam", steam_df),
        ("Twitch", twitch_df),
        ("Kick", kick_df),
        ("RAWG", rawg_df)
    ]

    for platform, df in sources:
        if df.empty or "game_name" not in df.columns:
            continue

        for game in df["game_name"].tolist():
            if game not in platform_map:
                platform_map[game] = []
            platform_map[game].append(platform)

    rows = []

    for game, platforms in platform_map.items():
        if len(platforms) >= 2:
            rows.append({
                "game_name": game,
                "platforms": ", ".join(platforms),
                "platform_count": len(platforms)
            })

    cross_df = pd.DataFrame(rows)

    if cross_df.empty:
        return "<p>No cross-platform matches yet.</p>"

    cross_df = cross_df.sort_values(
        ["platform_count", "game_name"],
        ascending=[False, True]
    )

    html_rows = ""

    for _, row in cross_df.iterrows():
        html_rows += f"""
        <tr>
            <td>{row["game_name"].title()}</td>
            <td>{row["platforms"]}</td>
            <td>{row["platform_count"]}</td>
        </tr>
        """

    return f"""
    <table>
        <tr>
            <th>Game</th>
            <th>Platforms Found</th>
            <th>Project2026 Score</th>
        </tr>
        {html_rows}
    </table>
    """


def top_name(df):
    if df.empty:
        return "N/A"
    return df.iloc[0]["game_name"].title()


def top_score(df):
    if df.empty:
        return "N/A"
    return fmt_num(df.iloc[0]["score"])


def build_dashboard(days=7):
    log_security_event("MAIN_DASHBOARD_BUILD", "Building main Project2026 dashboard")

    conn = None

    try:
        conn = get_connection()

        youtube_df = get_youtube_top(conn, days=days)
        steam_df = get_steam_top(conn, days=days)
        twitch_df = get_twitch_top(conn, days=days)
        kick_df = get_kick_top(conn, days=days)
        rawg_rating_df = get_rawg_top_rated(conn)
        rawg_meta_df = get_rawg_metacritic(conn)
        print(rawg_rating_df.head())
        print(rawg_meta_df.head())


    finally:
        if conn:
            conn.close()

    youtube_chart = make_chart(youtube_df, "YouTube Top Games", "Mentions")
    steam_chart = make_chart(steam_df, "Steam Top Games", "Current Players")
    twitch_chart = make_chart(twitch_df, "Twitch Top Games", "Current Viewers")
    kick_chart = make_chart(kick_df, "Kick Top Games", "Current Viewers")
    rawg_rating_chart = make_chart(rawg_rating_df, "RAWG Top Rated Games", "Rating")
    rawg_meta_chart = make_chart(rawg_meta_df, "RAWG Top Metacritic Games", "Metacritic")

    cross_platform_html = build_cross_platform(
        youtube_df,
        steam_df,
        twitch_df,
        kick_df,
        rawg_rating_df
    )

    html = f"""
<!DOCTYPE html>
<html>
<head>
<title>Project2026 Main Dashboard</title>

<style>
body {{
    background:
        radial-gradient(circle at top left, rgba(56,189,248,.18), transparent 30%),
        radial-gradient(circle at top right, rgba(34,197,94,.14), transparent 28%),
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

.nav {{
    margin-bottom: 18px;
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
    grid-template-columns: repeat(5, 1fr);
    gap: 14px;
    margin-top: 20px;
}}

.summary-card,
.panel {{
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
    font-size: 20px;
    color: #38bdf8;
}}

.summary-card span {{
    display: block;
    color: #94a3b8;
    font-size: 13px;
    margin-top: 6px;
}}

.summary-card small {{
    display: block;
    color: #e5e7eb;
    margin-top: 8px;
}}

.grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 18px;
    margin-top: 22px;
}}

.panel {{
    padding: 18px;
    margin-top: 22px;
    overflow-x: auto;
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

.explainer {{
    color: #94a3b8;
    font-size: 14px;
    line-height: 1.5;
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

<p class="subtitle">
Main comparison dashboard for YouTube, Steam, Twitch, Kick, and RAWG game intelligence.
</p>

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
        Steam shows active player demand. YouTube shows content attention.
        Twitch and Kick show live viewer demand. RAWG adds game rating, release,
        and review intelligence. Games appearing across multiple sources have a stronger
        Project2026 trend signal.
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

    <div class="summary-card">
        <strong>{top_name(rawg_rating_df)}</strong>
        <span>Top RAWG Rated</span>
        <small>{top_score(rawg_rating_df)} rating</small>
    </div>
</div>

<div class="panel">
    <h2>Project2026 Cross-Platform Matches</h2>
    <p class="explainer">
        This section shows games appearing in more than one source. Higher score means the game
        is showing up across more parts of the gaming ecosystem.
    </p>
    {cross_platform_html}
</div>

<div class="grid">
    <div class="panel">
        <h2>YouTube</h2>
        {youtube_chart}
        {build_platform_table(youtube_df, "YouTube Mentions")}
    </div>

    <div class="panel">
        <h2>Steam</h2>
        {steam_chart}
        {build_platform_table(steam_df, "Current Players")}
    </div>

    <div class="panel">
        <h2>Twitch</h2>
        {twitch_chart}
        {build_platform_table(twitch_df, "Current Viewers")}
    </div>

    <div class="panel">
        <h2>Kick</h2>
        {kick_chart}
        {build_platform_table(kick_df, "Current Viewers")}
    </div>
</div>

<div class="grid">
    <div class="panel">
        <h2>RAWG Rating Intelligence</h2>
        {rawg_rating_chart}
        {build_rawg_table(rawg_rating_df, "Rating")}
    </div>

    <div class="panel">
        <h2>RAWG Metacritic Intelligence</h2>
        {rawg_meta_chart}
        {build_rawg_table(rawg_meta_df, "Metacritic")}
    </div>
</div>

</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Created index.html")
    log_security_event("MAIN_DASHBOARD_SUCCESS", "Created index.html")


if __name__ == "__main__":
    build_dashboard(days=7)