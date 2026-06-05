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
    log_security_event("DB_CONNECT", "Opening PostgreSQL connection for Twitch dashboard")

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


def get_twitch_momentum(conn, days=7, limit=15):
    query = """
        WITH latest_run AS (
            SELECT MAX(captured_at) AS latest_time
            FROM twitch_trends
            WHERE captured_at >= NOW() - INTERVAL %s
        ),
        previous_run AS (
            SELECT MAX(captured_at) AS previous_time
            FROM twitch_trends
            WHERE captured_at < (SELECT latest_time FROM latest_run)
              AND captured_at >= NOW() - INTERVAL %s
        ),
        latest AS (
            SELECT
                LOWER(game_name) AS game_name,
                SUM(viewer_count) AS current_viewers,
                SUM(stream_count) AS current_streams
            FROM twitch_trends
            WHERE captured_at = (SELECT latest_time FROM latest_run)
            GROUP BY LOWER(game_name)
        ),
        previous AS (
            SELECT
                LOWER(game_name) AS game_name,
                SUM(viewer_count) AS previous_viewers,
                SUM(stream_count) AS previous_streams
            FROM twitch_trends
            WHERE captured_at = (SELECT previous_time FROM previous_run)
            GROUP BY LOWER(game_name)
        )
        SELECT
            l.game_name,
            l.current_viewers,
            COALESCE(p.previous_viewers, 0) AS previous_viewers,
            l.current_streams,
            COALESCE(p.previous_streams, 0) AS previous_streams,
            l.current_viewers - COALESCE(p.previous_viewers, 0) AS viewer_change,
            ROUND(
                ((l.current_viewers - COALESCE(p.previous_viewers, 0))::numeric
                / NULLIF(p.previous_viewers, 0)) * 100,
                2
            ) AS percent_change
        FROM latest l
        LEFT JOIN previous p
            ON l.game_name = p.game_name
        ORDER BY l.current_viewers DESC
        LIMIT %s;
    """

    return pd.read_sql(query, conn, params=(f"{days} days", f"{days} days", limit))


def trend_label(change):
    if change > 0:
        return "Trending Up", "up"
    if change < 0:
        return "Trending Down", "down"
    return "Stable", "stable"


def make_chart(df):
    if df.empty:
        return "<p>No Twitch data yet.</p>"

    fig = px.bar(
        df,
        x="game_name",
        y="current_viewers",
        text="current_viewers",
        title="Top Twitch Games by Current Viewers"
    )

    fig.update_layout(
        height=360,
        template="plotly_dark",
        paper_bgcolor="#181024",
        plot_bgcolor="#181024",
        margin=dict(l=30, r=30, t=55, b=40)
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def build_cards(df):
    if df.empty:
        return "<p>No Twitch data yet.</p>"

    cards = ""

    for index, row in df.iterrows():
        game = row["game_name"].title()
        viewers = fmt_num(row["current_viewers"])
        streams = fmt_num(row["current_streams"])
        change = int(row["viewer_change"]) if not pd.isna(row["viewer_change"]) else 0
        pct = row["percent_change"]

        pct_display = "N/A" if pd.isna(pct) else f"{pct:+}%"

        status, status_class = trend_label(change)

        cards += f"""
        <div class="game-card">
            <div class="rank">#{index + 1}</div>
            <h3>{game}</h3>

            <div class="stats">
                <div><strong>{viewers}</strong><span>Current Viewers</span></div>
                <div><strong>{streams}</strong><span>Live Streams</span></div>
                <div><strong>{change:+,}</strong><span>Viewer Change</span></div>
                <div><strong>{pct_display}</strong><span>% Change</span></div>
            </div>

            <div class="status {status_class}">{status}</div>
        </div>
        """

    return cards


def build_table(df):
    if df.empty:
        return "<p>No Twitch data yet.</p>"

    display = df.copy()
    display["game_name"] = display["game_name"].str.title()
    display["current_viewers"] = display["current_viewers"].apply(fmt_num)
    display["previous_viewers"] = display["previous_viewers"].apply(fmt_num)
    display["viewer_change"] = display["viewer_change"].apply(lambda x: f"{int(x):+,}")
    display["percent_change"] = display["percent_change"].apply(
        lambda x: "N/A" if pd.isna(x) else f"{x:+}%"
    )

    display = display.rename(columns={
        "game_name": "Game",
        "current_viewers": "Current Viewers",
        "previous_viewers": "Previous Viewers",
        "current_streams": "Live Streams",
        "previous_streams": "Previous Streams",
        "viewer_change": "Viewer Change",
        "percent_change": "% Change"
    })

    return display.to_html(index=False)


def build_dashboard(days=7):
    log_security_event("TWITCH_DASHBOARD_BUILD", "Building Twitch dashboard")

    conn = get_connection()
    df = get_twitch_momentum(conn, days=days, limit=15)
    conn.close()

    chart_html = make_chart(df)
    cards_html = build_cards(df)
    table_html = build_table(df)

    top_game = df.iloc[0]["game_name"].title() if not df.empty else "N/A"
    top_viewers = fmt_num(df.iloc[0]["current_viewers"]) if not df.empty else "N/A"

    html = f"""
<!DOCTYPE html>
<html>
<head>
<title>Project2026 Twitch Trends</title>
<style>
body {{
    background:
        radial-gradient(circle at top left, rgba(145,70,255,.35), transparent 30%),
        linear-gradient(135deg, #0f071a, #181024 50%, #241138);
    color: #f5f3ff;
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 24px;
}}

h1 {{
    color: #a970ff;
    margin-bottom: 4px;
}}

.subtitle {{
    color: #c4b5fd;
    margin-bottom: 18px;
}}

.nav a {{
    display: inline-block;
    background: #2e1065;
    color: white;
    padding: 10px 16px;
    margin-right: 8px;
    border-radius: 8px;
    text-decoration: none;
    border: 1px solid #6d28d9;
}}

.panel,
.game-card,
.summary-card {{
    background: rgba(24,16,36,.95);
    border: 1px solid #6d28d9;
    border-radius: 16px;
    box-shadow: 0 12px 30px rgba(0,0,0,.32);
}}

.summary {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-top: 20px;
}}

.summary-card {{
    padding: 18px;
    text-align: center;
}}

.summary-card strong {{
    display: block;
    font-size: 28px;
    color: #a970ff;
}}

.summary-card span {{
    color: #c4b5fd;
    font-size: 13px;
}}

.panel {{
    padding: 18px;
    margin-top: 22px;
}}

.grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-top: 20px;
}}

.game-card {{
    padding: 16px;
}}

.rank {{
    color: #a970ff;
    font-weight: bold;
}}

h3 {{
    margin: 6px 0 12px 0;
    font-size: 22px;
}}

.stats {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
}}

.stats div {{
    background: #0f071a;
    border: 1px solid #4c1d95;
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
    color: #c4b5fd;
}}

.status {{
    display: inline-block;
    margin-top: 12px;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: bold;
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

table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
}}

th,
td {{
    border-bottom: 1px solid #4c1d95;
    padding: 10px;
    text-align: left;
}}

th {{
    color: #a970ff;
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

<h1>Project2026 Twitch Trends</h1>
<p class="subtitle">Live gaming attention based on Twitch viewer counts, stream counts, and momentum.</p>

<div class="nav">
    <a href="index.html">Main</a>
    <a href="dashboard_youtube.html">YouTube</a>
    <a href="dashboard_steam.html">Steam</a>
    <a href="dashboard_twitch.html">Twitch</a>
    <a href="dashboard_kick.html">Kick</a>
</div>

<div class="summary">
    <div class="summary-card">
        <strong>{len(df)}</strong>
        <span>Games Tracked</span>
    </div>

    <div class="summary-card">
        <strong>{top_game}</strong>
        <span>Top Twitch Game</span>
    </div>

    <div class="summary-card">
        <strong>{top_viewers}</strong>
        <span>Top Viewer Count</span>
    </div>
</div>

<div class="panel">
    <h2>Twitch Viewer Graph</h2>
    {chart_html}
</div>

<div class="grid">
    {cards_html}
</div>

<div class="panel">
    <h2>Twitch Momentum Table</h2>
    {table_html}
</div>

</body>
</html>
"""

    with open("dashboard_twitch.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Created dashboard_twitch.html")
    log_security_event("TWITCH_DASHBOARD_SUCCESS", "Created dashboard_twitch.html")


if __name__ == "__main__":
    build_dashboard(7)