import asyncio
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def event_loop() -> Generator:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_remote_host() -> str:
    return "192.168.1.1"


@pytest.fixture
def sample_remote_port() -> int:
    return 8080


@pytest.fixture
def sample_client_id() -> int:
    return 1


@pytest.fixture
def mock_socket() -> MagicMock:
    with patch("pwnatpy.socket.socket") as mock:
        yield mock


@pytest.fixture
def sample_message_payload() -> bytes:
    return b"test data"
