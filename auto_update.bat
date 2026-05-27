@echo off
cd /d C:\Users\Samob\OneDrive\Desktop\Project2026

python scripts\youtube_trends_to_db.py
python scripts\steam_trends_to_db.py
python scripts\dashboard_generator.py

copy dashboard\index.html index.html /Y

git pull
git add .
git commit -m "Auto update dashboard"
git push

echo Project2026 update complete.
pause