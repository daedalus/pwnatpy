import socket
from dataclasses import dataclass


@dataclass
class SocketConfig:
    socket_type: int = socket.SOCK_STREAM
    protocol: int = socket.IPPROTO_TCP
    reuse_addr: bool = False
    reuse_port: bool = False
    blocking: bool = True
    broadcast: bool = False


class SocketManager:
    def __init__(self, config: SocketConfig | None = None) -> None:
        self._config = config or SocketConfig()
        self._sock: socket.socket | None = None
        self._family: int = socket.AF_INET

    def create(
        self,
        family: int = socket.AF_INET,
        socket_type: int = socket.SOCK_STREAM,
        protocol: int = socket.IPPROTO_TCP,
    ) -> socket.socket:
        self._family = family
        self._sock = socket.socket(family, socket_type, protocol)
        self._apply_options()
        return self._sock

    def create_udp(self, family: int = socket.AF_INET) -> socket.socket:
        return self.create(family, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    def create_raw(
        self, family: int = socket.AF_INET, protocol: int = 0
    ) -> socket.socket:
        return self.create(family, socket.SOCK_RAW, protocol)

    def _apply_options(self) -> None:
        if self._sock is None:
            return
        if self._config.reuse_addr:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self._config.reuse_port:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        if self._config.broadcast:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        if not self._config.blocking:
            self._sock.setblocking(False)

    def bind(self, address: tuple[str, int]) -> None:
        if self._sock is None:
            self.create()
        assert self._sock is not None
        self._sock.bind(address)

    def listen(self, backlog: int = 5) -> None:
        if self._sock is None:
            raise RuntimeError("Socket not created")
        self._sock.listen(backlog)

    def accept(self) -> tuple[socket.socket, tuple[str, int]]:
        if self._sock is None:
            raise RuntimeError("Socket not created")
        return self._sock.accept()

    def connect(self, address: tuple[str, int]) -> None:
        if self._sock is None:
            self.create()
        assert self._sock is not None
        self._sock.connect(address)

    def send(self, data: bytes) -> int:
        if self._sock is None:
            raise RuntimeError("Socket not created")
        return self._sock.send(data)

    def recv(self, bufsize: int = 1024) -> bytes:
        if self._sock is None:
            raise RuntimeError("Socket not created")
        return self._sock.recv(bufsize)

    def sendto(self, data: bytes, address: tuple[str, int]) -> int:
        if self._sock is None:
            self.create_udp()
        assert self._sock is not None
        return self._sock.sendto(data, address)

    def recvfrom(self, bufsize: int = 1024) -> tuple[bytes, tuple[str, int]]:
        if self._sock is None:
            raise RuntimeError("Socket not created")
        return self._sock.recvfrom(bufsize)

    def settimeout(self, timeout: float | None) -> None:
        if self._sock is None:
            raise RuntimeError("Socket not created")
        self._sock.settimeout(timeout)

    def getpeername(self) -> tuple[str, int]:
        if self._sock is None:
            raise RuntimeError("Socket not created")
        assert self._sock is not None
        name = self._sock.getpeername()
        return (name[0], name[1])

    def getsockname(self) -> tuple[str, int]:
        if self._sock is None:
            raise RuntimeError("Socket not created")
        assert self._sock is not None
        name = self._sock.getsockname()
        return (name[0], name[1])

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    @property
    def fd(self) -> int | None:
        return self._sock.fileno() if self._sock is not None else None

    @property
    def socket(self) -> socket.socket | None:
        return self._sock

    def __enter__(self) -> "SocketManager":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        self.close()


def create_udp_socket(
    bind_address: tuple[str, int] | None = None,
    reuse_addr: bool = False,
    reuse_port: bool = False,
    broadcast: bool = False,
) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    if reuse_addr:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if reuse_port:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    if broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    if bind_address:
        sock.bind(bind_address)
    return sock


def create_tcp_server(
    bind_address: tuple[str, int],
    backlog: int = 5,
    reuse_addr: bool = True,
) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    if reuse_addr:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(bind_address)
    sock.listen(backlog)
    return sock


def create_raw_socket(protocol: int = socket.IPPROTO_ICMP) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, protocol)
    sock.setsockopt(socket.SOL_IP, socket.IP_HDRINCL, 1)
    return sock
