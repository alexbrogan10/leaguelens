"""Client for Sleeper's public, read-only API (https://docs.sleeper.com).

Everything goes through ``SleeperClient._get``, which subclasses implement:

* ``HttpSleeperClient`` - real HTTP with caching and client-side rate limiting.
* ``FixtureSleeperClient`` - reads recorded JSON from disk; used by tests and the demo league.
* ``RoutingSleeperClient`` - sends demo IDs to fixtures and everything else to HTTP.
"""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx

from leaguelens.cache import Cache
from leaguelens.clients.ratelimit import TokenBucket

JSON = Any

# Cache lifetimes. ``None`` means the response is final and never expires.
TTL_STATE = timedelta(minutes=5)
TTL_USER = timedelta(hours=1)
TTL_LEAGUE = timedelta(minutes=10)
TTL_LIVE_WEEK = timedelta(minutes=5)
TTL_PLAYERS = timedelta(hours=24)  # Sleeper asks callers to fetch /players at most daily


class SleeperError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class SleeperClient(ABC):
    @abstractmethod
    def _get(self, path: str, ttl: timedelta | None) -> JSON:
        """Return parsed JSON for ``path`` (no leading slash), or ``None`` if not found."""

    # --- typed accessors -------------------------------------------------------------
    def get_state(self) -> dict[str, Any]:
        state = self._get("state/nfl", TTL_STATE)
        if not isinstance(state, dict):
            raise SleeperError("Sleeper returned no NFL state")
        return state

    def get_user(self, username_or_id: str) -> dict[str, Any] | None:
        user = self._get(f"user/{username_or_id}", TTL_USER)
        return user if isinstance(user, dict) else None

    def get_user_leagues(self, user_id: str, season: str) -> list[dict[str, Any]]:
        return self._list(f"user/{user_id}/leagues/nfl/{season}", TTL_LEAGUE)

    def get_league(self, league_id: str) -> dict[str, Any] | None:
        league = self._get(f"league/{league_id}", TTL_LEAGUE)
        return league if isinstance(league, dict) else None

    def get_league_users(self, league_id: str, final: bool = False) -> list[dict[str, Any]]:
        return self._list(f"league/{league_id}/users", None if final else TTL_LEAGUE)

    def get_rosters(self, league_id: str, final: bool = False) -> list[dict[str, Any]]:
        return self._list(f"league/{league_id}/rosters", None if final else TTL_LEAGUE)

    def get_matchups(self, league_id: str, week: int, final: bool = False) -> list[dict[str, Any]]:
        return self._list(f"league/{league_id}/matchups/{week}", None if final else TTL_LIVE_WEEK)

    def get_transactions(
        self, league_id: str, week: int, final: bool = False
    ) -> list[dict[str, Any]]:
        return self._list(f"league/{league_id}/transactions/{week}", None if final else TTL_LEAGUE)

    def get_winners_bracket(self, league_id: str, final: bool = False) -> list[dict[str, Any]]:
        return self._list(f"league/{league_id}/winners_bracket", None if final else TTL_LEAGUE)

    def get_players(self) -> dict[str, dict[str, Any]]:
        players = self._get("players/nfl", TTL_PLAYERS)
        return players if isinstance(players, dict) else {}

    def _list(self, path: str, ttl: timedelta | None) -> list[dict[str, Any]]:
        data = self._get(path, ttl)
        return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


class HttpSleeperClient(SleeperClient):
    def __init__(
        self,
        cache: Cache,
        base_url: str = "https://api.sleeper.app/v1",
        max_rps: float = 10.0,
        http: httpx.Client | None = None,
        max_concurrency: int = 4,
    ) -> None:
        self._cache = cache
        self._base = base_url.rstrip("/")
        self._bucket = TokenBucket(max_rps)
        self._sem = threading.BoundedSemaphore(max_concurrency)
        self._http = http or httpx.Client(
            timeout=httpx.Timeout(20.0), headers={"User-Agent": "LeagueLens/0.1"}
        )

    def _get(self, path: str, ttl: timedelta | None) -> JSON:
        key = f"sleeper:{path}"
        cached = self._cache.get(key)
        if cached is not None:
            return json.loads(cached)

        with self._sem:
            self._bucket.acquire()
            try:
                resp = self._http.get(f"{self._base}/{path}")
            except httpx.HTTPError as exc:
                raise SleeperError(f"Could not reach Sleeper: {exc}") from exc
        if resp.status_code == 404:
            return None
        if resp.status_code == 429:
            raise SleeperError("Sleeper rate limit hit; try again shortly", 429)
        if resp.status_code >= 400:
            raise SleeperError(f"Sleeper returned HTTP {resp.status_code}", resp.status_code)

        text = resp.text
        data = json.loads(text) if text else None
        # Don't cache "not found" (null) answers for long: a username might be created later.
        self._cache.set(key, text or "null", TTL_STATE if data is None else ttl, source="sleeper")
        return data


class FixtureSleeperClient(SleeperClient):
    """Serves ``<root>/<path>.json``. Missing files behave like Sleeper's empty answers."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _get(self, path: str, ttl: timedelta | None) -> JSON:
        file = self.root / f"{path}.json"
        if not file.is_file():
            return None
        return json.loads(file.read_text())


class RoutingSleeperClient(SleeperClient):
    """Routes requests mentioning a demo ID (prefix ``demo``) to fixtures."""

    def __init__(self, live: SleeperClient, demo: SleeperClient, prefix: str = "demo") -> None:
        self._live = live
        self._demo = demo
        self._prefix = prefix

    def _get(self, path: str, ttl: timedelta | None) -> JSON:
        parts = path.split("/")
        if len(parts) > 1 and parts[1].startswith(self._prefix):
            return self._demo._get(path, ttl)
        return self._live._get(path, ttl)
