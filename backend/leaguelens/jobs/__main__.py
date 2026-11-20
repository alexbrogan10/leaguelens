"""CLI for data jobs.

python -m leaguelens.jobs players
python -m leaguelens.jobs stats --season 2026
python -m leaguelens.jobs schedule --season 2026
python -m leaguelens.jobs all            # everything for the current season
python -m leaguelens.jobs worker         # run `all` every REFRESH_INTERVAL_MINUTES
"""

from __future__ import annotations

import argparse
import logging
import time

from leaguelens.clients.nflverse import HttpNflverseSource
from leaguelens.config import get_settings
from leaguelens.container import build_container
from leaguelens.jobs.refresh import refresh_players, refresh_schedule, refresh_stats

log = logging.getLogger("leaguelens.jobs")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="leaguelens.jobs")
    parser.add_argument("job", choices=["players", "stats", "schedule", "all", "worker"])
    parser.add_argument("--season", type=int, action="append", help="repeatable")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    settings = get_settings()
    c = build_container(settings)
    source = HttpNflverseSource(settings.nflverse_base_url)

    def seasons() -> list[int]:
        if args.season:
            return list(args.season)
        return [int(c.sleeper.get_state()["season"])]

    def run_all() -> None:
        current = seasons()
        refresh_players(c.session_factory, c.sleeper, source)
        refresh_schedule(c.session_factory, source, current)
        for season in current:
            refresh_stats(c.session_factory, source, season)

    if args.job == "players":
        refresh_players(c.session_factory, c.sleeper, source)
    elif args.job == "stats":
        for season in seasons():
            refresh_stats(c.session_factory, source, season)
    elif args.job == "schedule":
        refresh_schedule(c.session_factory, source, seasons())
    elif args.job == "all":
        run_all()
    else:
        while True:
            try:
                run_all()
            except Exception:
                log.exception("Refresh failed; will retry next interval")
            time.sleep(settings.refresh_interval_minutes * 60)


if __name__ == "__main__":
    main()
