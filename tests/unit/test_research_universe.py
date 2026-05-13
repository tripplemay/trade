from trade.data.universe import load_research_universe


def test_research_universe_covers_required_asset_classes() -> None:
    universe = load_research_universe()
    asset_classes = {entry.asset_class for entry in universe.entries}

    assert {
        "global_equity",
        "us_equity",
        "ex_us_equity",
        "bonds",
        "gold_commodity",
        "cash_defensive",
    }.issubset(asset_classes)


def test_research_universe_entries_include_data_dictionary_fields() -> None:
    universe = load_research_universe()

    assert universe.universe_id == "global_etf_research_universe_v1"
    assert "no paid data" in universe.data_source_policy
    for entry in universe.entries:
        assert entry.ticker
        assert entry.name
        assert entry.asset_class
        assert entry.region
        assert entry.currency == "USD"
        assert entry.role
        assert entry.data_source_policy
        assert entry.research_notes


def test_research_universe_is_not_live_or_broker_authorization() -> None:
    universe = load_research_universe()
    combined_policy = " ".join(entry.data_source_policy.lower() for entry in universe.entries)

    assert "broker" not in combined_policy
    assert "live" not in combined_policy
    assert "paid data" not in combined_policy
