"""B108 F002 — 抽样 manifest 的规范序列化与哈希。

**确定性与溯源分成两个文件**：

- ``manifest.json``   只含选择结果与选择参数，**不含任何时间戳**，
  因此同 seed 同候选池两次运行产出**逐字节相同**的文件。
- ``provenance.json`` 承载抓取时间、查询参数、逐层覆盖诊断这些必然变化的信息。

如果把 ``generated_at`` 塞进 manifest，「两次运行 sha256 一致」就永远不可能成立，
只能退而求其次去比较「除时间戳外的部分」——那等于把可复现性的验收口子开在自己身上。
分成两个文件后，acceptance 里那条「实测跑两次比对 sha256」可以字面成立。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.research.ashare_ep.sampling import Candidate

MANIFEST_SCHEMA_VERSION = "b108-sample-manifest-v1"


def _canonical_json(payload: dict[str, Any]) -> str:
    """规范 JSON：键排序、无多余空白、非 ASCII 原样保留。

    序列化参数必须固定，否则同样的数据在不同调用点会产生不同字节，哈希失去意义。
    """
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_manifest(
    selected: list[Candidate],
    *,
    seed: int,
    quota_per_stratum: int,
    years: tuple[int, ...],
    report_types: tuple[str, ...],
    excluded_manifest: str | None = None,
) -> dict[str, Any]:
    """构造确定性 manifest。**不含时间戳**（见模块 docstring）。"""
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "selection_params": {
            "seed": seed,
            "quota_per_stratum": quota_per_stratum,
            "years": list(years),
            "report_types": list(report_types),
            "excluded_manifest": excluded_manifest,
        },
        "count": len(selected),
        "items": [
            {
                "announcement_id": item.announcement_id,
                "sec_code": item.sec_code,
                "board": item.board,
                "year": item.year,
                "report_type": item.report_type,
                "report_period": item.report_period,
                "title": item.title,
                "url": item.url,
            }
            for item in selected
        ],
    }


def manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """manifest 的最终字节形态——**写文件和算哈希必须用同一个来源**。"""
    return (_canonical_json(manifest) + "\n").encode("utf-8")


def manifest_sha256(manifest: dict[str, Any]) -> str:
    """manifest 文件的 sha256，等于 ``shasum -a 256 <file>`` 的结果。

    ★E09 修复：原实现写文件时补了 ``\\n``、算哈希时却用不含 ``\\n`` 的规范串，
    于是 CLI 打印的 sha256 与文件实际哈希不等——偏偏这个值的唯一用途就是
    「冻结后核验」，不等价意味着核验动作本身在骗人。
    """
    return hashlib.sha256(manifest_bytes(manifest)).hexdigest()


def write_manifest(manifest: dict[str, Any], path: Path) -> str:
    """写出 manifest，返回其 sha256（与文件字节一致）。同输入必然同字节。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(manifest_bytes(manifest))
    return manifest_sha256(manifest)


def load_excluded_ids(path: Path) -> frozenset[str]:
    """从既有 manifest 读出要排除的公告 ID。

    同时接受本模块的 manifest 格式和 pilot 时代的 JSON 报告格式——已烧掉的 50 份存在
    后者里，排除它们是 H2 的硬要求，不能因为格式不同就漏掉。
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    ids: set[str] = set()

    for item in payload.get("items", []) or []:
        if announcement_id := item.get("announcement_id"):
            ids.add(str(announcement_id))

    # pilot 报告把逐份结果放在 documents[] 下
    for item in payload.get("documents", []) or []:
        if announcement_id := item.get("announcement_id"):
            ids.add(str(announcement_id))

    if not ids:
        raise ValueError(
            f"{path} 里没有解析出任何 announcement_id——"
            "排除清单为空会让已烧掉的样本重新进入 holdout，拒绝继续"
        )
    return frozenset(ids)


def build_pdf_freeze(
    manifest: dict[str, Any],
    pdf_dir: Path,
    *,
    suffix: str = ".pdf",
) -> dict[str, Any]:
    """把已下载 PDF 的字节哈希冻结成记录。

    ★E11 修复：抽样 manifest 只锁定「抽了哪些公告」，不锁定「评测的是哪些字节」。
    巨潮同一公告 ID 换 hash 是上游报告 §4.3 明确要求报警的情形；没有这一层，
    复评时无法证明用的还是同一批文件。抽样阶段拿不到哈希（不下载），
    所以这一步由下载方（F003）在下载后调用。

    缺文件不是静默跳过——记为 ``missing``，让复评方看得见。
    """
    entries: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in manifest.get("items", []):
        announcement_id = str(item["announcement_id"])
        path = pdf_dir / f"{announcement_id}{suffix}"
        if not path.exists():
            missing.append(announcement_id)
            continue
        payload = path.read_bytes()
        entries.append(
            {
                "announcement_id": announcement_id,
                "sec_code": item.get("sec_code"),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return {
        "manifest_sha256": manifest_sha256(manifest),
        "pdf_count": len(entries),
        "missing_count": len(missing),
        "missing": sorted(missing),
        "pdfs": sorted(entries, key=lambda entry: str(entry["announcement_id"])),
    }


def build_provenance(
    *,
    manifest_hash: str,
    generated_at: str,
    query_diagnostics: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    candidate_pool_size: int,
) -> dict[str, Any]:
    """溯源信息。这些字段每次运行都会变，故与 manifest 分开存放。"""
    return {
        "manifest_sha256": manifest_hash,
        "generated_at": generated_at,
        "candidate_pool_size": candidate_pool_size,
        "query_diagnostics": query_diagnostics,
        "stratum_coverage": coverage,
    }


def write_provenance(provenance: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(provenance, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
