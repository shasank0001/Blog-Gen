"""Container health probe for a worker's own dispatcher loop."""
import sys
import time
from pathlib import Path

HEARTBEAT_FILE = Path('/tmp/blog-gen-worker.health')


def mark_alive():
    HEARTBEAT_FILE.touch()


def clear():
    HEARTBEAT_FILE.unlink(missing_ok=True)


def healthy():
    try:
        return 0 <= time.time() - HEARTBEAT_FILE.stat().st_mtime < 45
    except OSError:
        return False


if __name__ == '__main__':
    sys.exit(0 if healthy() else 1)
