from core.net.update_checker import _parse_version


def test_parse_version_orders_numerically():
    assert _parse_version("v0.10.0") > _parse_version("0.9.9")
    assert _parse_version("v1.2.3") == (1, 2, 3)
