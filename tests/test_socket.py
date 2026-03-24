import socket
from unittest.mock import MagicMock, patch

from pwnatpy.socket import (
    SocketConfig,
    SocketManager,
    create_raw_socket,
    create_tcp_server,
    create_udp_socket,
)


class TestSocketConfig:
    def test_default_config(self) -> None:
        config = SocketConfig()
        assert config.socket_type == socket.SOCK_STREAM
        assert config.protocol == socket.IPPROTO_TCP
        assert config.reuse_addr is False
        assert config.reuse_port is False
        assert config.blocking is True
        assert config.broadcast is False

    def test_custom_config(self) -> None:
        config = SocketConfig(
            socket_type=socket.SOCK_DGRAM,
            protocol=socket.IPPROTO_UDP,
            reuse_addr=True,
            reuse_port=True,
            blocking=False,
            broadcast=True,
        )
        assert config.socket_type == socket.SOCK_DGRAM
        assert config.protocol == socket.IPPROTO_UDP
        assert config.reuse_addr is True
        assert config.reuse_port is True
        assert config.blocking is False
        assert config.broadcast is True


class TestSocketManager:
    def test_create_tcp_socket(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            manager = SocketManager()
            sock = manager.create()
            assert sock == mock_sock

    def test_create_udp_socket(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            manager = SocketManager()
            sock = manager.create_udp()
            assert sock == mock_sock

    def test_bind(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            manager = SocketManager()
            manager.bind(("127.0.0.1", 8080))
            mock_sock.bind.assert_called_once_with(("127.0.0.1", 8080))

    def test_listen(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            manager = SocketManager()
            manager.create()
            manager.listen(10)
            mock_sock.listen.assert_called_once_with(10)

    def test_accept(self) -> None:
        mock_sock = MagicMock()
        mock_client = MagicMock()
        mock_addr = ("127.0.0.1", 12345)
        mock_sock.accept.return_value = (mock_client, mock_addr)
        with patch("socket.socket", return_value=mock_sock):
            manager = SocketManager()
            manager.create()
            client, addr = manager.accept()
            assert client == mock_client
            assert addr == mock_addr

    def test_connect(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            manager = SocketManager()
            manager.connect(("127.0.0.1", 8080))
            mock_sock.connect.assert_called_once_with(("127.0.0.1", 8080))

    def test_send(self) -> None:
        mock_sock = MagicMock()
        mock_sock.send.return_value = 10
        with patch("socket.socket", return_value=mock_sock):
            manager = SocketManager()
            manager.create()
            result = manager.send(b"test data")
            mock_sock.send.assert_called_once_with(b"test data")
            assert result == 10

    def test_recv(self) -> None:
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b"test data"
        with patch("socket.socket", return_value=mock_sock):
            manager = SocketManager()
            manager.create()
            result = manager.recv(1024)
            mock_sock.recv.assert_called_once_with(1024)
            assert result == b"test data"

    def test_close(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            manager = SocketManager()
            manager.create()
            manager.close()
            mock_sock.close.assert_called_once()

    def test_context_manager(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            with SocketManager() as manager:
                manager.create()
            mock_sock.close.assert_called_once()


class TestHelperFunctions:
    def test_create_udp_socket_default(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            sock = create_udp_socket()
            assert sock == mock_sock

    def test_create_udp_socket_with_bind(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            create_udp_socket(bind_address=("127.0.0.1", 8080))
            mock_sock.bind.assert_called_once_with(("127.0.0.1", 8080))

    def test_create_udp_socket_with_options(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            create_udp_socket(reuse_addr=True, reuse_port=True, broadcast=True)
            mock_sock.setsockopt.assert_any_call(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )
            mock_sock.setsockopt.assert_any_call(
                socket.SOL_SOCKET, socket.SO_REUSEPORT, 1
            )
            mock_sock.setsockopt.assert_any_call(
                socket.SOL_SOCKET, socket.SO_BROADCAST, 1
            )

    def test_create_tcp_server(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            create_tcp_server(("127.0.0.1", 8080))
            mock_sock.setsockopt.assert_called_once_with(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )
            mock_sock.bind.assert_called_once_with(("127.0.0.1", 8080))
            mock_sock.listen.assert_called_once_with(5)

    def test_create_raw_socket(self) -> None:
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            create_raw_socket(socket.IPPROTO_ICMP)
            mock_sock.setsockopt.assert_called_once_with(
                socket.SOL_IP, socket.IP_HDRINCL, 1
            )
