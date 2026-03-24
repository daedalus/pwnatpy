import argparse
import asyncio
import sys

from . import __version__
from .client_component import pwnat_client
from .server import pwnat_server


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="pwnatpy",
        description="NAT traversal tool - peer-to-peer communication through NATs",
    )
    parser.add_argument(
        "-c",
        "--client",
        action="store_true",
        help="Run in client mode (default)",
    )
    parser.add_argument(
        "-s",
        "--server",
        action="store_true",
        help="Run in server mode",
    )
    parser.add_argument(
        "-6",
        "--ipv6",
        action="store_true",
        help="Use IPv6",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (can be used multiple times)",
    )
    parser.add_argument(
        "-a",
        "--reuse-addr",
        action="store_true",
        help="Enable SO_REUSEADDR",
    )
    parser.add_argument(
        "-p",
        "--reuse-port",
        action="store_true",
        help="Enable SO_REUSEPORT",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"pwnatpy {__version__}",
    )

    server_group = parser.add_argument_group("server options")
    server_group.add_argument(
        "server_bind_ip",
        nargs="?",
        default="0.0.0.0",
        help="Local IP to bind to (default: 0.0.0.0)",
    )
    server_group.add_argument(
        "proxy_port",
        nargs="?",
        type=int,
        default=2222,
        help="Proxy port (default: 2222)",
    )
    server_group.add_argument(
        "allowed_destinations",
        nargs="*",
        metavar="allowed",
        help="Allowed destinations in format [host]:[port]",
    )

    client_group = parser.add_argument_group("client options")
    client_group.add_argument(
        "client_local_ip",
        nargs="?",
        default="127.0.0.1",
        help="Local IP to bind to (default: 127.0.0.1)",
    )
    client_group.add_argument(
        "client_local_port",
        nargs="?",
        type=int,
        default=0,
        help="Local port (default: 0 = random)",
    )
    client_group.add_argument(
        "proxy_host",
        nargs="?",
        default="3.3.3.1",
        help="Proxy server host (default: 3.3.3.1)",
    )
    client_group.add_argument(
        "proxy_port_client",
        nargs="?",
        type=int,
        default=2222,
        help="Proxy server port (default: 2222)",
    )
    client_group.add_argument(
        "remote_host",
        nargs="?",
        default="127.0.0.1",
        help="Remote host to connect to (default: 127.0.0.1)",
    )
    client_group.add_argument(
        "remote_port",
        nargs="?",
        type=int,
        default=22,
        help="Remote port to connect to (default: 22)",
    )

    args = parser.parse_args()

    verbose = args.verbose > 0

    if args.server:
        try:
            asyncio.run(
                pwnat_server(
                    bind_ip=args.server_bind_ip,
                    proxy_port=args.proxy_port,
                    allowed_destinations=args.allowed_destinations or None,
                    reuse_addr=args.reuse_addr,
                    reuse_port=args.reuse_port,
                    verbose=verbose,
                )
            )
        except KeyboardInterrupt:
            return 0
        return 1

    client_mode = args.client or (
        not args.server
        and len(sys.argv) > 1
        and sys.argv[1] not in ("-s", "--server", "-h", "--help", "--version")
    )

    if client_mode:
        try:
            asyncio.run(
                pwnat_client(
                    local_ip=args.client_local_ip,
                    local_port=args.client_local_port,
                    proxy_host=args.proxy_host,
                    proxy_port=args.proxy_port_client,
                    remote_host=args.remote_host,
                    remote_port=args.remote_port,
                    reuse_addr=args.reuse_addr,
                    reuse_port=args.reuse_port,
                    verbose=verbose,
                )
            )
        except KeyboardInterrupt:
            return 0
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
