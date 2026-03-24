import asyncio
import logging
import socket

from .client import ClientManager, ClientState
from .message import (
    MessageBuilder,
    MessageType,
    decode_message,
)
from .packet import ICMPHandler

logger = logging.getLogger(__name__)

FAKE_DESTINATION = "3.3.3.3"
DEFAULT_PROXY_PORT = 2222
DEFAULT_PROXY_HOST = "3.3.3.1"


async def pwnat_client(
    local_ip: str = "127.0.0.1",
    local_port: int = 0,
    proxy_host: str = DEFAULT_PROXY_HOST,
    proxy_port: int = DEFAULT_PROXY_PORT,
    remote_host: str = "127.0.0.1",
    remote_port: int = 22,
    reuse_addr: bool = False,
    reuse_port: bool = False,
    verbose: bool = False,
) -> None:
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    client_manager = ClientManager()

    tcp_server_sock = socket.socket(
        socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP
    )
    if reuse_addr:
        tcp_server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if reuse_port:
        tcp_server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    tcp_server_sock.bind((local_ip, local_port))
    tcp_server_sock.listen(5)
    tcp_server_sock.setblocking(False)

    client = await client_manager.add_client(
        remote_host=remote_host,
        remote_port=remote_port,
    )

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_sock.setblocking(False)

    icmp_handler = ICMPHandler()
    icmp_sock = icmp_handler.create_send_socket()

    icmp_task = asyncio.create_task(
        _send_periodic_icmp(icmp_sock, proxy_host, client.client_id)
    )

    tunnel_established = await _wait_for_tunnel(
        udp_sock,
        (proxy_host, proxy_port),
        client,
        verbose,
    )

    if not tunnel_established:
        logger.error("Failed to establish tunnel")
        return

    hello = MessageBuilder.build_hello(
        client.client_id,
        remote_host,
        remote_port,
    )
    await asyncio.get_event_loop().sock_sendto(
        udp_sock, hello.to_bytes(), (proxy_host, proxy_port)
    )

    try:
        while True:
            try:
                tcp_client, tcp_addr = await asyncio.wait_for(
                    asyncio.get_event_loop().sock_accept(tcp_server_sock),
                    timeout=1.0,
                )
                asyncio.create_task(
                    _handle_tcp_connection(
                        tcp_client,
                        udp_sock,
                        (proxy_host, proxy_port),
                        client,
                        verbose,
                    )
                )
            except TimeoutError:
                pass

            try:
                data, addr = await asyncio.wait_for(
                    asyncio.get_event_loop().sock_recvfrom(udp_sock, 2048),
                    timeout=0.5,
                )
                await _handle_udp_message(
                    data,
                    addr,
                    udp_sock,
                    client,
                    verbose,
                )
            except TimeoutError:
                pass

    finally:
        icmp_task.cancel()
        tcp_server_sock.close()
        udp_sock.close()
        icmp_sock.close()


async def _send_periodic_icmp(
    sock: socket.socket,
    destination: str,
    client_id: int,
) -> None:
    seq = 0
    while True:
        try:
            await asyncio.sleep(5)
            icmp_handler = ICMPHandler()
            icmp_handler.send_time_exceeded(
                sock,
                destination,
                b"PWNAT",
                identifier=client_id,
                seq=seq,
            )
            seq = (seq + 1) % 65535
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"ICMP send error: {e}")


async def _wait_for_tunnel(
    udp_sock: socket.socket,
    server_addr: tuple[str, int],
    client: ClientState,
    verbose: bool,
) -> bool:
    for _ in range(10):
        try:
            data, addr = await asyncio.wait_for(
                asyncio.get_event_loop().sock_recvfrom(udp_sock, 10),
                timeout=2.0,
            )
            if addr == server_addr and len(data) >= 4:
                client.set_connected()
                if verbose:
                    logger.info("Tunnel established")
                return True
        except TimeoutError:
            continue
    return False


async def _handle_tcp_connection(
    tcp_sock: socket.socket,
    udp_sock: socket.socket,
    server_addr: tuple[str, int],
    client: ClientState,
    verbose: bool,
) -> None:
    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    asyncio.get_event_loop().sock_recv(tcp_sock, 1024),
                    timeout=1.0,
                )
                if not data:
                    break

                seq = client.get_next_seq()
                msg = MessageBuilder.build_data(client.client_id, seq, data)
                await asyncio.get_event_loop().sock_sendto(
                    udp_sock,
                    msg.to_bytes(),
                    server_addr,
                )
                client.last_seq_sent = seq

                await _wait_for_ack(udp_sock, client, seq, verbose)

            except TimeoutError:
                break

    except Exception as e:
        if verbose:
            logger.debug(f"TCP connection error: {e}")
    finally:
        tcp_sock.close()


async def _wait_for_ack(
    udp_sock: socket.socket,
    client: ClientState,
    seq: int,
    verbose: bool = False,
) -> None:
    expected_ack = MessageType.ACK0 if seq == 0 else MessageType.ACK1
    for _ in range(3):
        try:
            data, addr = await asyncio.wait_for(
                asyncio.get_event_loop().sock_recvfrom(udp_sock, 100),
                timeout=1.0,
            )
            msg = decode_message(data)
            if msg.msg_type == expected_ack:
                client.reset_resend()
                if verbose:
                    logger.debug(f"Received ACK for seq {seq}")
                return
        except TimeoutError:
            continue
        except Exception:
            continue


async def _handle_udp_message(
    data: bytes,
    addr: tuple[str, int],
    udp_sock: socket.socket,
    client: ClientState,
    verbose: bool,
) -> None:
    try:
        msg = decode_message(data)
    except Exception:
        return

    if msg.msg_type == MessageType.HELLOACK:
        client.set_connected()
        if verbose:
            logger.info("Received HELLOACK")
        return

    if msg.msg_type in (MessageType.DATA0, MessageType.DATA1):
        seq = 0 if msg.msg_type == MessageType.DATA0 else 1
        client.last_seq_recv = seq
        client.update_activity()

        ack = MessageBuilder.build_ack(client.client_id, seq)
        await asyncio.get_event_loop().sock_sendto(
            udp_sock,
            ack.to_bytes(),
            addr,
        )

        if verbose:
            logger.debug(f"Received DATA{seq}")
