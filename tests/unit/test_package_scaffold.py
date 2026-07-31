from trade import __version__


def test_package_exposes_version() -> None:
    # Keep in lockstep with pyproject.toml [project] version — B111 F004
    # fix-round aligned this drifted pin (was 0.1.0 while the wheel was 0.2.x).
    assert __version__ == "0.2.2"


def test_no_broker_entrypoints_in_scaffold() -> None:
    import trade.brokers as brokers

    assert brokers.__all__ == []
