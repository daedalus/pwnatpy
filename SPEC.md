# pwnatpy - Specification Document

## 1. Project Overview

### Project Name
**pwnatpy** - A NAT traversal tool

### Project Type
Network utility / proxy server

### Core Functionality
pwnat enables direct communication between a client behind a NAT and a server behind a separate NAT without any port forwarding, DMZ, UPnP, or third-party proxy. The connection is established peer-to-peer using ICMP Time Exceeded packets to penetrate NATs.

---

## 2. Technical Architecture

### 2.1 Protocol Overview

The pwnat protocol operates in three phases:

1. **NAT Penetration (ICMP-based)**
   - Server sends periodic ICMP Echo Request packets to 3.3.3.3 (fake destination)
   - Client sends ICMP Time Exceeded packets containing the server's original packet
   - Server's NAT recognizes the inner packet and forwards the ICMP to the server
   - Server extracts client's public IP address from the ICMP payload

2. **UDP Session Establishment**
   - Server sends UDP packets to client (initially dropped by client's NAT)
   - Client sends UDP packets to server (server's NAT allows as it's responding to server's outgoing packets)
   - Both NATs now have "pinholes" allowing bidirectional UDP traffic

3. **TCP Tunneling**
   - UDP tunnel carries TCP payload between client and server
   - Custom protocol handles reliability, ordering, and flow control

### 2.2 Message Protocol

Message header structure (5 bytes):
```
+----------+------+----------+
| client_id| type | length   |
| (2 bytes)|(1 b) | (2 bytes)|
+----------+------+----------+
```

Message types:
| Type | Value | Description |
|------|-------|-------------|
| GOODBYE | 0x01 | Connection termination |
| HELLO | 0x02 | Initial connection request with target host:port |
| HELLOACK | 0x03 | Acknowledgment of HELLO |
| KEEPALIVE | 0x04 | Keep-alive ping |
| DATA0 | 0x05 | Data packet (alternating sequence) |
| DATA1 | 0x06 | Data packet (alternating sequence) |
| ACK0 | 0x07 | Acknowledgment for DATA0 |
| ACK1 | 0x08 | Acknowledgment for DATA1 |

### 2.3 Data Flow

```
[Client App] <--TCP--> [pwnat Client] <--UDP Tunnel--> [pwnat Server] <--TCP--> [Remote Host]
```

---

## 3. Component Specifications

### 3.1 Main Entry Point (`pwnat.c`)

**Purpose**: Parse command-line arguments and dispatch to client or server mode.

**Command-line Options**:
| Option | Description |
|--------|-------------|
| `-c` | Client mode (default) |
| `-s` | Server mode |
| `-6` | Use IPv6 |
| `-v` | Increase debug verbosity (up to 2 levels) |
| `-a` | Enable SO_REUSEADDR |
| `-p` | Enable SO_REUSEPORT |
| `-h` | Show help |

**Client Usage**: `[local ip] <local port> <proxy host> [proxy port (def:2222)] <remote host> <remote port>`

**Server Usage**: `[local ip] [proxy port (def:2222)] [[allowed host]:[allowed port] ...]`

### 3.2 Server Component (`udpserver.c`)

**Purpose**: Run the pwnat server that accepts connections from clients behind NATs.

**Key Functions**:
- `udpserver(argc, argv)` - Main server loop
- `handle_message()` - Process incoming UDP messages
- `disconnect_and_remove_client()` - Clean up disconnected clients
- `destination_allowed()` - Check if connection to target is permitted

**Behavior**:
1. Creates UDP socket on specified port (default 2222)
2. Creates raw ICMP socket for sending fake packets
3. Creates raw ICMP listening socket for receiving Time Exceeded packets
4. Periodically sends ICMP Echo Request to 3.3.3.3
5. Listens for incoming ICMP Time Exceeded packets from clients
6. On client detection, sends UDP packet to create pinhole
7. Handles client connections, proxies TCP to UDP tunnel

**Allowed Destinations**: Server can optionally restrict allowed remote destinations.

### 3.3 Client Component (`udpclient.c`)

**Purpose**: Run the pwnat client that connects through NAT to server.

**Key Functions**:
- `udpclient(argc, argv)` - Main client loop
- `handle_message()` - Process incoming messages
- `disconnect_and_remove_client()` - Clean up connections
- `isnumber()` - Helper to parse arguments

**Behavior**:
1. Creates TCP server socket to accept local connections
2. Creates raw ICMP socket
3. Periodically sends ICMP Time Exceeded packets to server
4. On NAT penetration, creates UDP connection to server
5. Proxies local TCP connections through UDP tunnel to remote host

### 3.4 Client State Management (`client.h`, `client.c`)

**Client States** (for data going UDP -> TCP):
- `CLIENT_WAIT_HELLO` - Waiting for connection
- `CLIENT_WAIT_DATA0` - Waiting for DATA0
- `CLIENT_WAIT_DATA1` - Waiting for DATA1

**Client States** (for data going TCP -> UDP):
- `CLIENT_WAIT_DATA0` - Waiting for DATA0
- `CLIENT_WAIT_DATA1` - Waiting for DATA1
- `CLIENT_WAIT_ACK0` - Sent DATA0, waiting for ACK0
- `CLIENT_WAIT_ACK1` - Sent DATA1, waiting for ACK1

**Timeout Constants**:
- `CLIENT_TIMEOUT` - 1 second (resend interval)
- `CLIENT_MAX_RESEND` - 10 attempts before disconnect
- `KEEP_ALIVE_SECS` - 60 seconds (keep-alive interval)
- `KEEP_ALIVE_TIMEOUT_SECS` - 421 seconds (7 minutes + 1 second)

### 3.5 Socket Management (`socket.h`, `socket.c`)

**socket_t Structure**:
```c
typedef struct socket {
    int fd;                       // File descriptor
    int type;                     // SOCK_STREAM or SOCK_DGRAM
    struct sockaddr_storage addr; // IP and port
    socklen_t addr_len;          // Address length
} socket_t;
```

**Key Functions**:
- `sock_create()` - Create and optionally connect/bind socket
- `sock_connect()` - Connect socket to address
- `sock_accept()` - Accept incoming TCP connection
- `sock_send()` / `sock_recv()` - Send/receive data
- `sock_close()` / `sock_free()` - Cleanup

### 3.6 Message Handling (`message.h`, `message.c`)

**Protocol Constants**:
- `MSG_MAX_LEN` - 1024 bytes (maximum payload)
- `KEEP_ALIVE_SECS` - 60 seconds
- `KEEP_ALIVE_TIMEOUT_SECS` - 421 seconds

### 3.7 ICMP Packet Handling (`packet.h`, `packet.c`)

**Key Functions**:
- `create_icmp_socket()` - Create raw socket for sending ICMP (requires root)
- `create_listen_socket()` - Create raw socket for receiving ICMP (requires root)
- `send_icmp()` - Send ICMP Time Exceeded (client) or Echo Request (server)
- `calc_icmp_checksum()` - Calculate ICMP checksum
- `socket_broadcast()` - Enable SO_BROADCAST
- `socket_iphdrincl()` - Enable IP_HDRINCL

**Packet Structures**:
```c
struct ip_packet_t {
    uint8_t  vers_ihl, tos;
    uint16_t pkt_len, id, flags_frag_offset;
    uint8_t  ttl, proto;
    uint16_t checksum;
    uint32_t src_ip, dst_ip;
};

struct icmp_packet_t {
    uint8_t  type, code;
    uint16_t checksum, identifier, seq;
};
```

### 3.8 Client List Management (`list.h`, `list.c`)

**Purpose**: Manage list of connected clients.

**Operations**:
- `list_create()` - Initialize list
- `list_add()` - Add client (sorted insertion)
- `list_get()` / `list_get_at()` - Retrieve client
- `list_delete()` / `list_delete_at()` - Remove client
- `list_free()` - Clean up

### 3.9 Destination Filtering (`destination.h`, `destination.c`)

**Purpose**: Parse and match allowed destination addresses.

**Format**: `[host]:[port]` (both optional)

---

## 4. Build System

### Makefile Targets

**Build**:
```bash
make        # Builds pwnat with address sanitizer
make clean  # Removes compiled files
```

**Compilation**:
- Requires GCC with C99 support
- Default OS: LINUX
- Supports: LINUX, SOLARIS, CYGWIN

**Flags**:
- `-Wall -Wextra -Wpedantic -Wshadow -Wpointer-arith -Wwrite-strings`
- `-fsanitize=address` (AddressSanitizer enabled by default)

### Cross-Compilation

- `Makefile.mingw-win32` - Windows cross-compilation
- `cross-compile-mingw.sh` - Build script

---

## 5. Platform Support

### Unix/Linux
- Full support
- Requires root for ICMP sockets

### Windows
- Requires administrator privileges for ICMP sockets
- Uses WSAStartup/WSACleanup
- Custom gettimeofday implementation

---

## 6. Security Considerations

1. **Root/Admin Required**: Both client and server need elevated privileges for raw socket access
2. **No Encryption**: Traffic is transmitted in plaintext over UDP
3. **No Authentication**: Server has optional destination filtering but no client authentication
4. **ICMP Rate Limiting**: Periodic ICMP packets (every ~5 seconds) could be detected by firewalls

---

## 7. Files Summary

| File | Purpose |
|------|---------|
| `pwnat.c` | Main entry point |
| `udpserver.c` | Server implementation |
| `udpclient.c` | Client implementation |
| `client.c/h` | Client state management |
| `socket.c/h` | Socket abstraction |
| `message.c/h` | Protocol message handling |
| `packet.c/h` | ICMP packet construction |
| `list.c/h` | Client list management |
| `destination.c/h` | Destination filtering |
| `common.h` | Shared definitions |
| `strlcpy.c` | BSD string functions |
| `gettimeofday.c/h` | Windows compatibility |
| `xgetopt.c/h` | Windows getopt |
