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
    log_security_event("DB_CONNECT", "Opening PostgreSQL connection for Steam dashboard")

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


def get_steam_momentum(conn, days=7, limit=15):
    query = """
        WITH ranked AS (
            SELECT
                LOWER(game_name) AS game_name,
                steam_appid,
                current_players,
                captured_at,
                ROW_NUMBER() OVER (
                    PARTITION BY LOWER(game_name)
                    ORDER BY captured_at DESC
                ) AS rn
            FROM steam_trends
            WHERE captured_at >= NOW() - (%s * INTERVAL '1 day')
        ),
        latest AS (
            SELECT
                game_name,
                steam_appid,
                current_players,
                captured_at
            FROM ranked
            WHERE rn = 1
        ),
        previous AS (
            SELECT
                game_name,
                current_players AS previous_players,
                captured_at AS previous_captured_at
            FROM ranked
            WHERE rn = 2
        )
        SELECT
            l.game_name,
            l.steam_appid,
            l.current_players,
            COALESCE(p.previous_players, 0) AS previous_players,
            l.current_players - COALESCE(p.previous_players, 0) AS player_change,
            ROUND(
                ((l.current_players - COALESCE(p.previous_players, 0))::numeric
                / NULLIF(p.previous_players, 0)) * 100,
                2
            ) AS percent_change
        FROM latest l
        LEFT JOIN previous p
            ON l.game_name = p.game_name
        ORDER BY l.current_players DESC
        LIMIT %s;
    """

    return pd.read_sql(query, conn, params=(days, limit))


def trend_label(change):
    if change > 0:
        return "Trending Up", "up"
    if change < 0:
        return "Trending Down", "down"
    return "Stable", "stable"


def make_chart(df):
    if df.empty:
        return "<p>No Steam data yet.</p>"

    fig = px.bar(
        df,
        x="game_name",
        y="current_players",
        text="current_players",
        title="Top Steam Games by Current Players"
    )

    fig.update_traces(
        texttemplate="%{text:,}",
        textposition="outside"
    )

    fig.update_layout(
        height=380,
        template="plotly_dark",
        paper_bgcolor="#07111f",
        plot_bgcolor="#07111f",
        margin=dict(l=30, r=30, t=55, b=70),
        xaxis_title="Game",
        yaxis_title="Current Players"
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def build_cards(df):
    if df.empty:
        return "<p>No Steam data yet.</p>"

    cards = ""

    for index, row in df.iterrows():
        game = row["game_name"].title()
        players = fmt_num(row["current_players"])
        previous = fmt_num(row["previous_players"])

        change = 0 if pd.isna(row["player_change"]) else int(row["player_change"])
        pct = row["percent_change"]
        pct_display = "N/A" if pd.isna(pct) else f"{pct:+}%"

        status, status_class = trend_label(change)

        cards += f"""
        <div class="game-card">
            <div class="rank">#{index + 1}</div>
            <h3>{game}</h3>

            <div class="stats">
                <div><strong>{players}</strong><span>Current Players</span></div>
                <div><strong>{previous}</strong><span>Previous Players</span></div>
                <div><strong>{change:+,}</strong><span>Player Change</span></div>
                <div><strong>{pct_display}</strong><span>% Change</span></div>
            </div>

            <div class="status {status_class}">{status}</div>
        </div>
        """

    return cards


def build_table(df):
    if df.empty:
        return "<p>No Steam data yet.</p>"

    display = df.copy()

    display["game_name"] = display["game_name"].str.title()
    display["current_players"] = display["current_players"].apply(fmt_num)
    display["previous_players"] = display["previous_players"].apply(fmt_num)
    display["player_change"] = display["player_change"].apply(
        lambda x: "N/A" if pd.isna(x) else f"{int(x):+,}"
    )
    display["percent_change"] = display["percent_change"].apply(
        lambda x: "N/A" if pd.isna(x) else f"{x:+}%"
    )

    display = display.rename(columns={
        "game_name": "Game",
        "steam_appid": "Steam App ID",
        "current_players": "Current Players",
        "previous_players": "Previous Players",
        "player_change": "Player Change",
        "percent_change": "% Change"
    })

    return display.to_html(index=False, classes="data-table")


def build_dashboard(days=7):
    log_security_event("STEAM_DASHBOARD_BUILD", "Building Steam dashboard")

    conn = None

    try:
        conn = get_connection()
        df = get_steam_momentum(conn, days=days, limit=15)
    except Exception as e:
        log_security_event("STEAM_DASHBOARD_ERROR", str(e))
        print(f"Steam dashboard failed: {e}")
        return
    finally:
        if conn:
            conn.close()

    chart_html = make_chart(df)
    cards_html = build_cards(df)
    table_html = build_table(df)

    top_game = df.iloc[0]["game_name"].title() if not df.empty else "N/A"
    top_players = fmt_num(df.iloc[0]["current_players"]) if not df.empty else "N/A"

    html = f"""
<!DOCTYPE html>
<html>
<head>
<title>Project2026 Steam Trends</title>

<style>
body {{
    background:
        radial-gradient(circle at top left, rgba(59,130,246,.30), transparent 30%),
        linear-gradient(135deg, #020617, #07111f 50%, #0f2740);
    color: #eff6ff;
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 24px;
}}

h1 {{
    color: #60a5fa;
    margin-bottom: 4px;
}}

.subtitle {{
    color: #bfdbfe;
    margin-bottom: 18px;
}}

.nav {{
    margin-bottom: 18px;
}}

.nav a {{
    display: inline-block;
    background: #0f2740;
    color: white;
    padding: 10px 16px;
    margin-right: 8px;
    margin-bottom: 8px;
    border-radius: 8px;
    text-decoration: none;
    border: 1px solid #3b82f6;
}}

.nav a:hover {{
    background: #1d4ed8;
}}

.panel,
.game-card,
.summary-card {{
    background: rgba(7,17,31,.95);
    border: 1px solid #3b82f6;
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
    color: #60a5fa;
}}

.summary-card span {{
    color: #bfdbfe;
    font-size: 13px;
}}

.panel {{
    padding: 18px;
    margin-top: 22px;
    overflow-x: auto;
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
    color: #60a5fa;
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
    background: #020617;
    border: 1px solid #1d4ed8;
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
    color: #bfdbfe;
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
    border-bottom: 1px solid #1d4ed8;
    padding: 10px;
    text-align: left;
}}

th {{
    color: #60a5fa;
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

<h1>Project2026 Steam Trends</h1>
<p class="subtitle">Active player demand based on Steam current player counts and momentum.</p>

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
        <span>Top Steam Game</span>
    </div>

    <div class="summary-card">
        <strong>{top_players}</strong>
        <span>Top Player Count</span>
    </div>
</div>

<div class="panel">
    <h2>Steam Player Graph</h2>
    {chart_html}
</div>

<div class="grid">
    {cards_html}
</div>

<div class="panel">
    <h2>Steam Momentum Table</h2>
    {table_html}
</div>

</body>
</html>
"""

    with open("dashboard_steam.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Created dashboard_steam.html")
    log_security_event("STEAM_DASHBOARD_SUCCESS", "Created dashboard_steam.html")


if __name__ == "__main__":
    build_dashboard(7)