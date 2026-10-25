"""Usage limits for the public demo (PUBLIC_DEMO=1): the deployed app spends our API credits, so each visitor gets
a fair hourly allowance per feature, under a global daily ceiling. In-memory, per process: enough for a demo."""
import os
import time
from collections import defaultdict, deque

ENABLED = os.getenv("PUBLIC_DEMO") == "1"
# path prefix -> (bucket, per visitor per hour, all visitors per day)
RULES = [
    ("/api/chat", "chat", 30, 1500),
    ("/api/report", "report", 10, 300),
    ("/api/transcribe", "voice", 40, 1500),
    ("/api/speak", "voice", 40, 1500),
    ("/api/companies/discover", "agents", 3, 60),
    ("/api/swarm", "agents", 2, 40),
    ("/api/research", "agents", 4, 80),
]
_hits: dict = defaultdict(deque)
_day: dict = defaultdict(deque)


def check(path: str, method: str, visitor: str) -> str | None:
    """Returns an error message when the request is over its limit, else None."""
    if not ENABLED or method != "POST" and not path.startswith("/api/speak"):
        return None
    for prefix, bucket, per_hour, per_day in RULES:
        if path.startswith(prefix):
            now = time.time()
            mine, everyone = _hits[(bucket, visitor)], _day[bucket]
            while mine and now - mine[0] > 3600:
                mine.popleft()
            while everyone and now - everyone[0] > 86400:
                everyone.popleft()
            if len(everyone) >= per_day:
                return "The public demo reached its daily limit for this feature. Try again tomorrow."
            if len(mine) >= per_hour:
                return "You reached the demo limit for this feature. Try again in an hour."
            mine.append(now)
            everyone.append(now)
            return None
    return None
