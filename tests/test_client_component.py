import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pwnatpy.client_component import (
    _handle_udp_message,
    _send_periodic_icmp,
    _wait_for_tunnel,
    pwnat_client,
)


class TestPeriodicICMP:
    @pytest.mark.asyncio
    async def test_send_periodic_icmp_cancels(self) -> None:
        mock_sock = MagicMock()
        mock_sock.sendto = AsyncMock()

        with patch("pwnatpy.client_component.ICMPHandler") as mock_handler:
            mock_handler_instance = MagicMock()
            mock_handler_instance.send_time_exceeded = MagicMock()
            mock_handler.return_value = mock_handler_instance

            task = asyncio.create_task(_send_periodic_icmp(mock_sock, "3.3.3.1", 1))
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


class TestWaitForTunnel:
    @pytest.mark.asyncio
    async def test_tunnel_established(self) -> None:
        mock_udp_sock = MagicMock()
        mock_udp_sock.recvfrom = AsyncMock(
            return_value=(b"\x00\x00\x00\x00", ("3.3.3.1", 2222))
        )

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.sock_recvfrom = AsyncMock(
                return_value=(b"\x00\x00\x00\x00", ("3.3.3.1", 2222))
            )

            from pwnatpy.client import ClientManager

            manager = ClientManager()
            client = await manager.add_client("192.168.1.1", 8080)

            result = await _wait_for_tunnel(
                mock_udp_sock,
                ("3.3.3.1", 2222),
                client,
                verbose=False,
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_tunnel_timeout(self) -> None:
        mock_udp_sock = MagicMock()

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.sock_recvfrom = AsyncMock(side_effect=TimeoutError())

            from pwnatpy.client import ClientManager

            manager = ClientManager()
            client = await manager.add_client("192.168.1.1", 8080)

            result = await _wait_for_tunnel(
                mock_udp_sock,
                ("3.3.3.1", 2222),
                client,
                verbose=False,
            )
            assert result is False


class TestHandleUDPMessage:
    @pytest.mark.asyncio
    async def test_handle_helloack(self) -> None:
        mock_udp_sock = MagicMock()

        from pwnatpy.client import ClientManager
        from pwnatpy.message import MessageType, ProtocolMessage

        manager = ClientManager()
        client = await manager.add_client("192.168.1.1", 8080)

        helloack = ProtocolMessage(client.client_id, MessageType.HELLOACK, b"")
        await _handle_udp_message(
            helloack.to_bytes(),
            ("3.3.3.1", 2222),
            mock_udp_sock,
            client,
            verbose=False,
        )
        assert client.connected is True


class TestPwnatClient:
    @pytest.mark.asyncio
    async def test_client_initialization(self) -> None:
        with patch("pwnatpy.client_component.socket.socket") as mock_sock:
            mock_tcp = MagicMock()
            mock_udp = MagicMock()

            mock_tcp.accept = AsyncMock(side_effect=TimeoutError())
            mock_udp.recvfrom = AsyncMock(side_effect=TimeoutError())

            def create_sock(*args: object) -> MagicMock:
                if args[1] == socket.SOCK_STREAM:
                    return mock_tcp
                return mock_udp

            mock_sock.side_effect = create_sock

            with patch("pwnatpy.client_component.ICMPHandler"):
                try:
                    await asyncio.wait_for(
                        pwnat_client(
                            local_ip="127.0.0.1",
                            local_port=0,
                            remote_host="127.0.0.1",
                            remote_port=22,
                        ),
                        timeout=0.1,
                    )
                except TimeoutError:
                    pass
                except Exception:
                    pass
