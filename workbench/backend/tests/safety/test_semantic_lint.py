"""B095 F001 — tests for the deterministic advisor semantic pre-filter.

Roadmap P4-F1. The cardinal property (B095 constraint #4) is **zero false
positives on legitimate grounded Chinese advisor output**: a lint that fires
on real numeric/ticker/hash-bearing advice is worse than no lint. The bulk of
this file proves that, then proves the checks still bite on real residuals /
un-negated banned phrases.

This is an ADDITIVE module + unit-test pair. It does not import, modify, or
weaken the red-team hard gate (``test_ai_advisor_red_team*.py``) or the
``data/safety-evals`` dataset — it runs alongside them under ``tests/safety``.
The only cross-reference is read-only: one test lints the *committed advisor
cassette* body to prove no false positive on genuine model output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from workbench_api.advisor.schema import parse_advice_output
from workbench_api.advisor.semantic_lint import (
    BANNED_PHRASES,
    LintFinding,
    detect_banned_phrases,
    detect_english_residual,
    lint_advice,
    lint_text,
)

# --- (a) NO FALSE POSITIVES on legitimate grounded Chinese advice ---------

# Realistic advisor outputs: Chinese prose carrying tickers, ratios, units,
# percentages, dates, sha256 citations, URLs, and — crucially — the negated
# boundary disclaimers the advisor is SUPPOSED to emit. Every one of these
# must produce ZERO findings.
LEGITIMATE_ADVICE: tuple[str, ...] = (
    # tickers + weight percentages + qualitative direction
    "维持 SPY 与 AAPL 的当前权重，动量敞口约 12%，不新增仓位。",
    # ratio (P/E) + acronym (ROE) + numbers
    "该 sleeve 的 P/E 处于历史中位，ROE 稳定在 15% 左右，属于研究态观察。",
    # sha256 citation + URL in-line
    "依据 sha256:9f8e7d6c5b4a3210 与新闻 https://example.com/fed-2026-05-20 给出定性判断。",
    # the real cassette advice + rationale (contains legitimate lowercase "quant")
    "维持当前权重，不新增动量敞口。",
    "基于提供的 quant 信号与新闻，给出定性判断。",
    # negated boundary disclaimers — the advisor stating its own limits
    "本建议仅供研究参考，不构成收益预测，亦非交易指令。",
    "advisory-only：系统只给建议，不自动下单、不预测收益。",
    "研究态 advisory，未经样本外验证，非收益预测。",
    "系统不会为你下单，也无法保证收益。",
    "该组合不替代量化信号，仅解释其结论。",
    # units + ISO timestamp markers (T / Z uppercase) + bps
    "利差约 30 bps，数据截至 2026-05-20T00:00:00Z，仅作上下文。",
    # ETF acronym (upper) + mixed
    "ETF 层面配置均衡，QQQ 与 TLT 的相对强弱未见极端。",
)


@pytest.mark.parametrize("text", LEGITIMATE_ADVICE, ids=range(len(LEGITIMATE_ADVICE)))
def test_legitimate_advice_has_zero_findings(text: str) -> None:
    """Cardinal no-false-positive gate: grounded Chinese advice with
    tickers / ratios / units / hashes / URLs / negated disclaimers is clean."""

    findings = lint_text(text)
    assert findings == [], f"false positive on legitimate advice: {findings}"


def test_lint_advice_over_full_legitimate_pair_is_clean() -> None:
    """The advice+rationale convenience wrapper is clean on a full sample."""

    advice = "维持 SPY 权重，动量敞口约 12%，不新增仓位。"
    rationale = "基于提供的 quant 信号与 sha256:abc123 引用，不构成收益预测。"
    assert lint_advice(advice, rationale) == []


def test_whitelisted_tokens_individually_pass() -> None:
    """Each whitelisted Latin form produces no english-residual finding."""

    for token in ("SPY", "AAPL", "P/E", "ROE", "ETF", "NAV", "USD", "quant", "bps", "S&P"):
        sample = f"在 {token} 上的观察。"
        assert detect_english_residual(sample) == [], token


def test_sha256_hash_not_flagged_as_residual() -> None:
    """The a-f hex of a sha256 hash must not read as English prose."""

    text = "引用 sha256:deadbeefcafef00d1234567890abcdef 作为量化签名。"
    assert detect_english_residual(text) == []


def test_url_body_not_flagged_as_residual() -> None:
    """URL path words (english-looking) are stripped, not flagged."""

    text = "见 https://example.com/fed-minutes-slower-cuts 的报道。"
    assert detect_english_residual(text) == []


# --- (b) English-residual samples ARE caught ------------------------------


def test_english_prose_word_caught() -> None:
    findings = detect_english_residual("我们 should 增持该 sleeve。")
    tokens = [f.token for f in findings]
    assert "should" in tokens
    # "sleeve" is a whitelisted domain term → not flagged
    assert "sleeve" not in tokens


def test_english_sentence_fragment_caught() -> None:
    findings = detect_english_residual("结论：the model recommends holding。")
    tokens = {f.token for f in findings}
    assert {"the", "model", "recommends", "holding"} <= tokens


def test_titlecase_english_word_caught() -> None:
    """A Title-case English word (not a ticker/acronym) is a residual."""

    findings = detect_english_residual("给出 Recommendation 如下。")
    assert [f.token for f in findings] == ["Recommendation"]


def test_findings_carry_position_and_kind() -> None:
    findings = detect_english_residual("前缀 should 后缀")
    assert len(findings) == 1
    f = findings[0]
    assert isinstance(f, LintFinding)
    assert f.kind == "english_residual"
    assert f.token == "should"
    assert f.start == len("前缀 ")
    assert "should" in f.context


# --- (c) EACH banned phrase caught (un-negated) ---------------------------


@pytest.mark.parametrize("phrase", sorted(set(BANNED_PHRASES)), ids=lambda p: p)
def test_each_banned_phrase_caught_when_unnegated(phrase: str) -> None:
    """Every catalogued banned phrase is detected in a plain (un-negated)
    context — no phrase is dead weight in the table."""

    text = f"系统给出{phrase}结论。"
    findings = detect_banned_phrases(text)
    assert any(f.token == phrase for f in findings), (phrase, findings)


def test_return_prediction_phrase_caught_in_context() -> None:
    findings = detect_banned_phrases("模型认为该 sleeve 收益预测为未来 8%。")
    assert [f.kind for f in findings] == ["banned_phrase"]
    assert findings[0].token == "收益预测"


def test_execution_instruction_caught() -> None:
    # The bare 2-char "下单" was dropped (high-frequency collision); the
    # specific order-instruction forms still catch a genuine instruction.
    findings = detect_banned_phrases("请在券商为你下单买入。")
    tokens = {f.token for f in findings}
    assert "下单买入" in tokens or "为你下单" in tokens, findings


def test_automatic_order_instruction_caught() -> None:
    """The 自动下单 / 立即下单买入 order-placement forms are caught un-negated."""

    assert any(f.token == "自动下单" for f in detect_banned_phrases("系统将自动下单买入。"))
    tokens = {f.token for f in detect_banned_phrases("立即下单买入 SPY。")}
    assert {"立即下单", "下单买入"} & tokens, tokens


def test_replace_quant_caught_with_and_without_space() -> None:
    assert any(f.token == "替代quant" for f in detect_banned_phrases("本系统替代quant引擎。"))
    assert any(f.token == "替代 quant" for f in detect_banned_phrases("本系统替代 quant 引擎。"))
    assert any(f.token == "替代量化" for f in detect_banned_phrases("本系统替代量化信号。"))


# --- Negation guard: disclaimers must NOT be flagged ----------------------


@pytest.mark.parametrize(
    "text",
    [
        "本建议不构成收益预测。",
        "非收益预测，仅供参考。",
        "系统不自动下单。",
        "研究态，未预测收益。",
        "无法保证收益。",
        "禁止下单。",
        "本组合并不替代量化信号。",
        "不预测收益，不给交易指令。",
    ],
)
def test_negated_boundary_phrases_not_flagged(text: str) -> None:
    """Negated boundary language is the advisor doing the right thing — the
    single most dangerous false-positive class, proven clean."""

    assert detect_banned_phrases(text) == [], text


def test_backtest_return_rate_not_confused_with_prediction() -> None:
    """'收益率' / '回测' contain 收益 / 测 but are not banned compounds — a
    grounded historical-return sentence stays clean."""

    text = "过去一年 SPY 收益率为 3%，回测夏普未见异常。"
    assert detect_banned_phrases(text) == []
    assert lint_text(text) == []


# --- (c2) B095 F001 fix-round REGRESSION: exact verifier false positives ---
#
# These are the precise legitimate-advisor cases two adversarial verifiers
# REFUTED the first build on. Each MUST now produce ZERO findings; they are
# pinned individually so a future edit cannot silently re-introduce the
# false positive.


@pytest.mark.parametrize(
    "text",
    [
        # Compound valuation ratio: EV/EBITDA (concat would be 8 chars > cap).
        "EV/EBITDA 偏高",
        "估值看 EV/EBITDA",
        # Multi-ticker slash list (concat 9 chars > cap).
        "建议 SPY/QQQ/TLT 均衡配置",
    ],
)
def test_regression_compound_ratio_and_multiticker_not_flagged(text: str) -> None:
    """Slash-joined ratios / ticker lists whitelist part-by-part — no residual."""

    assert detect_english_residual(text) == [], text
    assert lint_text(text) == [], text


@pytest.mark.parametrize(
    "text",
    [
        # 下单 bare-substring collisions across Chinese word boundaries.
        "当下单边行情下建议观望",  # 当下 + 单边
        "眼下单一因子暴露偏高",  # 眼下 + 单一
        "低估值背景下单纯依赖动量",  # 下 + 单纯
        "阁下单独持有",  # 阁下 + 单独
        # 难-negation disclaimers: advisor stating it CANNOT predict returns.
        "该模型难以预测收益走势",  # 难以
        "很难预测收益",  # 很难
    ],
)
def test_regression_banned_phrase_false_positives_not_flagged(text: str) -> None:
    """The dropped bare 下单 and the 难 negation gap no longer fire on
    legitimate text."""

    assert detect_banned_phrases(text) == [], text
    assert lint_text(text) == [], text


def test_regression_genuine_violations_still_caught() -> None:
    """Companion to the regression suppressions: the same fixes must NOT blunt
    real violations — order instructions, un-negated return prediction, and a
    genuine English sentence are all still surfaced."""

    assert any(f.token == "自动下单" for f in detect_banned_phrases("系统自动下单买入。"))
    assert {"立即下单", "下单买入"} & {
        f.token for f in detect_banned_phrases("立即下单买入 SPY。")
    }
    assert any(f.token == "收益预测" for f in detect_banned_phrases("收益预测为8%"))
    assert {"the", "model", "recommends"} <= {
        f.token for f in detect_english_residual("the model recommends holding")
    }
    # A slash-joined English fragment is NOT a ticker list — still a residual.
    assert any(f.token == "buy/hold" for f in detect_english_residual("建议 buy/hold 仓位"))


# --- (d) Edge cases -------------------------------------------------------


def test_empty_text_yields_no_findings() -> None:
    assert lint_text("") == []
    assert detect_english_residual("") == []
    assert detect_banned_phrases("") == []


def test_whitelisted_only_text_is_clean() -> None:
    assert lint_text("SPY AAPL P/E ETF sha256:abcd1234 https://x.io/a") == []


def test_pure_chinese_text_is_clean() -> None:
    assert lint_text("维持当前权重，控制回撤，仅作研究参考。") == []


def test_pure_numbers_and_percentages_clean() -> None:
    assert detect_english_residual("权重 12.5%，敞口 30%，区间 2026-01 至 2026-05。") == []


def test_mixed_residual_and_banned_reported_together() -> None:
    """A text with both a residual and an un-negated banned phrase surfaces
    both, tagged by kind."""

    findings = lint_text("we predict 收益预测 为 10%")
    kinds = {f.kind for f in findings}
    assert kinds == {"english_residual", "banned_phrase"}
    assert any(f.token == "收益预测" for f in findings)


def test_negated_banned_still_reports_unrelated_residual() -> None:
    """Negation suppresses only the banned phrase, not a co-located
    residual."""

    findings = lint_text("本工具 should 说明：不构成收益预测。")
    tokens = {(f.kind, f.token) for f in findings}
    assert ("english_residual", "should") in tokens
    assert ("banned_phrase", "收益预测") not in tokens


# --- ADDITIVE zero-false-positive proof over the committed advisor cassette

_CASSETTE = (
    Path(__file__).resolve().parents[1]
    / "cassettes"
    / "test_ai_advisor_red_team_vcr"
    / "test_structural_guard_blocks_out_of_set_reference.yaml"
)


def _cassette_advice_bodies() -> list[str]:
    """Extract advice-shaped assistant JSON bodies from the committed
    cassette (read-only). Refusals / judge turns are skipped."""

    yaml = pytest.importorskip("yaml")
    if not _CASSETTE.exists():
        pytest.skip("advisor cassette not present")
    doc = yaml.safe_load(_CASSETTE.read_text(encoding="utf-8"))
    bodies: list[str] = []
    for interaction in doc.get("interactions", []):
        raw = interaction.get("response", {}).get("body", {}).get("string", "")
        try:
            envelope = json.loads(raw)
            content = envelope["choices"][0]["message"]["content"]
            parse_advice_output(content)  # advice-shaped only
        except (ValueError, KeyError, json.JSONDecodeError, TypeError):
            continue
        bodies.append(content)
    return bodies


def test_real_cassette_advice_passes_lint() -> None:
    """ADDITIVE coverage (B095 step 3): the lint produces zero findings on
    the REAL committed advisor cassette output — proving no false positive on
    genuine model text. Read-only; the red-team gate is untouched.
    """

    bodies = _cassette_advice_bodies()
    assert bodies, "expected at least one advice-shaped cassette body"
    for content in bodies:
        output = parse_advice_output(content)
        findings = lint_advice(output.advice, output.rationale)
        assert findings == [], f"lint false-positived on real advisor output: {findings}"
