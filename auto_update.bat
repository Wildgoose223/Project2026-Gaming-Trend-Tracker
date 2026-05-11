@echo off

cd /d C:\Users\Samob\OneDrive\Desktop\Project2026

python youtube_trends_to_db.py

python dashboard_generator.py

git add .

git commit -m "Automated dashboard update"

git pull origin main --rebase

git push