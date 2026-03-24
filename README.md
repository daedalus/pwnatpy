# pwnatpy

> NAT traversal tool - peer-to-peer communication through NATs without port forwarding

[![PyPI](https://img.shields.io/pypi/v/pwnatpy.svg)](https://pypi.org/project/pwnatpy/)
[![Python](https://img.shields.io/pypi/pyversions/pwnatpy.svg)](https://pypi.org/project/pwnatpy/)
[![Coverage](https://codecov.io/gh/user/pwnatpy/branch/main/graph/badge.svg)](https://codecov.io/gh/user/pwnatpy)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

pwnatpy enables direct communication between a client behind a NAT and a server behind a separate NAT without any port forwarding, DMZ, UPnP, or third-party proxy. The connection is established peer-to-peer using ICMP Time Exceeded packets to penetrate NATs.

## Install

```bash
pip install pwnatpy
```

## Usage

### Server Mode

```bash
pwnatpy -s [bind_ip] [proxy_port] [[allowed_host]:[allowed_port] ...]
```

Example:
```bash
sudo pwnatpy -s 0.0.0.0 2222
```

### Client Mode

```bash
pwnatpy [local_ip] <local_port> <proxy_host> [proxy_port] <remote_host> <remote_port>
```

Example:
```bash
sudo pwnatpy 127.0.0.1 0 3.3.3.1 2222 192.168.1.100 22
```

## How It Works

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

## Requirements

- Root/sudo privileges (required for raw socket access)
- Python 3.11+

## CLI Options

| Option | Description |
|--------|-------------|
| `-c` | Client mode (default) |
| `-s` | Server mode |
| `-6` | Use IPv6 |
| `-v` | Increase debug verbosity |
| `-a` | Enable SO_REUSEADDR |
| `-p` | Enable SO_REUSEPORT |

## Development

```bash
git clone https://github.com/user/pwnatpy.git
cd pwnatpy
pip install -e ".[test]"

# run tests
pytest

# format
ruff format src/ tests/

# lint
ruff check src/ tests/

# type check
mypy src/
```
