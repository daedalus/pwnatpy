import asyncio
import socket
import time
from dataclasses import dataclass, field
from enum import IntEnum

CLIENT_TIMEOUT = 1.0
CLIENT_MAX_RESEND = 10
KEEP_ALIVE_SECS = 60
KEEP_ALIVE_TIMEOUT_SECS = 421


class ClientStateType(IntEnum):
    CLIENT_WAIT_HELLO = 0
    CLIENT_WAIT_DATA0 = 1
    CLIENT_WAIT_DATA1 = 2
    CLIENT_WAIT_ACK0 = 3
    CLIENT_WAIT_ACK1 = 4
    CLIENT_CONNECTED = 5


class ClientStateDirection(IntEnum):
    UDP_TO_TCP = 0
    TCP_TO_UDP = 1


@dataclass
class ClientState:
    client_id: int
    remote_host: str
    remote_port: int
    public_ip: str = ""
    public_port: int = 0
    local_ip: str = ""
    local_port: int = 0
    state_udp_to_tcp: ClientStateType = ClientStateType.CLIENT_WAIT_HELLO
    state_tcp_to_udp: ClientStateType = ClientStateType.CLIENT_WAIT_DATA0
    last_seq_sent: int = 0
    last_seq_recv: int = 0
    resend_count: int = 0
    last_activity: float = field(default_factory=time.time)
    tcp_socket: socket.socket | None = None
    udp_socket: socket.socket | None = None
    connected: bool = False

    def is_expired(self, timeout: float = KEEP_ALIVE_TIMEOUT_SECS) -> bool:
        return (time.time() - self.last_activity) > timeout

    def should_resend(self) -> bool:
        if self.resend_count >= CLIENT_MAX_RESEND:
            return False
        return (time.time() - self.last_activity) > CLIENT_TIMEOUT

    def increment_resend(self) -> int:
        self.resend_count += 1
        return self.resend_count

    def reset_resend(self) -> None:
        self.resend_count = 0
        self.last_activity = time.time()

    def update_activity(self) -> None:
        self.last_activity = time.time()

    def set_connected(self) -> None:
        self.connected = True
        self.state_udp_to_tcp = ClientStateType.CLIENT_CONNECTED

    def get_next_seq(self) -> int:
        return 1 - self.last_seq_sent


class ClientManager:
    def __init__(self) -> None:
        self._clients: dict[int, ClientState] = {}
        self._next_client_id: int = 1
        self._lock = asyncio.Lock()

    async def add_client(
        self,
        remote_host: str,
        remote_port: int,
        public_ip: str = "",
        public_port: int = 0,
    ) -> ClientState:
        async with self._lock:
            client_id = self._next_client_id
            self._next_client_id += 1
            client = ClientState(
                client_id=client_id,
                remote_host=remote_host,
                remote_port=remote_port,
                public_ip=public_ip,
                public_port=public_port,
            )
            self._clients[client_id] = client
            return client

    async def get_client(self, client_id: int) -> ClientState | None:
        async with self._lock:
            return self._clients.get(client_id)

    async def remove_client(self, client_id: int) -> None:
        async with self._lock:
            if client_id in self._clients:
                client = self._clients[client_id]
                if client.tcp_socket:
                    try:
                        client.tcp_socket.close()
                    except Exception:
                        pass
                if client.udp_socket:
                    try:
                        client.udp_socket.close()
                    except Exception:
                        pass
                del self._clients[client_id]

    async def get_all_clients(self) -> list[ClientState]:
        async with self._lock:
            return list(self._clients.values())

    async def cleanup_expired(self) -> list[int]:
        expired_ids = []
        async with self._lock:
            for client_id, client in list(self._clients.items()):
                if client.is_expired():
                    expired_ids.append(client_id)
        for client_id in expired_ids:
            await self.remove_client(client_id)
        return expired_ids
