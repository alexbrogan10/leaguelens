"""Matching Sleeper players to nflverse (GSIS) player IDs.

Sleeper only fills ``gsis_id`` for a minority of players, so we fall back in order:
1. Sleeper's ``gsis_id``
2. ESPN ID, which both Sleeper and nflverse's players file carry
3. Normalised full name + position, accepted only when the match is unique
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?")
_NON_ALPHA = re.compile(r"[^a-z]")


def normalize_name(name: str) -> str:
    n = name.lower()
    n = _SUFFIX.sub("", n)
    return _NON_ALPHA.sub("", n)


class IdLinker:
    def __init__(self, nflverse_players: Iterable[Mapping[str, str]]) -> None:
        self._by_espn: dict[str, str] = {}
        by_name: dict[tuple[str, str], set[str]] = defaultdict(set)
        for row in nflverse_players:
            gsis = (row.get("gsis_id") or "").strip()
            if not gsis:
                continue
            espn = (row.get("espn_id") or "").strip()
            if espn:
                self._by_espn[espn] = gsis
            if row.get("status") == "RET":
                continue
            name = normalize_name(row.get("display_name") or "")
            if name:
                by_name[(name, row.get("position") or "")].add(gsis)
        self._by_name = {k: next(iter(v)) for k, v in by_name.items() if len(v) == 1}

    def gsis_for(self, sleeper_player: Mapping[str, Any]) -> str | None:
        gsis = str(sleeper_player.get("gsis_id") or "").strip()
        if gsis:
            return gsis
        espn = str(sleeper_player.get("espn_id") or "").strip()
        if espn and espn in self._by_espn:
            return self._by_espn[espn]
        name = normalize_name(str(sleeper_player.get("full_name") or ""))
        position = str(sleeper_player.get("position") or "")
        return self._by_name.get((name, position))


def pfr_to_gsis(nflverse_players: Iterable[Mapping[str, str]]) -> dict[str, str]:
    return {
        r["pfr_id"]: r["gsis_id"]
        for r in nflverse_players
        if (r.get("pfr_id") or "").strip() and (r.get("gsis_id") or "").strip()
    }
