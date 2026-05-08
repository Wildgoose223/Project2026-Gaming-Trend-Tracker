import os
import json
import psycopg2
from dotenv import load_dotenv

# =========================
# CONFIG
# =========================
load_dotenv()

DB_CONFIG = {
    "host": "localhost",
    "database": "YouTube_Data",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD")
}

if not DB_CONFIG["password"]:
    raise ValueError("Missing DB_PASSWORD in .env file")


def fetch_dashboard_data():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("SELECT MAX(run_time) FROM trending_games;")
    latest_run = cursor.fetchone()[0]

    if latest_run is None:
        cursor.close()
        conn.close()
        return None

    cursor.execute("""
        SELECT game_name, mentions, total_videos, percentage
        FROM trending_games
        WHERE run_time = %s
        ORDER BY mentions DESC;
    """, (latest_run,))
    current_games = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT run_time
        FROM trending_games
        ORDER BY run_time DESC
        LIMIT 2;
    """)
    runs = cursor.fetchall()
    previous_run = runs[1][0] if len(runs) > 1 else None

    current_with_change = []

    for game_name, mentions, total_videos, percentage in current_games:
        previous_mentions = 0

        if previous_run:
            cursor.execute("""
                SELECT mentions
                FROM trending_games
                WHERE run_time = %s
                AND game_name = %s;
            """, (previous_run, game_name))

            result = cursor.fetchone()
            if result:
                previous_mentions = result[0]

        change = mentions - previous_mentions

        current_with_change.append({
            "game_name": game_name,
            "mentions": mentions,
            "total_videos": total_videos,
            "percentage": percentage,
            "previous_mentions": previous_mentions,
            "change": change
        })

    cursor.execute("""
        SELECT 
            game_name,
            SUM(mentions) AS total_appearances,
            COUNT(*) AS times_detected
        FROM trending_games
        WHERE DATE(run_time) = CURRENT_DATE
        GROUP BY game_name
        ORDER BY total_appearances DESC
        LIMIT 10;
    """)
    top_today = cursor.fetchall()

    total_videos = current_games[0][2] if current_games else 0
    recognized_games = len(current_games)
    total_appearances = sum(row[1] for row in current_games)

    detection_rate = 0
    if total_videos:
        detection_rate = round((total_appearances / total_videos) * 100, 2)

    cursor.execute("""
        SELECT term, count
        FROM unknown_terms
        ORDER BY count DESC, last_seen DESC
        LIMIT 10;
    """)
    unknown_terms = cursor.fetchall()

    cursor.execute("""
        SELECT game_name
        FROM trending_games
        WHERE DATE(run_time) = CURRENT_DATE
        GROUP BY game_name
        ORDER BY SUM(mentions) DESC
        LIMIT 10;
    """)
    chart_games = [row[0] for row in cursor.fetchall()]

    if chart_games:
        cursor.execute("""
            SELECT run_time, game_name, mentions
            FROM trending_games
            WHERE DATE(run_time) = CURRENT_DATE
            AND game_name = ANY(%s)
            ORDER BY run_time ASC, game_name ASC;
        """, (chart_games,))
        chart_rows = cursor.fetchall()
    else:
        chart_rows = []

    chart_data = [
        {
            "run_time": row[0].strftime("%I:%M %p"),
            "game_name": row[1],
            "mentions": row[2]
        }
        for row in chart_rows
    ]

    cursor.close()
    conn.close()

    return {
        "latest_run": latest_run,
        "current_games": current_with_change,
        "top_today": top_today,
        "recognized_games": recognized_games,
        "total_videos": total_videos,
        "total_appearances": total_appearances,
        "detection_rate": detection_rate,
        "unknown_terms": unknown_terms,
        "chart_data": chart_data
    }


def trend_label(change):
    if change > 0:
        return "Trending Up"
    if change < 0:
        return "Trending Down"
    return "Stable"


def trend_class(change):
    if change > 0:
        return "up"
    if change < 0:
        return "down"
    return "stable"


def generate_dashboard():
    data = fetch_dashboard_data()

    if data is None:
        html = """
        <html>
        <head><title>YouTube Gaming Trend Dashboard</title></head>
        <body>
            <h1>YouTube Gaming Trend Dashboard</h1>
            <p>No trend data found yet. Run the collector script first.</p>
        </body>
        </html>
        """

        with open("dashboard.html", "w", encoding="utf-8") as file:
            file.write(html)

        print("Dashboard created, but no data was found.")
        return

    current_rows = ""

    for rank, game in enumerate(data["current_games"], start=1):
        change = game["change"]
        change_text = f"+{change}" if change > 0 else str(change)

        current_rows += f"""
        <tr>
            <td>{rank}</td>
            <td>{game["game_name"]}</td>
            <td>Appears in {game["mentions"]} of {game["total_videos"]} trending videos</td>
            <td>{game["previous_mentions"]}</td>
            <td class="{trend_class(change)}">{change_text}</td>
            <td>{game["percentage"]}%</td>
            <td class="{trend_class(change)}">{trend_label(change)}</td>
        </tr>
        """

    today_rows = ""

    for rank, row in enumerate(data["top_today"], start=1):
        game_name, total_appearances, times_detected = row

        today_rows += f"""
        <tr>
            <td>{rank}</td>
            <td>{game_name}</td>
            <td>{total_appearances}</td>
            <td>{times_detected}</td>
        </tr>
        """

    unknown_rows = ""

    for term, count in data["unknown_terms"]:
        unknown_rows += f"""
        <tr>
            <td>{term}</td>
            <td>{count}</td>
        </tr>
        """

    top_game = data["top_today"][0][0] if data["top_today"] else "No data"
    top_game_total = data["top_today"][0][1] if data["top_today"] else 0
    chart_json = json.dumps(data["chart_data"])

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>YouTube Gaming Trend Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f6f8;
                margin: 0;
                padding: 30px;
                color: #222;
            }}

            .container {{
                max-width: 1250px;
                margin: auto;
            }}

            h1 {{
                margin-bottom: 5px;
            }}

            .subtitle {{
                color: #555;
                margin-bottom: 25px;
                font-size: 16px;
            }}

            .explain, .chart-card {{
                background: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                margin-bottom: 25px;
                line-height: 1.6;
            }}

            .cards {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 15px;
                margin-bottom: 30px;
            }}

            .card {{
                background: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }}

            .card h2 {{
                font-size: 15px;
                color: #555;
                margin-bottom: 10px;
            }}

            .big {{
                font-size: 26px;
                font-weight: bold;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                margin-bottom: 30px;
            }}

            th, td {{
                padding: 14px;
                text-align: left;
                border-bottom: 1px solid #eee;
            }}

            th {{
                background-color: #222;
                color: white;
            }}

            .up {{
                color: green;
                font-weight: bold;
            }}

            .down {{
                color: red;
                font-weight: bold;
            }}

            .stable {{
                color: #777;
                font-weight: bold;
            }}

            .section-note {{
                color: #555;
                margin-top: -10px;
                margin-bottom: 12px;
            }}

            .footer {{
                color: #666;
                font-size: 14px;
                margin-top: 25px;
            }}

            canvas {{
                max-height: 420px;
            }}
        </style>
    </head>

    <body>
        <div class="container">
            <h1>YouTube Gaming Trend Dashboard</h1>
            <p class="subtitle">
                A PostgreSQL-backed dashboard that tracks which games appear in trending YouTube gaming video titles.
            </p>

            <div class="explain">
                <strong>How to read this dashboard:</strong><br>
                Each update scans the top trending YouTube gaming videos in the US.
                If a known game title or alias appears in a video title, it counts as one appearance.
                For example, if Roblox appears in 4 out of 25 trending video titles, it is shown as
                “Appears in 4 of 25 trending videos.”
                <br><br>
                The change column compares the latest update against the previous update, similar to a stock page.
                Higher appearances mean the game is showing up more often in trending gaming content.
            </div>

            <div class="cards">
                <div class="card">
                    <h2>Top Game Today</h2>
                    <div class="big">{top_game}</div>
                    <p>{top_game_total} total appearances today</p>
                </div>

                <div class="card">
                    <h2>Recognized Games</h2>
                    <div class="big">{data["recognized_games"]}</div>
                    <p>Games detected in latest pull</p>
                </div>

                <div class="card">
                    <h2>Detection Rate</h2>
                    <div class="big">{data["detection_rate"]}%</div>
                    <p>{data["total_appearances"]} appearances across {data["total_videos"]} videos</p>
                </div>

                <div class="card">
                    <h2>Last Updated</h2>
                    <div class="big">{data["latest_run"].strftime("%I:%M %p")}</div>
                    <p>{data["latest_run"].strftime("%Y-%m-%d")}</p>
                </div>
            </div>

            <h2>Game Trend Over Time</h2>
            <p class="section-note">
                This line chart shows how often the top games appeared across each data pull today.
                It works like a stock chart, but tracks game appearances instead of prices.
            </p>

            <div class="chart-card">
                <canvas id="trendChart"></canvas>
            </div>

            <h2>Recognized Games in Latest Pull</h2>
            <p class="section-note">
                These are games from the trusted game library that appeared in the latest YouTube trending pull.
            </p>

            <table>
                <tr>
                    <th>Rank</th>
                    <th>Game</th>
                    <th>Current Appearance Count</th>
                    <th>Previous Count</th>
                    <th>Change Since Last Update</th>
                    <th>Share of Trending Videos</th>
                    <th>Trend</th>
                </tr>
                {current_rows}
            </table>

            <h2>Top Games Today</h2>
            <p class="section-note">
                This combines all pulls from today instead of only showing the latest snapshot.
            </p>

            <table>
                <tr>
                    <th>Rank</th>
                    <th>Game</th>
                    <th>Total Appearances Today</th>
                    <th>Times Detected Today</th>
                </tr>
                {today_rows}
            </table>

            <h2>Possible Unmatched Trends</h2>
            <p class="section-note">
                These are repeated terms found in trending titles that are not currently confirmed as games in the trusted library.
                They can help identify new games, slang, DLC names, or missing aliases.
            </p>

            <table>
                <tr>
                    <th>Unknown Term</th>
                    <th>Times Seen</th>
                </tr>
                {unknown_rows}
            </table>

            <p class="footer">
                Dashboard generated from PostgreSQL trend data. This is version 1.0 of Project2026.
            </p>
        </div>

        <script>
            const chartData = {chart_json};

            const labels = [...new Set(chartData.map(item => item.run_time))];
            const games = [...new Set(chartData.map(item => item.game_name))];

            const colorList = [
                "#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c",
                "#0891b2", "#ca8a04", "#4f46e5", "#be123c", "#15803d"
            ];

            const datasets = games.map((game, index) => {{
                return {{
                    label: game,
                    data: labels.map(time => {{
                        const found = chartData.find(item => item.run_time === time && item.game_name === game);
                        return found ? found.mentions : 0;
                    }}),
                    borderColor: colorList[index % colorList.length],
                    backgroundColor: colorList[index % colorList.length],
                    borderWidth: 2,
                    tension: 0.25,
                    pointRadius: 3,
                    fill: false
                }};
            }});

            const ctx = document.getElementById("trendChart").getContext("2d");

            new Chart(ctx, {{
                type: "line",
                data: {{
                    labels: labels,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: "top"
                        }},
                        tooltip: {{
                            mode: "index",
                            intersect: false
                        }}
                    }},
                    interaction: {{
                        mode: "nearest",
                        axis: "x",
                        intersect: false
                    }},
                    scales: {{
                        x: {{
                            title: {{
                                display: true,
                                text: "Pull Time"
                            }}
                        }},
                        y: {{
                            beginAtZero: true,
                            title: {{
                                display: true,
                                text: "Appearances in Trending Videos"
                            }},
                            ticks: {{
                                stepSize: 1
                            }}
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """

    with open("dashboard.html", "w", encoding="utf-8") as file:
        file.write(html)

    print("Dashboard updated successfully: dashboard.html")


if __name__ == "__main__":
    generate_dashboard()