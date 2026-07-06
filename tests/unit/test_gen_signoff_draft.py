"""B098 F001 — unit tests for scripts/gen_signoff_draft.py.

Covers the two things that matter for this tool:

  (a) mechanical fields render from a fixture batch state (features / commits /
      changed files / CI conclusions / gates / production-surface heuristic);
  (b) ★ the judgment sections are ALWAYS placeholders and NEVER contain a verdict
      (PASS / FAIL / 裁定) — asserted specifically even when every CI run is green,
      i.e. the tool does NOT infer a verdict from all-green CI;
  (c) missing / malformed data degrades to a placeholder and never crashes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "gen_signoff_draft.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_signoff_draft", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve the module for field().
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gsd = _load_module()


# Tokens a judgment section must NEVER contain in a machine-generated draft.
FORBIDDEN_VERDICT_TOKENS = ["PASS", "FAIL", "裁定：", "全 PASS", "全PASS", "→ done"]


def _green_state() -> gsd.BatchState:
    """A fixture batch state with ALL CI runs green (success)."""
    return gsd.BatchState(
        batch_id="B999",
        features=[
            gsd.Feature(
                id="F001", title="mech scaffold tool", executor="generator", status="done"
            ),
            gsd.Feature(
                id="F002", title="codex independent signoff", executor="codex", status="pending"
            ),
        ],
        commits=[
            gsd.Commit(sha="abcdef1234567890", subject="feat(B999-F001): scaffold [F001 done]"),
            gsd.Commit(sha="0011223344556677", subject="chore(B999): 开批"),
        ],
        diffstat=" scripts/x.py | 10 ++++++++++\n 1 file changed, 10 insertions(+)",
        changed_files=["trade/engine.py", "docs/foo.md", "tests/unit/test_x.py", "misc.txt"],
        ci_runs=[
            gsd.CIRun(
                workflow="Workbench Backend CI",
                conclusion="success",
                status="completed",
                url="u1",
            ),
            gsd.CIRun(
                workflow="AI Safety Eval", conclusion="success", status="completed", url="u2"
            ),
            gsd.CIRun(
                workflow="Workbench Deploy", conclusion="success", status="completed", url="u3"
            ),
        ],
        head_sha="abcdef1234567890",
        generator_handoff={
            "summary": "all green",
            "tests": "261 passed",
            "ruff": "clean",
            "mypy": "ok",
        },
        notes=[],
    )


# --------------------------------------------------------------------------- #
# (a) mechanical fields render
# --------------------------------------------------------------------------- #


def test_features_render_from_state() -> None:
    out = gsd.render_features(_green_state())
    assert "F001" in out
    assert "mech scaffold tool" in out
    assert "generator" in out
    assert "codex" in out
    assert "pending" in out


def test_commits_render_shas_and_subjects() -> None:
    out = gsd.render_commits(_green_state())
    assert "abcdef1234" in out  # truncated SHA
    assert "feat(B999-F001): scaffold [F001 done]" in out


def test_changed_files_and_diffstat_render() -> None:
    out = gsd.render_changed_files(_green_state())
    assert "1 file changed" in out


def test_ci_conclusions_echo_gh_vocabulary() -> None:
    out = gsd.render_ci(_green_state())
    assert "Workbench Backend CI" in out
    assert "AI Safety Eval" in out
    # gh's raw "success" is echoed — this is a fact column, not a verdict.
    assert "success" in out


def test_gates_echo_generator_handoff() -> None:
    out = gsd.render_gates(_green_state())
    assert "261 passed" in out
    # explicitly labelled as self-reported / not re-run
    assert "自报" in out


def test_production_surface_is_location_bucketing_not_a_verdict() -> None:
    out = gsd.render_production_surface(_green_state())
    # trade/ is a runtime prefix; docs/ and tests/ are non-runtime; misc.txt is other.
    assert "trade/engine.py" in out
    assert "docs/foo.md" in out
    assert "tests/unit/test_x.py" in out
    assert "misc.txt" in out
    # It must frame itself as a raw location fact, not a risk judgment.
    assert "非风险裁定" in out
    for token in ("PASS", "FAIL", "安全", "有风险"):
        assert token not in out


def test_classify_changed_files_buckets() -> None:
    runtime, non_runtime, other = gsd.classify_changed_files(
        ["trade/a.py", "docs/b.md", "tests/c.py", "workbench/backend/workbench_api/d.py", "z.cfg"]
    )
    assert runtime == ["trade/a.py", "workbench/backend/workbench_api/d.py"]
    assert non_runtime == ["docs/b.md", "tests/c.py"]
    assert other == ["z.cfg"]


# --------------------------------------------------------------------------- #
# (b) ★ judgment sections are ALWAYS placeholders — even with all-green CI
# --------------------------------------------------------------------------- #


def test_judgment_sections_are_pure_placeholders() -> None:
    out = gsd.render_judgment_sections()
    # Every judgment heading is followed by an explicit evaluator placeholder.
    assert out.count("[待独立评估填写：") >= 4
    for token in FORBIDDEN_VERDICT_TOKENS:
        assert token not in out


def test_judgment_function_takes_no_state() -> None:
    """Structural proof of 铁律#4: judgment cannot depend on CI/git state."""
    import inspect

    sig = inspect.signature(gsd.render_judgment_sections)
    assert len(sig.parameters) == 0


def test_full_draft_with_all_green_ci_still_has_no_verdict_in_judgment() -> None:
    """★ Even when every CI run is 'success', the tool must NOT write a verdict.

    We split the draft at the judgment banner and assert the judgment half is
    placeholder-only. (The mechanical half legitimately echoes gh's raw
    'success' conclusion — that is a fact column, not the evaluator's 裁定.)
    """
    draft = gsd.render_draft(_green_state())
    banner = "# 以下为判断段"
    assert banner in draft
    judgment_half = draft.split(banner, 1)[1]

    # The judgment half carries the four placeholders...
    assert judgment_half.count("[待独立评估填写：") >= 4
    # ...and never a verdict, despite all-green CI upstream.
    for token in FORBIDDEN_VERDICT_TOKENS:
        assert token not in judgment_half
    # Guard the specific failure mode: green CI must not become an implied PASS.
    assert "PASS" not in judgment_half


# --------------------------------------------------------------------------- #
# (c) missing / malformed data → placeholder, never crash
# --------------------------------------------------------------------------- #


def _empty_state() -> gsd.BatchState:
    return gsd.BatchState(
        batch_id="UNKNOWN",
        features=[],
        commits=[],
        diffstat=None,
        changed_files=[],
        ci_runs=[],
        head_sha=None,
        generator_handoff=None,
        notes=["无法确定批次 id", "gh run list 不可用"],
    )


def test_empty_state_renders_placeholders_without_crashing() -> None:
    draft = gsd.render_draft(_empty_state())
    # Mechanical data-missing placeholder appears for the empty sections.
    assert gsd.DATA_PLACEHOLDER in draft
    # Judgment placeholders still present.
    assert "[待独立评估填写：" in draft
    # Collection notes surfaced in the appendix.
    assert "gh run list 不可用" in draft


def test_parse_ci_runs_handles_garbage() -> None:
    assert gsd.parse_ci_runs(None) == []
    assert gsd.parse_ci_runs("not json") == []
    assert gsd.parse_ci_runs("{}") == []  # object, not list
    assert gsd.parse_ci_runs("[1, 2, 3]") == []  # non-dict rows dropped


def test_parse_ci_runs_extracts_fields_including_head_sha() -> None:
    payload = (
        '[{"workflowName":"Backend CI","conclusion":"success",'
        '"status":"completed","url":"http://x","headSha":"deadbeef"}]'
    )
    runs = gsd.parse_ci_runs(payload)
    assert len(runs) == 1
    assert runs[0].workflow == "Backend CI"
    assert runs[0].conclusion == "success"
    assert runs[0].head_sha == "deadbeef"


def test_collect_ci_for_commits_aggregates_and_dedups(monkeypatch: pytest.MonkeyPatch) -> None:
    # Same run url appears for two commit SHAs → must be deduped to one row.
    payload = (
        '[{"workflowName":"Backend CI","conclusion":"success",'
        '"status":"completed","url":"http://run/1","headSha":"aaa"}]'
    )
    monkeypatch.setattr(gsd, "_run", lambda *a, **k: payload)
    runs, available = gsd.collect_ci_for_commits(["aaa", "bbb"])
    assert available is True
    assert len(runs) == 1  # deduped by url


def test_collect_ci_for_commits_reports_gh_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gsd, "_run", lambda *a, **k: None)  # gh missing / unauth
    runs, available = gsd.collect_ci_for_commits(["aaa"])
    assert runs == []
    assert available is False  # distinguishes "gh unavailable" from "no runs"


def test_parse_features_handles_missing_and_malformed() -> None:
    assert gsd.parse_features(None) == []
    assert gsd.parse_features({}) == []
    assert gsd.parse_features({"features": "nope"}) == []
    feats = gsd.parse_features({"features": [{"id": "F1"}, "junk"]})
    assert len(feats) == 1
    assert feats[0].id == "F1"
    assert feats[0].title == ""  # missing key → empty string, no crash


def test_infer_batch_id() -> None:
    assert gsd.infer_batch_id("deadbeef\tchore(B098): open batch") == "B098"
    assert gsd.infer_batch_id("deadbeef\tno batch here") is None
    assert gsd.infer_batch_id(None) is None
    assert gsd.infer_batch_id("") is None


def test_collect_commits_filters_by_scope_not_body_mention() -> None:
    log = "\n".join(
        [
            "sha1\tfeat(B097-F001): x",
            "sha2\tchore(B096): y",
            "sha3\tfeat(B097-F002): z",
            "sha4\tchore(B098): B097(P3)done 后接手",  # body mention → must be EXCLUDED
            "sha5\tchore(env): B097+Planner 双重实测",  # body mention → must be EXCLUDED
            "sha6\tchore(B097): 开批",
        ]
    )
    commits = gsd.collect_commits("B097", log)
    assert [c.sha for c in commits] == ["sha1", "sha3", "sha6"]
    assert gsd.collect_commits("B097", None) == []


def test_run_returns_none_on_missing_binary() -> None:
    # A binary that does not exist must degrade to None, not raise.
    assert gsd._run(["this-binary-does-not-exist-xyz", "--nope"]) is None


@pytest.mark.parametrize("bad", ["{", "[", "null", ""])
def test_load_json_file_tolerates_bad(tmp_path: Path, bad: str) -> None:
    p = tmp_path / "x.json"
    p.write_text(bad, encoding="utf-8")
    assert gsd._load_json_file(p) is None
    assert gsd._load_json_file(tmp_path / "missing.json") is None
