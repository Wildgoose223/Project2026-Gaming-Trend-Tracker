import os
from datetime import datetime

print("=" * 50)
print("Project2026 Gaming Trend Tracker")
print("Started:", datetime.now())
print("=" * 50)

print("\nPulling YouTube trends...")
os.system("python youtube_trends.py")

print("\nPulling Steam trends...")
os.system("python steam_trends.py")

print("\nRebuilding dashboards...")
os.system("python dashboard_generator.py")

print("\nCompleted:", datetime.now())
print("=" * 50)