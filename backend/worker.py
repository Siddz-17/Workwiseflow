"""RQ worker for background ingestion. Run on Linux/macOS (RQ needs fork):  python worker.py"""

from redis import Redis
from rq import Queue, Worker

from app.config import get_settings

if __name__ == "__main__":
    url = get_settings().redis_url
    if not url:
        raise SystemExit("Set REDIS_URL to run the worker")
    conn = Redis.from_url(url)
    Worker([Queue("ingestion", connection=conn)], connection=conn).work()
