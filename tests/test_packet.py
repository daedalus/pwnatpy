import struct

from pwnatpy.packet import (
    FAKE_DESTINATION,
    ICMP_DEST_UNREACHABLE,
    ICMP_ECHO_REPLY,
    ICMP_ECHO_REQUEST,
    ICMP_IDENTIFIER,
    ICMP_TIME_EXCEEDED,
    ICMPHandler,
    ip_int_to_string,
    ip_string_to_int,
)


class TestICMPConstants:
    def test_icmp_types(self) -> None:
        assert ICMP_ECHO_REQUEST == 8
        assert ICMP_ECHO_REPLY == 0
        assert ICMP_TIME_EXCEEDED == 11
        assert ICMP_DEST_UNREACHABLE == 3


class TestIPConversion:
    def test_ip_string_to_int(self) -> None:
        assert ip_string_to_int("127.0.0.1") == 0x7F000001
        assert ip_string_to_int("192.168.1.1") == 0xC0A80101
        assert ip_string_to_int("0.0.0.0") == 0
        assert ip_string_to_int("255.255.255.255") == 0xFFFFFFFF

    def test_ip_int_to_string(self) -> None:
        assert ip_int_to_string(0x7F000001) == "127.0.0.1"
        assert ip_int_to_string(0xC0A80101) == "192.168.1.1"
        assert ip_int_to_string(0) == "0.0.0.0"
        assert ip_int_to_string(0xFFFFFFFF) == "255.255.255.255"

    def test_roundtrip(self) -> None:
        original = "203.0.113.42"
        converted = ip_string_to_int(original)
        back = ip_int_to_string(converted)
        assert back == original


class TestICMPHandler:
    def test_default_ipv4(self) -> None:
        handler = ICMPHandler(use_ipv6=False)
        assert handler._use_ipv6 is False

    def test_ipv6_flag(self) -> None:
        handler = ICMPHandler(use_ipv6=True)
        assert handler._use_ipv6 is True

    def test_calc_icmp_checksum_zero(self) -> None:
        handler = ICMPHandler()
        data = b"\x00" * 10
        checksum = handler._calc_icmp_checksum(data)
        assert checksum == 65535

    def test_calc_icmp_checksum_simple(self) -> None:
        handler = ICMPHandler()
        data = b"Hello"
        checksum = handler._calc_icmp_checksum(data)
        assert checksum > 0

    def test_calc_icmp_checksum_with_odd_length(self) -> None:
        handler = ICMPHandler()
        data = b"HelloW"
        checksum1 = handler._calc_icmp_checksum(data)
        checksum2 = handler._calc_icmp_checksum(data + b"\x00")
        assert checksum1 == checksum2

    def test_parse_icmp_packet_valid(self) -> None:
        handler = ICMPHandler()
        packet = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, 0, 1234, 1) + b"test"
        parsed = handler.parse_icmp_packet(packet)
        assert parsed is not None
        assert parsed.type == ICMP_ECHO_REQUEST
        assert parsed.code == 0
        assert parsed.identifier == 1234
        assert parsed.seq == 1

    def test_parse_icmp_packet_too_short(self) -> None:
        handler = ICMPHandler()
        packet = b"\x00\x00\x00"
        parsed = handler.parse_icmp_packet(packet)
        assert parsed is None

    def test_parse_icmp_packet_invalid(self) -> None:
        handler = ICMPHandler()
        packet = b"invalid"
        parsed = handler.parse_icmp_packet(packet)
        assert parsed is None

    def test_parse_ip_packet_valid(self) -> None:
        handler = ICMPHandler()
        ip_header = struct.pack(
            "!BBHHHBBHII",
            0x45,  # vers + ihl
            0,  # tos
            64,  # total length
            1234,  # id
            0,  # flags + frag offset
            64,  # ttl
            1,  # protocol (ICMP)
            0,  # checksum
            0xC0A80101,  # src ip
            0x0101A8C0,  # dst ip
        )
        parsed = handler.parse_ip_packet(ip_header)
        assert parsed is not None
        assert parsed.vers_ihl == 0x45
        assert parsed.tos == 0
        assert parsed.pkt_len == 64
        assert parsed.id == 1234

    def test_parse_ip_packet_too_short(self) -> None:
        handler = ICMPHandler()
        ip_header = b"\x00" * 10
        parsed = handler.parse_ip_packet(ip_header)
        assert parsed is None


class TestICMPPacketCreation:
    def test_create_echo_request_packet(self) -> None:
        handler = ICMPHandler()
        packet = handler._create_icmp_packet(
            ICMP_ECHO_REQUEST,
            0,
            ICMP_IDENTIFIER,
            1,
            b"test",
        )
        assert len(packet) > 0
        icmp_type = packet[0]
        assert icmp_type == ICMP_ECHO_REQUEST

    def test_create_time_exceeded_packet(self) -> None:
        handler = ICMPHandler()
        packet = handler._create_icmp_packet(
            ICMP_TIME_EXCEEDED,
            0,
            ICMP_IDENTIFIER,
            1,
            b"original packet data",
        )
        assert len(packet) > 0
        icmp_type = packet[0]
        assert icmp_type == ICMP_TIME_EXCEEDED


class TestFakeDestination:
    def test_fake_destination_value(self) -> None:
        assert FAKE_DESTINATION == "3.3.3.3"

    def test_icmp_identifier_value(self) -> None:
        assert ICMP_IDENTIFIER == 0xFFFF
