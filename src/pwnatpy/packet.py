import socket
import struct
from dataclasses import dataclass
from typing import NamedTuple

ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0
ICMP_TIME_EXCEEDED = 11
ICMP_DEST_UNREACHABLE = 3

FAKE_DESTINATION = "3.3.3.3"
ICMP_IDENTIFIER = 0xFFFF


class IPPacket(NamedTuple):
    vers_ihl: int
    tos: int
    pkt_len: int
    id: int
    flags_frag_offset: int
    ttl: int
    proto: int
    checksum: int
    src_ip: int
    dst_ip: int


class ICMPPacket(NamedTuple):
    type: int
    code: int
    checksum: int
    identifier: int
    seq: int


@dataclass
class RawICMPPacket:
    ip_header: bytes
    icmp_header: bytes
    payload: bytes

    @property
    def total_packet(self) -> bytes:
        return self.ip_header + self.icmp_header + self.payload


class ICMPHandler:
    def __init__(self, use_ipv6: bool = False) -> None:
        self._use_ipv6 = use_ipv6
        self._sock: socket.socket | None = None
        self._listen_sock: socket.socket | None = None

    def create_send_socket(self) -> socket.socket:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        self._sock.setsockopt(socket.SOL_IP, socket.IP_HDRINCL, 1)
        return self._sock

    def create_listen_socket(self) -> socket.socket:
        self._listen_sock = socket.socket(
            socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP
        )
        return self._listen_sock

    def send_echo_request(
        self,
        sock: socket.socket,
        destination: str,
        identifier: int = ICMP_IDENTIFIER,
        sequence: int = 0,
        seq: int = 0,
    ) -> None:
        icmp_packet = self._create_icmp_packet(
            ICMP_ECHO_REQUEST,
            0,
            identifier,
            sequence if sequence else seq,
            b"",
        )
        sock.sendto(icmp_packet, (destination, 0))

    def send_time_exceeded(
        self,
        sock: socket.socket,
        destination: str,
        original_packet: bytes,
        identifier: int = ICMP_IDENTIFIER,
        sequence: int = 0,
        seq: int = 0,
    ) -> None:
        icmp_packet = self._create_icmp_packet(
            ICMP_TIME_EXCEEDED,
            0,
            identifier,
            sequence if sequence else seq,
            original_packet,
        )
        sock.sendto(icmp_packet, (destination, 0))

    def _create_icmp_packet(
        self,
        icmp_type: int,
        icmp_code: int,
        identifier: int,
        sequence: int,
        payload: bytes,
    ) -> bytes:
        header = struct.pack("!BBHHH", icmp_type, icmp_code, 0, identifier, sequence)
        checksum = self._calc_icmp_checksum(header + payload)
        header = struct.pack(
            "!BBHHH", icmp_type, icmp_code, checksum, identifier, sequence
        )
        return header + payload

    def _calc_icmp_checksum(self, data: bytes) -> int:
        if len(data) % 2 != 0:
            data += b"\x00"
        checksum = 0
        for i in range(0, len(data), 2):
            word = (data[i] << 8) + data[i + 1]
            checksum += word
        checksum = (checksum >> 16) + (checksum & 0xFFFF)
        checksum += checksum >> 16
        return ~checksum & 0xFFFF

    def parse_icmp_packet(self, data: bytes) -> ICMPPacket | None:
        if len(data) < 8:
            return None
        try:
            icmp_type, icmp_code, checksum, identifier, seq = struct.unpack(
                "!BBHHH",
                data[:8],
            )
            return ICMPPacket(icmp_type, icmp_code, checksum, identifier, seq)
        except struct.error:
            return None

    def parse_ip_packet(self, data: bytes) -> IPPacket | None:
        if len(data) < 20:
            return None
        try:
            (
                vers_ihl,
                tos,
                pkt_len,
                pkt_id,
                flags_frag,
                ttl,
                proto,
                checksum,
                src,
                dst,
            ) = struct.unpack(
                "!BBHHHBBHII",
                data[:20],
            )
            return IPPacket(
                vers_ihl,
                tos,
                pkt_len,
                pkt_id,
                flags_frag,
                ttl,
                proto,
                checksum,
                src,
                dst,
            )
        except struct.error:
            return None

    def recv_icmp(
        self, sock: socket.socket, bufsize: int = 1024
    ) -> tuple[bytes, tuple[str, int]]:
        return sock.recvfrom(bufsize)

    def close(self) -> None:
        if self._sock:
            self._sock.close()
        if self._listen_sock:
            self._listen_sock.close()

    def __enter__(self) -> "ICMPHandler":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        self.close()


def ip_string_to_int(ip_str: str) -> int:
    result: tuple[int, ...] = struct.unpack("!I", socket.inet_aton(ip_str))
    return result[0]


def ip_int_to_string(ip_int: int) -> str:
    return socket.inet_ntoa(struct.pack("!I", ip_int))
