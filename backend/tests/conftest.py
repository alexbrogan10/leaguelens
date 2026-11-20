from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from leaguelens.api.main import create_app
from leaguelens.clients.sleeper import FixtureSleeperClient
from leaguelens.container import Container
from leaguelens.db import Base, make_engine, make_session_factory

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sleeper() -> FixtureSleeperClient:
    return FixtureSleeperClient(FIXTURES / "sleeper")


@pytest.fixture
def container(sleeper, tmp_path) -> Container:
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return Container(sleeper=sleeper, session_factory=make_session_factory(engine), engine=engine)


@pytest.fixture
def client(container) -> TestClient:
    return TestClient(create_app(container))
