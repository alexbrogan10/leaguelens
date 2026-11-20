"""Database tables.

League data (rosters, matchups, ...) is not normalised into tables: it is small, owned
by Sleeper and changes weekly, so it lives in ``http_cache``. Large, slow-changing data
(the player universe and nflverse weekly stats) gets real tables.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from leaguelens.db import Base


class HttpCache(Base):
    __tablename__ = "http_cache"

    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    body: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # NULL means the entry never expires (e.g. a completed past season).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Player(Base):
    __tablename__ = "players"

    sleeper_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    gsis_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(128))
    position: Mapped[str | None] = mapped_column(String(8), index=True, nullable=True)
    fantasy_positions: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    team: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    injury_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    years_exp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlayerWeekStat(Base):
    """One row per player per regular-season week, from nflverse ``stats_player``."""

    __tablename__ = "player_week_stats"

    gsis_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    week: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    team: Mapped[str | None] = mapped_column(String(8), nullable=True)
    position: Mapped[str | None] = mapped_column(String(8), nullable=True)

    pass_att: Mapped[float] = mapped_column(Float, default=0)
    pass_cmp: Mapped[float] = mapped_column(Float, default=0)
    pass_yd: Mapped[float] = mapped_column(Float, default=0)
    pass_td: Mapped[float] = mapped_column(Float, default=0)
    pass_int: Mapped[float] = mapped_column(Float, default=0)
    pass_2pt: Mapped[float] = mapped_column(Float, default=0)
    carries: Mapped[float] = mapped_column(Float, default=0)
    rush_yd: Mapped[float] = mapped_column(Float, default=0)
    rush_td: Mapped[float] = mapped_column(Float, default=0)
    rush_2pt: Mapped[float] = mapped_column(Float, default=0)
    targets: Mapped[float] = mapped_column(Float, default=0)
    receptions: Mapped[float] = mapped_column(Float, default=0)
    rec_yd: Mapped[float] = mapped_column(Float, default=0)
    rec_td: Mapped[float] = mapped_column(Float, default=0)
    rec_2pt: Mapped[float] = mapped_column(Float, default=0)
    fum_lost: Mapped[float] = mapped_column(Float, default=0)
    air_yards: Mapped[float] = mapped_column(Float, default=0)
    target_share: Mapped[float] = mapped_column(Float, default=0)
    air_yards_share: Mapped[float] = mapped_column(Float, default=0)
    wopr: Mapped[float] = mapped_column(Float, default=0)
    team_carries: Mapped[float] = mapped_column(Float, default=0)
    snap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job: Mapped[str] = mapped_column(String(64), index=True)
    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    rows: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class NflGame(Base):
    """Regular-season schedule, used to find bye weeks and remaining games."""

    __tablename__ = "nfl_games"

    game_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    week: Mapped[int] = mapped_column(Integer)
    home_team: Mapped[str] = mapped_column(String(8))
    away_team: Mapped[str] = mapped_column(String(8))
