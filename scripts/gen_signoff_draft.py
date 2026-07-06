#!/usr/bin/env python
"""B098 F001 — signoff DRAFT auto-scaffolder (mechanical parts only, 铁律#4-safe).

Fills the **mechanical scaffold** of an evaluator signoff from batch state that is
*mechanically extractable* from git / gh / progress.json / features.json:

  - batch id + feature list (id, title, executor, status)
  - 被验收 commit SHAs + one-line subjects
  - changed-files list + git diff --stat
  - CI conclusions per workflow (gh run list --commit <head_sha>)
  - gates echoed from progress.json generator_handoff (if present)
  - production surface: a raw file-LOCATION heuristic (runtime dirs vs docs/test/research)

★ CARDINAL 铁律#4 CONSTRAINT — this tool NEVER fills, guesses, or implies a
verdict / 裁定 / 命门 judgment / risk grading / soft-watch grade. Every judgment
section is emitted as an EXPLICIT ``[待独立评估填写：...]`` placeholder for the
independent evaluator. In particular ``render_judgment_sections`` takes NO batch
state at all — it structurally *cannot* infer a verdict from green CI. The tool is
generator scaffolding infrastructure; it does NOT evaluate.

Read-only: shells out to git / gh with read-only commands; writes nothing to repo
state. Missing data degrades to a placeholder — it never crashes.

Usage::

    python scripts/gen_signoff_draft.py                 # infer batch from latest commit
    python scripts/gen_signoff_draft.py --batch B097    # explicit batch id
    python scripts/gen_signoff_draft.py --batch B097 -o draft.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Judgment-section placeholder template. ``label`` names the missing judgment.
JUDGMENT_PLACEHOLDER = "[待独立评估填写：{label}]"

#: Mechanical-fact placeholder (data unavailable / not reported), distinct from
#: the judgment placeholder so a reader can tell "no data" from "needs judgment".
DATA_PLACEHOLDER = "[数据缺失 — 无法机械提取]"

#: File-path prefixes treated as *runtime / production* surface. This is a raw
#: LOCATION fact used only to bucket changed files — NOT a risk verdict.
RUNTIME_PREFIXES: tuple[str, ...] = (
    "trade/",
    "workbench/backend/workbench_api/",
    "workbench/frontend/src/",
    "workbench/frontend/app/",
    ".github/workflows/",
    "workbench/deploy/",
)

#: File-path prefixes that are docs / tests / research (non-runtime surface).
NON_RUNTIME_PREFIXES: tuple[str, ...] = (
    "docs/",
    "tests/",
    "test/",
    "scripts/research/",
    ".auto-memory/",
    "framework/",
    "design-draft/",
)


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Feature:
    """One features.json entry (mechanical fields only)."""

    id: str
    title: str
    executor: str
    status: str


@dataclass(frozen=True)
class Commit:
    """One git commit belonging to the batch."""

    sha: str
    subject: str


@dataclass(frozen=True)
class CIRun:
    """One gh run-list row (raw gh conclusions, echoed verbatim)."""

    workflow: str
    conclusion: str  # gh vocabulary: success/failure/cancelled/"" — NOT PASS/FAIL
    status: str
    url: str
    head_sha: str = ""


@dataclass(frozen=True)
class BatchState:
    """Everything mechanically collected for a batch. No judgment lives here."""

    batch_id: str
    features: list[Feature]
    commits: list[Commit]
    diffstat: str | None
    changed_files: list[str]
    ci_runs: list[CIRun]
    head_sha: str | None
    generator_handoff: dict[str, object] | None
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Read-only shell helpers (impure, but never mutate repo state)
# --------------------------------------------------------------------------- #


def _run(cmd: list[str], cwd: Path = REPO_ROOT, timeout: int = 30) -> str | None:
    """Run a read-only command, returning stdout or ``None`` on any failure.

    Never raises: a missing binary, non-zero exit, or timeout all degrade to
    ``None`` so callers can fall back to placeholders.
    """
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _load_json_file(path: Path) -> dict[str, object] | None:
    """Load a JSON object from disk, returning ``None`` on any error."""
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


# --------------------------------------------------------------------------- #
# Collection (mechanical extraction)
# --------------------------------------------------------------------------- #


_BATCH_RE = re.compile(r"\bB\d{2,}\b")


def infer_batch_id(log_text: str | None) -> str | None:
    """Infer the batch id from the most recent commit subject that names one."""
    if not log_text:
        return None
    for line in log_text.splitlines():
        match = _BATCH_RE.search(line)
        if match:
            return match.group(0)
    return None


def collect_commits(batch_id: str, log_text: str | None) -> list[Commit]:
    """Filter ``git log`` (``<sha>\\t<subject>`` lines) to this batch's commits.

    Matches the batch id inside the conventional-commit scope — ``type(B097): ``
    or ``type(B097-F001): `` — NOT mere body mentions (e.g. a later batch that
    references ``B097(P3)done`` in its message). Returned newest-first (git log
    order preserved).
    """
    commits: list[Commit] = []
    if not log_text:
        return commits
    scope = re.compile(rf"\({re.escape(batch_id)}\b")
    for line in log_text.splitlines():
        sha, _, subject = line.partition("\t")
        if sha and scope.search(subject):
            commits.append(Commit(sha=sha.strip(), subject=subject.strip()))
    return commits


def parse_ci_runs(json_text: str | None) -> list[CIRun]:
    """Parse ``gh run list --json ...`` output into CIRun rows."""
    if not json_text:
        return []
    try:
        rows = json.loads(json_text)
    except ValueError:
        return []
    if not isinstance(rows, list):
        return []
    runs: list[CIRun] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        runs.append(
            CIRun(
                workflow=str(row.get("workflowName", "") or ""),
                conclusion=str(row.get("conclusion", "") or ""),
                status=str(row.get("status", "") or ""),
                url=str(row.get("url", "") or ""),
                head_sha=str(row.get("headSha", "") or ""),
            )
        )
    return runs


def collect_ci_for_commits(shas: list[str]) -> tuple[list[CIRun], bool]:
    """Query ``gh run list`` for each commit SHA; aggregate + dedup by url.

    Returns ``(runs, gh_available)``. ``gh_available`` is False if gh could not
    be invoked at all (missing binary / not authenticated) so the caller can
    emit a placeholder instead of implying "no runs exist".
    """
    aggregated: list[CIRun] = []
    seen_urls: set[str] = set()
    gh_available = False
    for sha in shas:
        out = _run(
            [
                "gh",
                "run",
                "list",
                "--commit",
                sha,
                "--json",
                "workflowName,conclusion,status,url,headSha",
            ]
        )
        if out is None:
            continue
        gh_available = True
        for run in parse_ci_runs(out):
            key = run.url or f"{run.head_sha}:{run.workflow}"
            if key in seen_urls:
                continue
            seen_urls.add(key)
            aggregated.append(run)
    return aggregated, gh_available


def parse_features(data: dict[str, object] | None) -> list[Feature]:
    """Extract features (id/title/executor/status) from features.json data."""
    if not data:
        return []
    raw = data.get("features")
    if not isinstance(raw, list):
        return []
    features: list[Feature] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        features.append(
            Feature(
                id=str(item.get("id", "") or ""),
                title=str(item.get("title", "") or ""),
                executor=str(item.get("executor", "") or ""),
                status=str(item.get("status", "") or ""),
            )
        )
    return features


def classify_changed_files(files: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Bucket changed files by LOCATION only (raw fact, not a risk verdict).

    Returns ``(runtime, non_runtime, other)`` — files matching a runtime prefix,
    a non-runtime prefix, or neither. Non-runtime is checked first so that e.g.
    ``tests/`` under any tree lands in non-runtime.
    """
    runtime: list[str] = []
    non_runtime: list[str] = []
    other: list[str] = []
    for path in files:
        if path.startswith(NON_RUNTIME_PREFIXES):
            non_runtime.append(path)
        elif path.startswith(RUNTIME_PREFIXES):
            runtime.append(path)
        else:
            other.append(path)
    return runtime, non_runtime, other


def collect_batch_state(batch_id: str | None) -> BatchState:
    """Gather all mechanical facts for ``batch_id`` (or infer it). Never raises."""
    notes: list[str] = []

    log_text = _run(["git", "log", "--pretty=format:%H%x09%s", "-n", "800"])
    if log_text is None:
        notes.append("git log 不可用（非 git 仓库或 git 缺失）")

    resolved = batch_id or infer_batch_id(log_text)
    if resolved is None:
        resolved = "UNKNOWN"
        notes.append("无法确定批次 id（未提供 --batch 且日志中无 B<NNN> 标记）")

    commits = collect_commits(resolved, log_text)
    if not commits:
        notes.append(f"未找到含 {resolved} 的 commit")

    head_sha: str | None = commits[0].sha if commits else None

    diffstat: str | None = None
    changed_files: list[str] = []
    if commits:
        oldest = commits[-1].sha
        newest = commits[0].sha
        rev_range = f"{oldest}^..{newest}"
        diffstat = _run(["git", "diff", "--stat", rev_range])
        names = _run(["git", "diff", "--name-only", rev_range])
        if names is not None:
            changed_files = [ln.strip() for ln in names.splitlines() if ln.strip()]
        else:
            notes.append("git diff --name-only 失败（首个 commit 无父节点？）")

    ci_runs: list[CIRun] = []
    if commits:
        ci_runs, gh_available = collect_ci_for_commits([c.sha for c in commits])
        if not gh_available:
            notes.append("gh run list 不可用（gh 缺失/未认证/无网络）— CI 结论留占位")
        elif not ci_runs:
            notes.append("本批次所有 commit 均无 CI run 记录（多为 paths-ignore chore commit）")

    features = parse_features(_load_json_file(REPO_ROOT / "features.json"))
    progress = _load_json_file(REPO_ROOT / "progress.json")
    handoff_obj = progress.get("generator_handoff") if progress else None
    generator_handoff = handoff_obj if isinstance(handoff_obj, dict) else None

    return BatchState(
        batch_id=resolved,
        features=features,
        commits=commits,
        diffstat=diffstat,
        changed_files=changed_files,
        ci_runs=ci_runs,
        head_sha=head_sha,
        generator_handoff=generator_handoff,
        notes=notes,
    )


# --------------------------------------------------------------------------- #
# Rendering — MECHANICAL sections (facts only)
# --------------------------------------------------------------------------- #


def _md_escape(text: str) -> str:
    """Escape pipe characters so free text does not break markdown tables."""
    return text.replace("|", "\\|")


def render_header(state: BatchState) -> str:
    lines = [
        f"# {state.batch_id} — Evaluator Signoff（草稿 / DRAFT）",
        "",
        "> ⚠️ **本文件由 `scripts/gen_signoff_draft.py` 自动生成，仅含机械可提取的事实。**",
        "> 所有 **裁定 / 命门 / 软观察 / 框架 learnings** 段落均为占位符，"
        "必须由 **独立 evaluator** 亲自填写（守铁律#4：本工具是辅助脚手架，**不做任何评估**）。",
        f"> head_sha：`{state.head_sha or DATA_PLACEHOLDER}`",
    ]
    return "\n".join(lines)


def render_features(state: BatchState) -> str:
    lines = ["## 1. 批次与 feature（机械提取自 features.json）", ""]
    if not state.features:
        lines.append(DATA_PLACEHOLDER)
        return "\n".join(lines)
    lines.append("| feature | 标题 | executor | status |")
    lines.append("|---|---|---|---|")
    for feat in state.features:
        lines.append(
            f"| {_md_escape(feat.id)} | {_md_escape(feat.title)} "
            f"| {_md_escape(feat.executor)} | {_md_escape(feat.status)} |"
        )
    return "\n".join(lines)


def render_commits(state: BatchState) -> str:
    lines = ["## 2. 被验收 commit（机械提取自 git log）", ""]
    if not state.commits:
        lines.append(DATA_PLACEHOLDER)
        return "\n".join(lines)
    lines.append("| SHA | 一行消息 |")
    lines.append("|---|---|")
    for commit in state.commits:
        lines.append(f"| `{commit.sha[:10]}` | {_md_escape(commit.subject)} |")
    return "\n".join(lines)


def render_changed_files(state: BatchState) -> str:
    lines = ["## 3. 改动文件与 diff scope（机械提取自 git diff --stat）", ""]
    if not state.changed_files and not state.diffstat:
        lines.append(DATA_PLACEHOLDER)
        return "\n".join(lines)
    if state.diffstat:
        lines.append("```")
        lines.append(state.diffstat.rstrip())
        lines.append("```")
    else:
        lines.append(f"改动文件（{len(state.changed_files)} 个）：")
        lines.append("")
        for path in state.changed_files:
            lines.append(f"- `{path}`")
    return "\n".join(lines)


def render_ci(state: BatchState) -> str:
    lines = [
        "## 4. CI 结论（机械提取自 `gh run list`，echo gh 原始 conclusion）",
        "",
        "> 下表 conclusion 列为 gh 的机械结论字段（success/failure/…），"
        "**非本工具或 evaluator 的裁定**。",
        "",
    ]
    if not state.ci_runs:
        lines.append(DATA_PLACEHOLDER)
        return "\n".join(lines)
    lines.append("| commit | workflow | status | conclusion (gh) | url |")
    lines.append("|---|---|---|---|---|")
    for run in state.ci_runs:
        conclusion = run.conclusion or "(空)"
        sha = run.head_sha[:10] if run.head_sha else "?"
        lines.append(
            f"| `{sha}` | {_md_escape(run.workflow)} | {_md_escape(run.status)} "
            f"| `{_md_escape(conclusion)}` | {_md_escape(run.url)} |"
        )
    return "\n".join(lines)


def render_gates(state: BatchState) -> str:
    lines = [
        "## 5. 门禁（echo 自 progress.json `generator_handoff`，未重跑/未复核）",
        "",
        "> 以下数字为 generator **自报**，本工具原样 echo，**未独立复跑、未判定真伪**。",
        "> 独立复跑与判定属 evaluator 职责（见判断段）。",
        "",
    ]
    handoff = state.generator_handoff
    if not handoff:
        lines.append(f"generator_handoff 缺失或为空 → {DATA_PLACEHOLDER}")
        return "\n".join(lines)
    # Echo whatever keys are present without interpreting them.
    lines.append("```json")
    lines.append(json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True))
    lines.append("```")
    return "\n".join(lines)


def render_production_surface(state: BatchState) -> str:
    lines = [
        "## 6. 生产面（文件位置启发式 — 原始 LOCATION 事实，非风险裁定）",
        "",
        "> 仅按文件路径前缀分桶，回答「改了哪些位置」这一机械事实；"
        "**是否构成生产风险 = evaluator 判断**（见判断段命门）。",
        "",
    ]
    if not state.changed_files:
        lines.append(DATA_PLACEHOLDER)
        return "\n".join(lines)
    runtime, non_runtime, other = classify_changed_files(state.changed_files)

    def _bucket(title: str, paths: list[str]) -> None:
        lines.append(f"**{title}（{len(paths)}）：**")
        if paths:
            for path in paths:
                lines.append(f"- `{path}`")
        else:
            lines.append("- （无）")
        lines.append("")

    _bucket("runtime / 生产路径前缀命中", runtime)
    _bucket("docs / test / research 前缀命中", non_runtime)
    _bucket("其它（未归类前缀）", other)
    return "\n".join(lines).rstrip()


# --------------------------------------------------------------------------- #
# Rendering — JUDGMENT sections (ALWAYS placeholders; take NO batch state)
# --------------------------------------------------------------------------- #


def render_judgment_sections() -> str:
    """Emit the judgment scaffold as pure placeholders.

    ★ This function deliberately takes **no arguments**. Judgment is NEVER a
    function of CI/git/features state — so this tool structurally cannot infer a
    verdict from green CI. The independent evaluator fills every placeholder.
    """
    return "\n".join(
        [
            "## 7. 裁定（★独立评估填写，本工具不预填）",
            "",
            JUDGMENT_PLACEHOLDER.format(label="总体裁定 + 逐 feature 结论"),
            "",
            "## 8. 命门识别与独立复核（★独立评估填写）",
            "",
            JUDGMENT_PLACEHOLDER.format(label="命门与独立复核（最高怀疑度，独立复算/脱敏扫描/离线复跑）"),
            "",
            "## 9. 软观察（★独立评估填写，非阻断项分级由 evaluator 定）",
            "",
            JUDGMENT_PLACEHOLDER.format(label="软观察（soft-watch 分级 / flake-vs-real 判定）"),
            "",
            "## 10. 框架 learnings（★独立评估填写）",
            "",
            JUDGMENT_PLACEHOLDER.format(label="框架 learnings / proposed-learnings"),
        ]
    )


def render_notes(state: BatchState) -> str:
    if not state.notes:
        return ""
    lines = ["## 附录：机械提取告警（数据缺失说明）", ""]
    for note in state.notes:
        lines.append(f"- {note}")
    return "\n".join(lines)


def render_draft(state: BatchState) -> str:
    """Assemble the full markdown draft: mechanical facts + judgment placeholders."""
    sections = [
        render_header(state),
        render_features(state),
        render_commits(state),
        render_changed_files(state),
        render_ci(state),
        render_gates(state),
        render_production_surface(state),
        "---",
        "# 以下为判断段：本工具一律留白，由独立 evaluator 填写",
        render_judgment_sections(),
    ]
    notes = render_notes(state)
    if notes:
        sections.extend(["---", notes])
    return "\n\n".join(section for section in sections if section) + "\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Auto-scaffold the MECHANICAL parts of an evaluator signoff draft "
            "(铁律#4-safe: judgment sections are always placeholders)."
        )
    )
    parser.add_argument(
        "--batch",
        default=None,
        help="Batch id (e.g. B097). If omitted, inferred from the latest commit subject.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Write the draft to this file instead of stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    state = collect_batch_state(args.batch)
    draft = render_draft(state)
    if args.output:
        Path(args.output).write_text(draft, encoding="utf-8")
        sys.stderr.write(f"signoff draft written to {args.output}\n")
    else:
        sys.stdout.write(draft)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
