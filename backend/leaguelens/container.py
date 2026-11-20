"""Wires concrete dependencies. Tests build their own ``Container`` with fakes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from leaguelens.cache import DbCache
from leaguelens.clients.sleeper import (
    FixtureSleeperClient,
    HttpSleeperClient,
    RoutingSleeperClient,
    SleeperClient,
)
from leaguelens.config import Settings
from leaguelens.db import Base, make_engine, make_session_factory
from leaguelens.services.valuation import ValuesMemo

DEMO_DATA_DIR = Path(__file__).parent / "demo_data"


@dataclass
class Container:
    sleeper: SleeperClient
    session_factory: sessionmaker[Session]
    engine: Engine
    values_memo: ValuesMemo = field(default_factory=ValuesMemo)


def build_container(settings: Settings) -> Container:
    engine = make_engine(settings.database_url)
    # Alembic owns the schema in Docker/prod; create_all keeps zero-setup local dev working.
    Base.metadata.create_all(engine)
    sf = make_session_factory(engine)
    live = HttpSleeperClient(
        DbCache(sf), base_url=settings.sleeper_base_url, max_rps=settings.sleeper_max_rps
    )
    sleeper = RoutingSleeperClient(live=live, demo=FixtureSleeperClient(DEMO_DATA_DIR))
    return Container(sleeper=sleeper, session_factory=sf, engine=engine)
