from __future__ import annotations

from scripts.test import ashare_as_filed_data_pilot as sut


def test_clean_title_removes_highlight_markup_and_space() -> None:
    assert sut.clean_title("2024年<em>第一季度报告</em> ") == "2024年第一季度报告"


def test_regular_title_rejects_summary_revision_and_notice() -> None:
    pattern = r"年(?:第)?一季度报告"
    assert sut.is_regular_report_title("公司2024年第一季度报告", 2024, pattern)
    assert not sut.is_regular_report_title("2024年第一季度报告（更正后）", 2024, pattern)
    assert not sut.is_regular_report_title("关于2024年第一季度报告的公告", 2024, pattern)
    assert not sut.is_regular_report_title("2024年第一季度报告摘要", 2024, pattern)
    assert not sut.is_regular_report_title("公司H股公告-2024年第一季度报告", 2024, pattern)
    assert not sut.is_regular_report_title("2024年第一季度报告（更新后）", 2024, pattern)


def test_extract_parent_profit_survives_pdf_line_wrap() -> None:
    text = """
    归属于上市公司股东的净利
                10,919,621.90  15,192,356.22 -28.12%
    润（元）
    """
    assert sut.extract_number_after_label(text, sut.PARENT_PROFIT_LABEL) == 10_919_621.90


def test_extract_numbers_from_standard_table_rows() -> None:
    text = """
    归属于上市公司股东的净利润（元）  10,919,621.90 15,192,356.22
    基本每股收益（元/股） 0.0475 0.0667
    """
    assert sut.extract_number_after_label(text, sut.PARENT_PROFIT_LABEL) == 10_919_621.90
    assert sut.extract_number_after_label(text, sut.BASIC_EPS_LABEL) == 0.0475


def test_q3_parent_profit_uses_ytd_column_and_unit_scale() -> None:
    text = """
    单位：千元
    归属于上市公司股东的净利润 677,519 1,200,000 -43.54% 3,674,784 4,200,000 -12.51%
    """
    result = sut.extract_parent_profit(text, "q3")
    assert result["raw_value"] == 3_674_784
    assert result["value"] == 3_674_784_000
    assert result["unit"] == "千元"


def test_consolidated_income_statement_is_preferred_to_q3_highlights() -> None:
    text = """
    单位：元
    归属于上市公司股东的净利润 10 9 -1% 30 20 50%
    合并利润表 金额单位：人民币千元
    归属于母公司所有者的净利润 3,674,784 4,200,000
    """
    result = sut.extract_parent_profit(text, "q3")
    assert result["source_label"] == "split_consolidated_income_statement"
    assert result["value"] == 3_674_784_000


def test_split_consolidated_q3_row_uses_ytd_value() -> None:
    text = """
    合并利润表 单位：元 币种：人民币
    五、净利润 16,558,112.04 -6,598,390.40 3,728,547.23 -18,154,758.60
    归属于母公司所有者 20,354,873.06 -4,330,550.82 11,598,106.62 -11,894,649.75
    的净利润
    少数股东损益 -3,796,761.02 -2,267,839.58 -7,869,559.39 -6,260,108.85
    """
    result = sut.extract_parent_profit(text, "q3")
    assert result["source_label"] == "split_consolidated_income_statement"
    assert result["value"] == 11_598_106.62


def _document(*, revision: bool = False, hash_value: str = "a") -> dict:
    corrected = revision and hash_value == "corrected"
    return {
        "bucket": "revision-pair" if revision else "2019-q1",
        "announcement_id": hash_value,
        "announcement_time_ms": 2 if corrected else 1,
        "sec_code": "300691" if revision else "600000",
        "org_id": "9900032804" if revision else "gssh0600000",
        "report_period": "2024-03-31" if revision else "2019-03-31",
        "title": (
            "2024年第一季度报告（更正后）"
            if corrected
            else "2024年一季度报告"
        ),
        "pdf_sha256": hash_value,
        "valid_pdf": True,
        "text_chars": 1_000,
        "parent_profit_label": True,
        "parent_profit_value": 100.0,
        "basic_eps_label": True,
        "basic_eps_value": 1.0,
        "current_snapshot_match_05pct": True,
    }


def test_evaluate_pilot_requires_exact_sample_and_distinct_revision_versions() -> None:
    documents = [_document(hash_value=f"regular-{index}") for index in range(48)]
    documents += [
        _document(revision=True, hash_value="original"),
        _document(revision=True, hash_value="corrected"),
    ]
    result = sut.evaluate_pilot(documents)
    assert result["pilot_pass"]
    assert result["pilot_verdict"] == "AS_FILED_ARCHIVE_PILOT_GO"
    assert result["archive_acquisition_pass"]
    assert result["structured_extraction_qa_pass"]
    assert result["ep_signal_data_ready"] is False
    assert result["cny_2_1m_portfolio_backtest_allowed"] is False


def test_evaluate_pilot_fails_when_text_extraction_is_sparse() -> None:
    documents = [_document(hash_value=f"regular-{index}") for index in range(48)]
    documents += [
        _document(revision=True, hash_value="original"),
        _document(revision=True, hash_value="corrected"),
    ]
    for document in documents[:6]:
        document["text_chars"] = 0
        document["parent_profit_label"] = False
        document["parent_profit_value"] = None
    result = sut.evaluate_pilot(documents)
    assert result["pilot_pass"] is False
    assert result["pilot_verdict"] == "AS_FILED_ARCHIVE_PILOT_NO_GO"
    assert result["archive_acquisition_pass"] is False


def test_evaluate_pilot_rejects_revision_pair_from_different_company() -> None:
    documents = [_document(hash_value=f"regular-{index}") for index in range(48)]
    documents += [
        _document(revision=True, hash_value="original"),
        _document(revision=True, hash_value="corrected"),
    ]
    documents[-1]["sec_code"] = "300692"
    result = sut.evaluate_pilot(documents)
    assert result["archive_acquisition_pass"] is False
    assert result["pilot_verdict"] == "AS_FILED_ARCHIVE_PILOT_NO_GO"


def test_current_snapshot_match_blocks_structured_extraction_readiness() -> None:
    documents = [_document(hash_value=f"regular-{index}") for index in range(48)]
    documents += [
        _document(revision=True, hash_value="original"),
        _document(revision=True, hash_value="corrected"),
    ]
    for document in documents:
        document["current_snapshot_match_05pct"] = False
    result = sut.evaluate_pilot(documents)
    assert result["archive_acquisition_pass"]
    assert result["structured_extraction_qa_pass"] is False
    assert result["pilot_pass"] is False
    assert result["pilot_verdict"] == "ARCHIVE_ACQUISITION_GO_EXTRACTION_QA_NO_GO"


def test_structured_extraction_qa_accepts_exact_95pct_boundary() -> None:
    documents = [_document(hash_value=f"regular-{index}") for index in range(48)]
    documents += [
        _document(revision=True, hash_value="original"),
        _document(revision=True, hash_value="corrected"),
    ]
    for document in documents[:10]:
        document["current_snapshot_match_05pct"] = None
    for document in documents[10:12]:
        document["current_snapshot_match_05pct"] = False
    result = sut.evaluate_pilot(documents)
    assert result["metrics"]["current_snapshot_comparable"] == 40
    assert result["metrics"]["current_snapshot_match_fraction"] == 0.95
    assert result["structured_extraction_qa_pass"]
    assert result["pilot_pass"]


def test_structured_extraction_qa_requires_30_comparable_documents() -> None:
    documents = [_document(hash_value=f"regular-{index}") for index in range(48)]
    documents += [
        _document(revision=True, hash_value="original"),
        _document(revision=True, hash_value="corrected"),
    ]
    for document in documents[29:]:
        document["current_snapshot_match_05pct"] = None
    result = sut.evaluate_pilot(documents)
    assert result["metrics"]["current_snapshot_comparable"] == 29
    assert result["metrics"]["current_snapshot_match_fraction"] == 1.0
    assert result["structured_extraction_qa_pass"] is False
    assert result["pilot_verdict"] == "ARCHIVE_ACQUISITION_GO_EXTRACTION_QA_NO_GO"
