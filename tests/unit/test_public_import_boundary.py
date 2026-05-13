import pytest

from trade.data.public_import import import_public_data_stub, public_import_boundary


def test_public_import_boundary_is_manual_disabled_and_off_ci() -> None:
    boundary = public_import_boundary()

    assert boundary.enabled_by_default is False
    assert boundary.ci_dependency is False
    assert boundary.requires_credentials is False
    assert str(boundary.output_directory).startswith("data/")
    assert boundary.data_label == "optional_public_best_effort_non_pit"
    assert "not point-in-time" in boundary.limitation


def test_public_import_stub_fails_closed_without_network() -> None:
    with pytest.raises(RuntimeError, match="intentionally disabled"):
        import_public_data_stub()
