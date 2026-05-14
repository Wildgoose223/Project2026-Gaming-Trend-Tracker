import os
import json
from datetime import datetime

import psycopg2
from dotenv import load_dotenv


# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv()


# =========================
# CONFIG
# =========================
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

if not DB_CONFIG["password"]:
    raise ValueError("Missing DB_PASSWORD in .env file")


# =========================
# FETCH DASHBOARD DATA
# =========================
def fetch_dashboard_data():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        WITH current_runs AS (
            SELECT
                run_time,
                MAX(total_videos) AS videos_in_pull
            FROM trending_games
            WHERE DATE(run_time) = CURRENT_DATE
            GROUP BY run_time
        ),
        current_total AS (
            SELECT
                COALESCE(SUM(videos_in_pull), 0) AS total_videos_today,
                COUNT(*) AS pulls_today
            FROM current_runs
        ),
        current_games AS (
            SELECT
                game_name,
                SUM(mentions) AS mentions_today,
                MAX(rawg_name) AS rawg_name,
                MAX(released) AS released,
                MAX(rating) AS rating,
                MAX(metacritic) AS metacritic,
                MAX(platforms) AS platforms,
                MAX(genres) AS genres,
                MAX(background_image) AS background_image
            FROM trending_games
            WHERE DATE(run_time) = CURRENT_DATE
            GROUP BY game_name
        ),
        previous_games AS (
            SELECT
                game_name,
                SUM(mentions) AS mentions_yesterday
            FROM trending_games
            WHERE DATE(run_time) = CURRENT_DATE - INTERVAL '1 day'
            GROUP BY game_name
        )
        SELECT
            current_games.game_name,
            current_games.mentions_today,
            current_total.total_videos_today,
            ROUND(
                (current_games.mentions_today::numeric / NULLIF(current_total.total_videos_today, 0)) * 100,
                2
            ) AS percentage_today,
            COALESCE(previous_games.mentions_yesterday, 0) AS mentions_yesterday,
            current_games.mentions_today - COALESCE(previous_games.mentions_yesterday, 0) AS change,
            current_games.rawg_name,
            current_games.released,
            current_games.rating,
            current_games.metacritic,
            current_games.platforms,
            current_games.genres,
            current_games.background_image,
            current_total.pulls_today
        FROM current_games
        CROSS JOIN current_total
        LEFT JOIN previous_games
            ON current_games.game_name = previous_games.game_name
        ORDER BY current_games.mentions_today DESC
        LIMIT 10;
    """)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    dashboard_data = []

    for row in rows:
        (
            game_name,
            mentions_today,
            total_videos_today,
            percentage_today,
            mentions_yesterday,
            change,
            rawg_name,
            released,
            rating,
            metacritic,
            platforms,
            genres,
            background_image,
            pulls_today
        ) = row

        if change > 0:
            trend_label = "Trending Up"
        elif change < 0:
            trend_label = "Declining"
        else:
            trend_label = "Stable"

        dashboard_data.append({
            "game_name": game_name,
            "display_name": rawg_name or game_name,
            "mentions": mentions_today,
            "total_videos": total_videos_today,
            "percentage": percentage_today,
            "mentions_yesterday": mentions_yesterday,
            "change": change,
            "trend_label": trend_label,
            "released": str(released) if released else "Unknown",
            "rating": rating if rating is not None else "N/A",
            "metacritic": metacritic if metacritic is not None else "N/A",
            "platforms": platforms or "Unknown",
            "genres": genres or "Unknown",
            "background_image": background_image or "",
            "pulls_today": pulls_today
        })

    return dashboard_data


# =========================
# GENERATE HTML
# =========================
def generate_dashboard():
    data = fetch_dashboard_data()

    chart_labels = [item["display_name"] for item in data]
    chart_values = [item["mentions"] for item in data]

    pulls_today = data[0]["pulls_today"] if data else 0
    total_videos_today = data[0]["total_videos"] if data else 0

    cards_html = ""

    for rank, item in enumerate(data, start=1):
        image_html = ""

        if item["background_image"]:
            image_html = f"""
            <img class="game-image" src="{item["background_image"]}" alt="{item["display_name"]}">
            """

        change_display = f"+{item['change']}" if item["change"] > 0 else item["change"]

        cards_html += f"""
        <div class="game-card">
            {image_html}

            <div class="game-content">
                <div class="rank">#{rank}</div>

                <h2>{item["display_name"]}</h2>

                <p class="subtitle">
                    Matched as: <strong>{item["game_name"]}</strong>
                </p>

                <div class="stats">
                    <div>
                        <span class="stat-value">{item["mentions"]}</span>
                        <span class="stat-label">Mentions Today</span>
                    </div>

                    <div>
                        <span class="stat-value">{item["percentage"]}%</span>
                        <span class="stat-label">Of Today's Trending Videos</span>
                    </div>

                    <div>
                        <span class="stat-value">{change_display}</span>
                        <span class="stat-label">Vs Yesterday</span>
                    </div>
                </div>

                <p class="meaning">
                    <strong>{item["display_name"]}</strong> appeared in 
                    <strong>{item["percentage"]}%</strong> of all trending YouTube Gaming videos collected today.
                </p>

                <p class="trend {item["trend_label"].replace(" ", "-").lower()}">
                    {item["trend_label"]}
                </p>

                <div class="metadata">
                    <p><strong>Platforms:</strong> {item["platforms"]}</p>
                    <p><strong>Genres:</strong> {item["genres"]}</p>
                    <p><strong>Released:</strong> {item["released"]}</p>
                    <p><strong>RAWG Rating:</strong> {item["rating"]}</p>
                    <p><strong>Metacritic:</strong> {item["metacritic"]}</p>
                </div>
            </div>
        </div>
        """

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Project2026 Gaming Trend Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
        body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: #e5e7eb;
        }}

        header {{
            padding: 32px;
            text-align: center;
            background: #111827;
            border-bottom: 1px solid #334155;
        }}

        header h1 {{
            margin: 0;
            font-size: 36px;
        }}

        header p {{
            color: #94a3b8;
            margin-top: 8px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 32px;
        }}

        .summary-box {{
            background: #111827;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 32px;
            color: #cbd5e1;
            line-height: 1.6;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-top: 18px;
        }}

        .summary-stat {{
            background: #020617;
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 16px;
            text-align: center;
        }}

        .summary-stat span {{
            display: block;
            font-size: 28px;
            font-weight: bold;
            color: #38bdf8;
        }}

        .summary-stat small {{
            color: #94a3b8;
        }}

        .chart-section {{
            background: #111827;
            padding: 24px;
            border-radius: 16px;
            margin-bottom: 32px;
            border: 1px solid #334155;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(330px, 1fr));
            gap: 24px;
        }}

        .game-card {{
            background: #111827;
            border: 1px solid #334155;
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
        }}

        .game-image {{
            width: 100%;
            height: 180px;
            object-fit: cover;
            display: block;
        }}

        .game-content {{
            padding: 20px;
        }}

        .rank {{
            color: #38bdf8;
            font-weight: bold;
            font-size: 18px;
        }}

        h2 {{
            margin: 8px 0;
            font-size: 24px;
        }}

        .subtitle {{
            color: #94a3b8;
            font-size: 14px;
        }}

        .stats {{
            display: flex;
            justify-content: space-between;
            margin: 20px 0;
            gap: 12px;
        }}

        .stats div {{
            background: #1e293b;
            padding: 12px;
            border-radius: 12px;
            text-align: center;
            flex: 1;
        }}

        .stat-value {{
            display: block;
            font-size: 22px;
            font-weight: bold;
        }}

        .stat-label {{
            display: block;
            color: #94a3b8;
            font-size: 12px;
            margin-top: 4px;
        }}

        .meaning {{
            background: #020617;
            border: 1px solid #1e293b;
            padding: 12px;
            border-radius: 12px;
            color: #cbd5e1;
            font-size: 14px;
            line-height: 1.5;
        }}

        .trend {{
            display: inline-block;
            padding: 8px 12px;
            border-radius: 999px;
            font-weight: bold;
            font-size: 13px;
            margin-top: 10px;
        }}

        .trending-up {{
            background: #064e3b;
            color: #6ee7b7;
        }}

        .declining {{
            background: #7f1d1d;
            color: #fecaca;
        }}

        .stable {{
            background: #334155;
            color: #cbd5e1;
        }}

        .metadata {{
            margin-top: 18px;
            font-size: 14px;
            color: #cbd5e1;
            line-height: 1.5;
        }}

        .metadata p {{
            margin: 8px 0;
        }}

        footer {{
            text-align: center;
            color: #64748b;
            padding: 24px;
            font-size: 13px;
        }}
    </style>
</head>

<body>
    <header>
        <h1>Project2026 Gaming Trend Dashboard</h1>
        <p>Daily gaming trend summary from YouTube Gaming, enriched with RAWG metadata</p>
        <p>Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </header>

    <div class="container">
        <section class="summary-box">
            <strong>How to read this dashboard:</strong>
            This dashboard shows what percentage of today's collected trending YouTube Gaming videos each game appeared in.
            For example, if a game shows 24%, that means it appeared in 24% of the trending videos collected today.

            <div class="summary-grid">
                <div class="summary-stat">
                    <span>{pulls_today}</span>
                    <small>Pulls Today</small>
                </div>

                <div class="summary-stat">
                    <span>{total_videos_today}</span>
                    <small>Total Trending Videos Checked Today</small>
                </div>

                <div class="summary-stat">
                    <span>{len(data)}</span>
                    <small>Top Games Displayed</small>
                </div>
            </div>
        </section>

        <section class="chart-section">
            <canvas id="trendChart"></canvas>
        </section>

        <section class="grid">
            {cards_html}
        </section>
    </div>

    <footer>
        Project2026 | YouTube Data API + PostgreSQL + RAWG
    </footer>

    <script>
        const labels = {json.dumps(chart_labels)};
        const values = {json.dumps(chart_values)};

        const ctx = document.getElementById('trendChart');

        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: labels,
                datasets: [{{
                    label: 'Total Mentions Today',
                    data: values,
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        labels: {{
                            color: '#e5e7eb'
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{
                            color: '#e5e7eb'
                        }},
                        grid: {{
                            color: '#334155'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            color: '#e5e7eb',
                            precision: 0
                        }},
                        grid: {{
                            color: '#334155'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as file:
        file.write(html)

    print("Daily dashboard updated successfully: index.html")


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    generate_dashboard()