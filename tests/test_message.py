import pytest

from pwnatpy.message import (
    MSG_MAX_LEN,
    MessageBuilder,
    MessageType,
    ProtocolMessage,
    decode_message,
    encode_message,
)


class TestMessageType:
    def test_message_types(self) -> None:
        assert MessageType.GOODBYE == 0x01
        assert MessageType.HELLO == 0x02
        assert MessageType.HELLOACK == 0x03
        assert MessageType.KEEPALIVE == 0x04
        assert MessageType.DATA0 == 0x05
        assert MessageType.DATA1 == 0x06
        assert MessageType.ACK0 == 0x07
        assert MessageType.ACK1 == 0x08


class TestProtocolMessage:
    def test_to_bytes(self) -> None:
        msg = ProtocolMessage(client_id=1, msg_type=MessageType.HELLO, payload=b"test")
        data = msg.to_bytes()
        assert len(data) == 5 + len(b"test")

    def test_from_bytes(self) -> None:
        original = ProtocolMessage(
            client_id=1, msg_type=MessageType.HELLO, payload=b"test"
        )
        data = original.to_bytes()
        msg = ProtocolMessage.from_bytes(data)
        assert msg.client_id == original.client_id
        assert msg.msg_type == original.msg_type
        assert msg.payload == original.payload

    def test_from_bytes_invalid_length(self) -> None:
        with pytest.raises(ValueError, match="Message too short"):
            ProtocolMessage.from_bytes(b"\x00\x00")

    def test_from_bytes_incomplete_payload(self) -> None:
        data = b"\x00\x01\x02\x00\x05test"
        with pytest.raises(ValueError, match="Message payload incomplete"):
            ProtocolMessage.from_bytes(data)

    def test_goodbye_message(self) -> None:
        msg = ProtocolMessage(client_id=1, msg_type=MessageType.GOODBYE, payload=b"")
        data = msg.to_bytes()
        assert len(data) == 5
        parsed = ProtocolMessage.from_bytes(data)
        assert parsed.client_id == 1
        assert parsed.msg_type == MessageType.GOODBYE
        assert parsed.payload == b""

    def test_data_message(self) -> None:
        payload = b"x" * 100
        msg = ProtocolMessage(client_id=5, msg_type=MessageType.DATA0, payload=payload)
        data = msg.to_bytes()
        parsed = ProtocolMessage.from_bytes(data)
        assert parsed.client_id == 5
        assert parsed.msg_type == MessageType.DATA0
        assert parsed.payload == payload


class TestMessageBuilder:
    def test_build_hello(self) -> None:
        msg = MessageBuilder.build_hello(1, "192.168.1.1", 8080)
        assert msg.client_id == 1
        assert msg.msg_type == MessageType.HELLO
        assert msg.payload == b"192.168.1.1:8080"

    def test_build_hello_with_port(self) -> None:
        msg = MessageBuilder.build_hello(2, "example.com", 22)
        assert msg.payload == b"example.com:22"

    def test_build_hello_ack(self) -> None:
        msg = MessageBuilder.build_hello_ack(1)
        assert msg.client_id == 1
        assert msg.msg_type == MessageType.HELLOACK
        assert msg.payload == b""

    def test_build_goodbye(self) -> None:
        msg = MessageBuilder.build_goodbye(1)
        assert msg.client_id == 1
        assert msg.msg_type == MessageType.GOODBYE
        assert msg.payload == b""

    def test_build_keepalive(self) -> None:
        msg = MessageBuilder.build_keepalive(1)
        assert msg.client_id == 1
        assert msg.msg_type == MessageType.KEEPALIVE
        assert msg.payload == b""

    def test_build_data_seq0(self) -> None:
        msg = MessageBuilder.build_data(1, 0, b"test data")
        assert msg.client_id == 1
        assert msg.msg_type == MessageType.DATA0
        assert msg.payload == b"test data"

    def test_build_data_seq1(self) -> None:
        msg = MessageBuilder.build_data(1, 1, b"test data")
        assert msg.client_id == 1
        assert msg.msg_type == MessageType.DATA1

    def test_build_ack_seq0(self) -> None:
        msg = MessageBuilder.build_ack(1, 0)
        assert msg.client_id == 1
        assert msg.msg_type == MessageType.ACK0
        assert msg.payload == b""

    def test_build_ack_seq1(self) -> None:
        msg = MessageBuilder.build_ack(1, 1)
        assert msg.client_id == 1
        assert msg.msg_type == MessageType.ACK1

    def test_parse_hello_payload(self) -> None:
        host, port = MessageBuilder.parse_hello_payload(b"192.168.1.1:8080")
        assert host == "192.168.1.1"
        assert port == 8080

    def test_parse_hello_payload_with_port(self) -> None:
        host, port = MessageBuilder.parse_hello_payload(b"example.com:22")
        assert host == "example.com"
        assert port == 22

    def test_parse_hello_payload_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid HELLO payload format"):
            MessageBuilder.parse_hello_payload(b"invalid")


class TestEncodeDecodeFunctions:
    def test_encode_message(self) -> None:
        data = encode_message(1, MessageType.HELLO, b"test")
        assert len(data) > 0

    def test_roundtrip(self) -> None:
        original = ProtocolMessage(
            client_id=42, msg_type=MessageType.DATA1, payload=b"hello world"
        )
        encoded = encode_message(
            original.client_id, original.msg_type, original.payload
        )
        decoded = decode_message(encoded)
        assert decoded.client_id == original.client_id
        assert decoded.msg_type == original.msg_type
        assert decoded.payload == original.payload


class TestEdgeCases:
    def test_empty_payload(self) -> None:
        msg = ProtocolMessage(client_id=1, msg_type=MessageType.KEEPALIVE, payload=b"")
        data = msg.to_bytes()
        parsed = ProtocolMessage.from_bytes(data)
        assert parsed.payload == b""

    def test_max_payload_size(self) -> None:
        max_payload = b"x" * MSG_MAX_LEN
        msg = ProtocolMessage(
            client_id=1, msg_type=MessageType.DATA0, payload=max_payload
        )
        data = msg.to_bytes()
        assert len(data) == 5 + MSG_MAX_LEN

    def test_large_client_id(self) -> None:
        msg = ProtocolMessage(
            client_id=65535, msg_type=MessageType.HELLO, payload=b"test"
        )
        data = msg.to_bytes()
        parsed = ProtocolMessage.from_bytes(data)
        assert parsed.client_id == 65535

    def test_all_message_types(self) -> None:
        for msg_type in MessageType:
            msg = ProtocolMessage(client_id=1, msg_type=msg_type, payload=b"test")
            data = msg.to_bytes()
            parsed = ProtocolMessage.from_bytes(data)
            assert parsed.msg_type == msg_type
