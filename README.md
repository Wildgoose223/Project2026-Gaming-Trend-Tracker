# Project2026 – Gaming Trend Analytics Dashboard

A multi-source gaming analytics platform that tracks trending games across YouTube and Steam, stores historical data in PostgreSQL, and generates a live dashboard for trend analysis and visualization.

---

# Live Dashboard

https://wildgoose223.github.io/Project2026-Gaming-Trend-Tracker/

---

# Dashboard Features

- YouTube Gaming trend tracking
- Steam player analytics
- PostgreSQL data persistence
- Historical snapshot storage
- Automated dashboard updates
- RAWG API game metadata integration
- Trend summaries and rankings
- Cross-platform comparison analytics
- GitHub Pages dashboard hosting

---

# Dashboard Overview

Project2026 compares:

- What people are watching on YouTube
- What people are actively playing on Steam
- Cross-platform trend overlap
- Historical gaming trend data over time

The dashboard includes:
- Trend graphs
- Steam vs YouTube comparisons
- Trend summaries
- Historical rankings
- Automated data visualization

---

# Tech Stack

## Languages & Tools
- Python
- PostgreSQL
- HTML/CSS
- Git/GitHub

## APIs
- YouTube Data API v3
- Steam API
- RAWG API

## Python Libraries
- psycopg2
- pandas
- requests
- python-dotenv
- matplotlib

---

# Project Structure

Project2026/
│
├── dashboard/
│   ├── index.html
│   ├── dashboard_today.html
│   ├── dashboard_week.html
│   ├── dashboard_month.html
│
├── scripts/
│   ├── dashboard_generator.py
│   ├── dashboard_v2.py
│   ├── youtube_trend_pull_v2.py
│   ├── youtube_trends_to_db.py
│   ├── steam_trends_to_db.py
│   ├── build_game_library_from_rawg.py
│   ├── build_steam_library.py
│   ├── rawg_library_builder.py
│   ├── sync_game_library.py
│
├── screenshots/
│
├── sql/
│
├── .gitignore
├── README.md
└── index.html

---

# How It Works

## 1. Data Collection

The project pulls:
- Trending gaming videos from YouTube
- Current Steam player counts
- Game metadata from RAWG

---

## 2. Data Processing

Python scripts:
- Clean and normalize titles
- Match games using alias libraries
- Store results in PostgreSQL
- Generate trend summaries

---

## 3. Dashboard Generation

The dashboard is automatically generated using:
- HTML
- CSS
- Python-generated analytics data

---

## 4. Historical Trend Analysis

The system stores snapshots over time to analyze:
- Rising games
- Declining games
- Platform popularity differences
- Long-term gaming trends

---

# Automation

Project2026 supports automated scheduled updates using:
- Windows Task Scheduler
- Batch automation scripts
- Daily data refresh pipelines

---

# Future Improvements

Planned features include:
- Twitch integration
- Historical trend momentum
- Interactive filters
- Date-range selection
- Live database hosting
- Multilingual dashboard support
- Trend prediction
- AI-assisted analytics
- Cross-platform weighted trend scoring

---

# Why This Project Exists

Project2026 started as a gaming trend tracker and evolved into a larger analytics platform focused on:
- trend intelligence
- automated analytics
- historical tracking
- dashboard visualization
- cross-platform gaming insights

The goal is to explore how entertainment, player behavior, and content trends intersect across platforms.

---

# Author

GitHub:
https://github.com/Wildgoose223
