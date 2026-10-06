"""Long-running scheduler: scrape -> ingest every INTERVAL_SECONDS.

Hardened vs. the first version: absolute paths (no CWD dependence),
UTF-8 child environment (Bengali titles crash cp1252 redirected stdout),
sys.executable instead of bare "python", and a lock file so overlapping
cycles can never stack up.
"""
import os
import subprocess
import sys
import logging
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOCK_PATH = BASE_DIR / "scheduler.lock"
INTERVAL_SECONDS = 6 * 3600  # Every 6 hours

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def _child_env():
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def execute_pipeline():
    logging.info("Starting scrape job...")
    env = _child_env()
    try:
        # Run scraping suite
        subprocess.run([sys.executable, str(BASE_DIR / "scraper" / "main.py")],
                       cwd=str(BASE_DIR), check=True, env=env)
        # Ingest to database
        subprocess.run([sys.executable, str(BASE_DIR / "src" / "storage" / "db.py")],
                       cwd=str(BASE_DIR), check=True, env=env)
        logging.info("Scrape and ingestion cycle completed.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Execution failed: {e}")


def _acquire_lock():
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


if __name__ == "__main__":
    if not _acquire_lock():
        logging.error("Another scheduler holds %s; exiting.", LOCK_PATH)
        sys.exit(1)
    try:
        while True:
            execute_pipeline()
            logging.info(f"Sleeping for {INTERVAL_SECONDS / 3600} hours...")
            time.sleep(INTERVAL_SECONDS)
    finally:
        try:
            os.remove(LOCK_PATH)
        except OSError:
            pass