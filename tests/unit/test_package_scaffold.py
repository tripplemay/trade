from trade import __version__


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"


def test_no_broker_entrypoints_in_scaffold() -> None:
    import trade.brokers as brokers

    assert brokers.__all__ == []
