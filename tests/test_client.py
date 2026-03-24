import time

import pytest

from pwnatpy.client import (
    CLIENT_MAX_RESEND,
    CLIENT_TIMEOUT,
    KEEP_ALIVE_SECS,
    KEEP_ALIVE_TIMEOUT_SECS,
    ClientManager,
    ClientState,
    ClientStateType,
)


class TestClientState:
    def test_initial_state(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
        )
        assert client.client_id == 1
        assert client.remote_host == "192.168.1.1"
        assert client.remote_port == 8080
        assert client.state_udp_to_tcp == ClientStateType.CLIENT_WAIT_HELLO
        assert client.state_tcp_to_udp == ClientStateType.CLIENT_WAIT_DATA0
        assert client.connected is False

    def test_with_public_address(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
            public_ip="203.0.113.1",
            public_port=2222,
        )
        assert client.public_ip == "203.0.113.1"
        assert client.public_port == 2222

    def test_is_expired_false_fresh(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
        )
        assert client.is_expired() is False

    def test_is_expired_true(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
        )
        client.last_activity = time.time() - KEEP_ALIVE_TIMEOUT_SECS - 10
        assert client.is_expired() is True

    def test_is_expired_custom_timeout(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
        )
        client.last_activity = time.time() - 10
        assert client.is_expired(timeout=5) is True

    def test_should_resend_true(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
        )
        client.last_activity = time.time() - CLIENT_TIMEOUT - 0.1
        assert client.should_resend() is True

    def test_should_resend_false_max_resend(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
        )
        client.resend_count = CLIENT_MAX_RESEND
        assert client.should_resend() is False

    def test_increment_resend(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
        )
        assert client.resend_count == 0
        client.increment_resend()
        assert client.resend_count == 1
        client.increment_resend()
        assert client.resend_count == 2

    def test_reset_resend(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
        )
        client.resend_count = 5
        old_activity = client.last_activity
        client.reset_resend()
        assert client.resend_count == 0
        assert client.last_activity >= old_activity

    def test_update_activity(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
        )
        old_time = client.last_activity
        time.sleep(0.01)
        client.update_activity()
        assert client.last_activity > old_time

    def test_set_connected(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
        )
        client.set_connected()
        assert client.connected is True
        assert client.state_udp_to_tcp == ClientStateType.CLIENT_CONNECTED

    def test_get_next_seq_alternates(self) -> None:
        client = ClientState(
            client_id=1,
            remote_host="192.168.1.1",
            remote_port=8080,
        )
        assert client.get_next_seq() == 1
        client.last_seq_sent = 0
        assert client.get_next_seq() == 1
        client.last_seq_sent = 1
        assert client.get_next_seq() == 0


@pytest.mark.asyncio
class TestClientManager:
    async def test_add_client(self) -> None:
        manager = ClientManager()
        client = await manager.add_client("192.168.1.1", 8080)
        assert client.client_id == 1
        assert client.remote_host == "192.168.1.1"
        assert client.remote_port == 8080

    async def test_add_multiple_clients(self) -> None:
        manager = ClientManager()
        client1 = await manager.add_client("192.168.1.1", 8080)
        client2 = await manager.add_client("192.168.1.2", 8081)
        assert client1.client_id == 1
        assert client2.client_id == 2

    async def test_get_client_exists(self) -> None:
        manager = ClientManager()
        added = await manager.add_client("192.168.1.1", 8080)
        retrieved = await manager.get_client(1)
        assert retrieved is not None
        assert retrieved.client_id == added.client_id

    async def test_get_client_not_exists(self) -> None:
        manager = ClientManager()
        await manager.add_client("192.168.1.1", 8080)
        retrieved = await manager.get_client(999)
        assert retrieved is None

    async def test_remove_client(self) -> None:
        manager = ClientManager()
        await manager.add_client("192.168.1.1", 8080)
        await manager.remove_client(1)
        retrieved = await manager.get_client(1)
        assert retrieved is None

    async def test_remove_nonexistent_client(self) -> None:
        manager = ClientManager()
        await manager.remove_client(999)

    async def test_get_all_clients(self) -> None:
        manager = ClientManager()
        await manager.add_client("192.168.1.1", 8080)
        await manager.add_client("192.168.1.2", 8081)
        clients = await manager.get_all_clients()
        assert len(clients) == 2

    async def test_cleanup_expired(self) -> None:
        manager = ClientManager()
        client = await manager.add_client("192.168.1.1", 8080)
        client.last_activity = time.time() - KEEP_ALIVE_TIMEOUT_SECS - 10
        expired = await manager.cleanup_expired()
        assert 1 in expired
        assert await manager.get_client(1) is None

    async def test_cleanup_none_expired(self) -> None:
        manager = ClientManager()
        await manager.add_client("192.168.1.1", 8080)
        expired = await manager.cleanup_expired()
        assert len(expired) == 0

    async def test_client_with_public_info(self) -> None:
        manager = ClientManager()
        client = await manager.add_client(
            remote_host="192.168.1.1",
            remote_port=8080,
            public_ip="203.0.113.1",
            public_port=2222,
        )
        assert client.public_ip == "203.0.113.1"
        assert client.public_port == 2222


class TestConstants:
    def test_timeout_constants(self) -> None:
        assert CLIENT_TIMEOUT == 1.0
        assert CLIENT_MAX_RESEND == 10
        assert KEEP_ALIVE_SECS == 60
        assert KEEP_ALIVE_TIMEOUT_SECS == 421
