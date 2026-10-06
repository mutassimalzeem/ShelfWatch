@echo off
cd /d "i:\My Drive\Coding\Data Science Project\ShelfWatch\scraper"
set PYTHONUNBUFFERED=1
python -u main.py > "i:\My Drive\Coding\Data Science Project\ShelfWatch\scraper\_full_run2.txt" 2>&1
