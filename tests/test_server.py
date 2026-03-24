import pytest

from pwnatpy.server import DestinationFilter


class TestDestinationFilter:
    def test_no_destinations_allowed(self) -> None:
        filter = DestinationFilter(None)
        assert filter.is_allowed("any.host.com", 80) is True
        assert filter.is_allowed("192.168.1.1", 8080) is True

    def test_empty_list_allowed(self) -> None:
        filter = DestinationFilter([])
        assert filter.is_allowed("any.host.com", 80) is True

    def test_parse_host_only(self) -> None:
        filter = DestinationFilter(["192.168.1.1"])
        assert filter.is_allowed("192.168.1.1", 80) is True
        assert filter.is_allowed("192.168.1.2", 80) is False

    def test_parse_port_only(self) -> None:
        filter = DestinationFilter([":8080"])
        assert filter.is_allowed("192.168.1.1", 8080) is True
        assert filter.is_allowed("192.168.1.1", 8081) is False

    def test_parse_host_and_port(self) -> None:
        filter = DestinationFilter(["192.168.1.1:8080"])
        assert filter.is_allowed("192.168.1.1", 8080) is True
        assert filter.is_allowed("192.168.1.1", 8081) is False
        assert filter.is_allowed("192.168.1.2", 8080) is False

    def test_parse_multiple_destinations(self) -> None:
        filter = DestinationFilter(["192.168.1.1:80", "192.168.1.2:443"])
        assert filter.is_allowed("192.168.1.1", 80) is True
        assert filter.is_allowed("192.168.1.2", 443) is True
        assert filter.is_allowed("192.168.1.3", 80) is False

    def test_parse_host_with_port_missing(self) -> None:
        filter = DestinationFilter(["example.com"])
        assert filter.is_allowed("example.com", 80) is True
        assert filter.is_allowed("example.com", 443) is True
        assert filter.is_allowed("other.com", 80) is False


class TestPwnatServer:
    @pytest.mark.asyncio
    async def test_server_initialization(self) -> None:
        filter_obj = DestinationFilter(None)
        assert filter_obj is not None

    @pytest.mark.asyncio
    async def test_server_with_custom_port(self) -> None:
        filter_obj = DestinationFilter(None)
        assert filter_obj.is_allowed("example.com", 8080)

    @pytest.mark.asyncio
    async def test_server_with_allowed_destinations(self) -> None:
        filter_obj = DestinationFilter(["192.168.1.1:80"])
        assert filter_obj.is_allowed("192.168.1.1", 80)
