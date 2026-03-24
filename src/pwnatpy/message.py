import struct
from dataclasses import dataclass
from enum import IntEnum

MSG_MAX_LEN = 1024

GOODBYE = 0x01
HELLO = 0x02
HELLOACK = 0x03
KEEPALIVE = 0x04
DATA0 = 0x05
DATA1 = 0x06
ACK0 = 0x07
ACK1 = 0x08


class MessageType(IntEnum):
    GOODBYE = 0x01
    HELLO = 0x02
    HELLOACK = 0x03
    KEEPALIVE = 0x04
    DATA0 = 0x05
    DATA1 = 0x06
    ACK0 = 0x07
    ACK1 = 0x08


@dataclass
class ProtocolMessage:
    client_id: int
    msg_type: MessageType
    payload: bytes

    def to_bytes(self) -> bytes:
        header = struct.pack("!HBH", self.client_id, self.msg_type, len(self.payload))
        return header + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "ProtocolMessage":
        if len(data) < 5:
            raise ValueError("Message too short: minimum 5 bytes required")
        client_id, msg_type_byte, length = struct.unpack("!HBH", data[:5])
        if len(data) < 5 + length:
            raise ValueError(f"Message payload incomplete: expected {length} bytes")
        msg_type = MessageType(msg_type_byte)
        payload = data[5 : 5 + length]
        return cls(client_id, msg_type, payload)


class MessageBuilder:
    @staticmethod
    def build_hello(
        client_id: int, remote_host: str, remote_port: int
    ) -> ProtocolMessage:
        payload = f"{remote_host}:{remote_port}".encode()
        return ProtocolMessage(client_id, MessageType.HELLO, payload)

    @staticmethod
    def build_hello_ack(client_id: int) -> ProtocolMessage:
        return ProtocolMessage(client_id, MessageType.HELLOACK, b"")

    @staticmethod
    def build_goodbye(client_id: int) -> ProtocolMessage:
        return ProtocolMessage(client_id, MessageType.GOODBYE, b"")

    @staticmethod
    def build_keepalive(client_id: int) -> ProtocolMessage:
        return ProtocolMessage(client_id, MessageType.KEEPALIVE, b"")

    @staticmethod
    def build_data(client_id: int, seq: int, data: bytes) -> ProtocolMessage:
        msg_type = MessageType.DATA0 if seq == 0 else MessageType.DATA1
        return ProtocolMessage(client_id, msg_type, data)

    @staticmethod
    def build_ack(client_id: int, seq: int) -> ProtocolMessage:
        msg_type = MessageType.ACK0 if seq == 0 else MessageType.ACK1
        return ProtocolMessage(client_id, msg_type, b"")

    @staticmethod
    def parse_hello_payload(payload: bytes) -> tuple[str, int]:
        decoded = payload.decode()
        if ":" in decoded:
            host, port_str = decoded.rsplit(":", 1)
            return host, int(port_str)
        raise ValueError("Invalid HELLO payload format")


def encode_message(
    client_id: int, msg_type: MessageType, payload: bytes = b""
) -> bytes:
    return ProtocolMessage(client_id, msg_type, payload).to_bytes()


def decode_message(data: bytes) -> ProtocolMessage:
    return ProtocolMessage.from_bytes(data)
