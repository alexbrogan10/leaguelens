"""Client for nflverse public data releases (https://github.com/nflverse/nflverse-data).

Only release CSV files are used; no scraping. ``StatsSource`` is the interface the jobs
depend on. ``HttpNflverseSource`` downloads files; ``FixtureStatsSource`` reads local CSVs.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Protocol

import httpx

Row = dict[str, str]


class StatsSource(Protocol):
    def weekly_player_stats(self, season: int) -> list[Row]: ...

    def snap_counts(self, season: int) -> list[Row]: ...

    def players(self) -> list[Row]: ...

    def schedules(self) -> list[Row]: ...


FILES = {
    "stats": "stats_player/stats_player_week_{season}.csv",
    "snaps": "snap_counts/snap_counts_{season}.csv",
    "players": "players/players.csv",
    "schedules": "schedules/games.csv",
}


class NflverseError(Exception):
    pass


def parse_csv(text: str) -> list[Row]:
    return list(csv.DictReader(io.StringIO(text)))


class HttpNflverseSource:
    def __init__(
        self,
        base_url: str = "https://github.com/nflverse/nflverse-data/releases/download",
        http: httpx.Client | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._http = http or httpx.Client(
            timeout=httpx.Timeout(60.0),
            follow_redirects=True,
            headers={"User-Agent": "LeagueLens/0.1"},
        )

    def _fetch(self, name: str, season: int | None = None) -> list[Row]:
        path = FILES[name].format(season=season)
        try:
            resp = self._http.get(f"{self._base}/{path}")
        except httpx.HTTPError as exc:
            raise NflverseError(f"Could not download {path}: {exc}") from exc
        if resp.status_code == 404:
            return []  # e.g. a season that hasn't started
        if resp.status_code >= 400:
            raise NflverseError(f"Downloading {path} failed with HTTP {resp.status_code}")
        return parse_csv(resp.text)

    def weekly_player_stats(self, season: int) -> list[Row]:
        return self._fetch("stats", season)

    def snap_counts(self, season: int) -> list[Row]:
        return self._fetch("snaps", season)

    def players(self) -> list[Row]:
        return self._fetch("players")

    def schedules(self) -> list[Row]:
        return self._fetch("schedules")


class FixtureStatsSource:
    """Reads ``<root>/<file path>`` using the same layout as the release URLs."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _read(self, name: str, season: int | None = None) -> list[Row]:
        file = self.root / FILES[name].format(season=season)
        return parse_csv(file.read_text()) if file.is_file() else []

    def weekly_player_stats(self, season: int) -> list[Row]:
        return self._read("stats", season)

    def snap_counts(self, season: int) -> list[Row]:
        return self._read("snaps", season)

    def players(self) -> list[Row]:
        return self._read("players")

    def schedules(self) -> list[Row]:
        return self._read("schedules")
