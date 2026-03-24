import asyncio
import logging
import socket
import struct

from .client import ClientManager, ClientState
from .message import (
    MessageBuilder,
    MessageType,
    decode_message,
)
from .packet import ICMP_TIME_EXCEEDED, ICMPHandler, ip_int_to_string

logger = logging.getLogger(__name__)

FAKE_DESTINATION = "3.3.3.3"
DEFAULT_PROXY_PORT = 2222


class DestinationFilter:
    def __init__(self, allowed_destinations: list[str] | None = None) -> None:
        self._allowed: list[tuple[str | None, int | None]] = []
        if allowed_destinations:
            for dest in allowed_destinations:
                self._parse_destination(dest)

    def _parse_destination(self, dest: str) -> tuple[str | None, int | None]:
        host: str | None = None
        port: int | None = None
        if ":" in dest:
            host_part, port_part = dest.rsplit(":", 1)
            if host_part:
                host = host_part
            try:
                port = int(port_part)
            except ValueError:
                pass
        elif dest:
            host = dest
        self._allowed.append((host, port))
        return (host, port)

    def is_allowed(self, host: str, port: int) -> bool:
        if not self._allowed:
            return True
        for allowed_host, allowed_port in self._allowed:
            if allowed_host and allowed_host != host:
                continue
            if allowed_port and allowed_port != port:
                continue
            return True
        return False


async def pwnat_server(
    bind_ip: str = "0.0.0.0",
    proxy_port: int = DEFAULT_PROXY_PORT,
    allowed_destinations: list[str] | None = None,
    reuse_addr: bool = False,
    reuse_port: bool = False,
    verbose: bool = False,
) -> None:
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    destination_filter = DestinationFilter(allowed_destinations)
    client_manager = ClientManager()

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    if reuse_addr:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if reuse_port:
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    udp_sock.bind((bind_ip, proxy_port))
    udp_sock.setblocking(False)

    icmp_handler = ICMPHandler()
    icmp_send_sock = icmp_handler.create_send_socket()
    icmp_listen_sock = icmp_handler.create_listen_socket()
    icmp_listen_sock.setblocking(False)

    keepalive_task = asyncio.create_task(
        _send_periodic_icmp(icmp_send_sock, FAKE_DESTINATION)
    )

    cleanup_task = asyncio.create_task(_periodic_cleanup(client_manager))

    loop = asyncio.get_event_loop()
    try:
        while True:
            try:
                async with asyncio.timeout(1.0):
                    data, addr = await loop.sock_recvfrom(udp_sock, 2048)
                await _handle_udp_message(
                    data,
                    addr,
                    udp_sock,
                    client_manager,
                    destination_filter,
                    verbose,
                )
            except TimeoutError:
                pass
            except TimeoutError:
                pass

            try:
                async with asyncio.timeout(0.1):
                    icmp_data, icmp_addr = await loop.sock_recvfrom(
                        icmp_listen_sock, 2048
                    )
                await _handle_icmp_message(
                    icmp_data,
                    icmp_addr,
                    udp_sock,
                    client_manager,
                    verbose,
                )
            except TimeoutError:
                pass
            except TimeoutError:
                pass

    finally:
        keepalive_task.cancel()
        cleanup_task.cancel()
        udp_sock.close()
        icmp_send_sock.close()
        icmp_listen_sock.close()


async def _send_periodic_icmp(sock: socket.socket, destination: str) -> None:
    seq = 0
    while True:
        try:
            await asyncio.sleep(5)
            icmp_handler = ICMPHandler()
            icmp_handler.send_echo_request(sock, destination, seq=seq)
            seq = (seq + 1) % 65535
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"ICMP send error: {e}")


async def _periodic_cleanup(client_manager: ClientManager) -> None:
    while True:
        try:
            await asyncio.sleep(30)
            await client_manager.cleanup_expired()
        except asyncio.CancelledError:
            break


async def _handle_udp_message(
    data: bytes,
    addr: tuple[str, int],
    udp_sock: socket.socket,
    client_manager: ClientManager,
    destination_filter: DestinationFilter,
    verbose: bool,
) -> None:
    try:
        msg = decode_message(data)
    except Exception as e:
        if verbose:
            logger.debug(f"Failed to decode message: {e}")
        return

    client = await client_manager.get_client(msg.client_id)
    if not client:
        if verbose:
            logger.debug(f"Unknown client ID: {msg.client_id}")
        return

    if msg.msg_type == MessageType.HELLO:
        try:
            remote_host, remote_port = MessageBuilder.parse_hello_payload(msg.payload)
            if not destination_filter.is_allowed(remote_host, remote_port):
                if verbose:
                    logger.debug(
                        f"Destination not allowed: {remote_host}:{remote_port}"
                    )
                return

            client.remote_host = remote_host
            client.remote_port = remote_port
            client.public_ip = addr[0]
            client.public_port = addr[1]
            client.set_connected()

            ack = MessageBuilder.build_hello_ack(client.client_id)
            udp_sock.sendto(ack.to_bytes(), addr)

            if verbose:
                logger.info(
                    f"Client {client.client_id} connected: {remote_host}:{remote_port}"
                )

        except Exception as e:
            if verbose:
                logger.debug(f"Error handling HELLO: {e}")

    elif msg.msg_type == MessageType.KEEPALIVE:
        client.update_activity()
        if verbose:
            logger.debug(f"Keepalive from client {client.client_id}")

    elif msg.msg_type == MessageType.GOODBYE:
        if verbose:
            logger.info(f"Client {client.client_id} disconnected")
        await client_manager.remove_client(client.client_id)

    elif msg.msg_type in (MessageType.DATA0, MessageType.DATA1):
        seq = 0 if msg.msg_type == MessageType.DATA0 else 1
        client.last_seq_recv = seq
        client.update_activity()

        ack = MessageBuilder.build_ack(client.client_id, seq)
        udp_sock.sendto(ack.to_bytes(), addr)


async def _handle_icmp_message(
    data: bytes,
    addr: tuple[str, int],
    udp_sock: socket.socket,
    client_manager: ClientManager,
    verbose: bool,
) -> None:
    del addr
    if len(data) < 28:
        return

    try:
        ip_header = data[20:]
        icmp_type = ip_header[0]

        if icmp_type != ICMP_TIME_EXCEEDED:
            return

        if len(ip_header) < 28:
            return

        original_ip = ip_header[28:]
        if len(original_ip) < 20:
            return

        src_ip_int = struct.unpack("!I", original_ip[12:16])[0]
        dst_ip_int = struct.unpack("!I", original_ip[16:20])[0]

        if ip_int_to_string(dst_ip_int) != FAKE_DESTINATION:
            return

        client_ip = ip_int_to_string(src_ip_int)

        existing = await _find_client_by_ip(client_manager, client_ip)
        if existing:
            if verbose:
                logger.debug(f"Keepalive ICMP from existing client: {client_ip}")
            return

        _ = await client_manager.add_client(
            remote_host="",
            remote_port=0,
            public_ip=client_ip,
            public_port=DEFAULT_PROXY_PORT,
        )

        udp_sock.sendto(
            b"\x00\x00\x00\x00",
            (client_ip, DEFAULT_PROXY_PORT),
        )

        if verbose:
            logger.info(f"New client detected via ICMP: {client_ip}")

    except Exception as e:
        if verbose:
            logger.debug(f"Error handling ICMP: {e}")


async def _find_client_by_ip(
    client_manager: ClientManager,
    ip: str,
) -> ClientState | None:
    clients = await client_manager.get_all_clients()
    for client in clients:
        if client.public_ip == ip:
            return client
    return None
