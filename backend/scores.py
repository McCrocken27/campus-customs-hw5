"""Yale Athletics scores for the dashboard's sports ticker (ported from HW4).

Source: the public calendar RSS feed on yalebulldogs.com (Yale's official athletics
site). Each finished game's description has a result line like "W 3-1" or "L 25-38".
The feed is fetched at most every 15 minutes and cached in memory; if it can't be
reached, the last good copy is served, or an empty board if there isn't one yet.
These are real scores from Yale, not shop data, so they don't go through the MCP server.
"""

from __future__ import annotations

import logging
import re
import ssl
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

import truststore
from pydantic import BaseModel

FEED_URL = "https://yalebulldogs.com/calendar.ashx/calendar.rss?sport_id=0"
SOURCE_URL = "https://yalebulldogs.com"
CACHE_SECONDS = 15 * 60
MAX_RESULTS = 15
MAX_UPCOMING = 6

SIDEARM = "{http://sidearmsports.com/schemas/cal_rss/1.0/}"
RESULT_LINE = re.compile(r"^\s*([WLT])\s+(\d+)\s*-\s*(\d+)", re.MULTILINE)
SPORT = re.compile(r"Yale University (.+?) (?:vs\.?|at) ", re.IGNORECASE)
OPPONENT_CLEANUP = re.compile(r"^(University of |The )", re.IGNORECASE)

# yalebulldogs.com doesn't send its full certificate chain; Windows' trust store can
# complete it. Certificates are still fully verified.
_TLS = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
_cache: dict = {"at": 0.0, "board": None}
_lock = threading.Lock()
logger = logging.getLogger("uvicorn.error")


class GameResult(BaseModel):
    date: str
    sport: str
    opponent: str
    home: bool
    outcome: str  # W, L, or T
    yale_score: int
    opponent_score: int


class UpcomingGame(BaseModel):
    date: str
    time: str | None
    sport: str
    opponent: str
    home: bool


class Scoreboard(BaseModel):
    results: list[GameResult]
    upcoming: list[UpcomingGame]
    updated_at: str | None
    source: str
    available: bool


def _parse_feed(xml_text: str) -> Scoreboard:
    root = ET.fromstring(xml_text)
    results: list[GameResult] = []
    upcoming: list[UpcomingGame] = []
    now = datetime.now().isoformat()

    for item in root.findall("channel/item"):
        title = item.findtext("title") or ""
        # The feed separates lines with a literal "\n" (backslash + n), not real newlines.
        description = (item.findtext("description") or "").replace("\\n", "\n")
        start = (item.findtext(f"{SIDEARM}localstartdate") or "")[:19]
        sport_match = SPORT.search(title)
        opponent = OPPONENT_CLEANUP.sub("", (item.findtext(f"{SIDEARM}opponent") or "").strip())
        if not sport_match or not opponent or not start:
            continue
        sport = sport_match.group(1).strip()
        home = " vs" in title.split(sport, 1)[-1][:5]
        if opponent.lower().startswith("yale"):
            # Events Yale hosts list Yale itself as the "opponent".
            opponent, home = "Yale-hosted event", True
        result = RESULT_LINE.search(description)
        if result:
            outcome, yale, them = result.groups()
            results.append(GameResult(date=start[:10], sport=sport, opponent=opponent, home=home,
                                      outcome=outcome, yale_score=int(yale), opponent_score=int(them)))
        elif start >= now[: len(start)]:
            upcoming.append(UpcomingGame(date=start[:10], time=start[11:16] or None, sport=sport,
                                         opponent=opponent, home=home))

    results.sort(key=lambda g: g.date, reverse=True)
    upcoming.sort(key=lambda g: (g.date, g.time or ""))
    return Scoreboard(results=results[:MAX_RESULTS], upcoming=upcoming[:MAX_UPCOMING],
                      updated_at=datetime.now().strftime("%Y-%m-%d %H:%M"), source=SOURCE_URL, available=True)


def get_scoreboard() -> Scoreboard:
    with _lock:
        board = _cache["board"]
        if board is not None and time.monotonic() - _cache["at"] < CACHE_SECONDS:
            return board
        try:
            req = urllib.request.Request(FEED_URL, headers={"User-Agent": "CampusCustoms/1.0"})
            with urllib.request.urlopen(req, timeout=10, context=_TLS) as resp:
                board = _parse_feed(resp.read().decode("utf-8", errors="replace"))
            _cache.update(at=time.monotonic(), board=board)
        except Exception as exc:
            logger.warning("scores feed failed: %s: %s", type(exc).__name__, exc)
            _cache["at"] = time.monotonic() - CACHE_SECONDS + 60  # try again in a minute
            if board is None:
                return Scoreboard(results=[], upcoming=[], updated_at=None, source=SOURCE_URL, available=False)
        return board
