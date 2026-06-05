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


def get_youtube_top(conn, limit=10):
    query = """
        SELECT
            LOWER(game_name) AS game_name,
            SUM(mentions) AS score
        FROM trending_games
        WHERE run_timestamp >= NOW() - INTERVAL '7 days'
        GROUP BY LOWER(game_name)
        ORDER BY score DESC
        LIMIT %s;
    """
    return pd.read_sql(query, conn, params=(limit,))


def get_steam_top(conn, limit=10):
    query = """
        SELECT DISTINCT ON (LOWER(game_name))
            LOWER(game_name) AS game_name,
            current_players AS score
        FROM steam_trends
        ORDER BY LOWER(game_name), captured_at DESC;
    """
    df = pd.read_sql(query, conn)
    return df.sort_values("score", ascending=False).head(limit)


def get_twitch_top(conn, limit=10):
    query = """
        SELECT DISTINCT ON (LOWER(game_name))
            LOWER(game_name) AS game_name,
            viewer_count AS score
        FROM twitch_trends
        ORDER BY LOWER(game_name), captured_at DESC;
    """
    df = pd.read_sql(query, conn)
    return df.sort_values("score", ascending=False).head(limit)


def get_kick_top(conn, limit=10):
    query = """
        SELECT DISTINCT ON (LOWER(game_name))
            LOWER(game_name) AS game_name,
            viewer_count AS score
        FROM kick_trends
        ORDER BY LOWER(game_name), captured_at DESC;
    """
    df = pd.read_sql(query, conn)
    return df.sort_values("score", ascending=False).head(limit)


def make_chart(df, title):
    if df.empty:
        return "<p>No data yet.</p>"

    fig = px.bar(
        df,
        x="game_name",
        y="score",
        text="score",
        title=title
    )

    fig.update_layout(
        height=330,
        template="plotly_dark",
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=30, r=30, t=55, b=40)
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def build_platform_table(df, label):
    if df.empty:
        return f"<p>No {label} data yet.</p>"

    rows = ""

    for i, row in df.iterrows():
        rows += f"""
        <tr>
            <td>#{i + 1}</td>
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


def build_cross_platform(youtube_df, steam_df, twitch_df, kick_df):
    platform_map = {}

    sources = [
        ("YouTube", youtube_df),
        ("Steam", steam_df),
        ("Twitch", twitch_df),
        ("Kick", kick_df)
    ]

    for platform, df in sources:
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
            <th>Platforms</th>
            <th>Cross-Platform Score</th>
        </tr>
        {html_rows}
    </table>
    """


def build_dashboard():
    log_security_event("MAIN_DASHBOARD_BUILD", "Building main Project2026 dashboard")

    conn = get_connection()

    youtube_df = get_youtube_top(conn)
    steam_df = get_steam_top(conn)
    twitch_df = get_twitch_top(conn)
    kick_df = get_kick_top(conn)

    conn.close()

    youtube_chart = make_chart(youtube_df, "YouTube Top Games")
    steam_chart = make_chart(steam_df, "Steam Top Games")
    twitch_chart = make_chart(twitch_df, "Twitch Top Games")
    kick_chart = make_chart(kick_df, "Kick Top Categories / Games")

    cross_platform_html = build_cross_platform(
        youtube_df,
        steam_df,
        twitch_df,
        kick_df
    )

    top_youtube = youtube_df.iloc[0]["game_name"].title() if not youtube_df.empty else "N/A"
    top_steam = steam_df.iloc[0]["game_name"].title() if not steam_df.empty else "N/A"
    top_twitch = twitch_df.iloc[0]["game_name"].title() if not twitch_df.empty else "N/A"
    top_kick = kick_df.iloc[0]["game_name"].title() if not kick_df.empty else "N/A"

    html = f"""
<!DOCTYPE html>
<html>
<head>
<title>Project2026 Main Dashboard</title>
<style>
body {{
    background:
        radial-gradient(circle at top left, rgba(56,189,248,.18), transparent 30%),
        radial-gradient(circle at top right, rgba(83,252,24,.14), transparent 28%),
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

.nav a {{
    display: inline-block;
    background: #1e293b;
    color: white;
    padding: 10px 16px;
    margin-right: 8px;
    border-radius: 8px;
    text-decoration: none;
    border: 1px solid #334155;
}}

.summary {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
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
    font-size: 22px;
    color: #38bdf8;
}}

.summary-card span {{
    color: #94a3b8;
    font-size: 13px;
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

@media (max-width: 1000px) {{
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
Main comparison dashboard for YouTube, Steam, Twitch, and Kick gaming signals.
</p>

<div class="nav">
    <a href="index.html">Main</a>
    <a href="dashboard_youtube.html">YouTube</a>
    <a href="dashboard_steam.html">Steam</a>
    <a href="dashboard_twitch.html">Twitch</a>
    <a href="dashboard_kick.html">Kick</a>
</div>

<div class="summary">
    <div class="summary-card">
        <strong>{top_youtube}</strong>
        <span>Top YouTube Game</span>
    </div>

    <div class="summary-card">
        <strong>{top_steam}</strong>
        <span>Top Steam Game</span>
    </div>

    <div class="summary-card">
        <strong>{top_twitch}</strong>
        <span>Top Twitch Game</span>
    </div>

    <div class="summary-card">
        <strong>{top_kick}</strong>
        <span>Top Kick Category/Game</span>
    </div>
</div>

<div class="panel">
    <h2>What This Page Shows</h2>
    <p class="explainer">
        YouTube shows content attention. Steam shows active player demand.
        Twitch and Kick show live viewer demand. Games appearing across multiple platforms
        have stronger trend signals than games appearing on only one source.
    </p>
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

<div class="panel">
    <h2>Cross-Platform Matches</h2>
    <p class="explainer">
        These games appeared on two or more platforms. This is the beginning of the Project2026
        cross-platform trend score.
    </p>
    {cross_platform_html}
</div>

</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Created index.html")
    log_security_event("MAIN_DASHBOARD_SUCCESS", "Created index.html")


if __name__ == "__main__":
    build_dashboard()