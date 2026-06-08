# arXiv and SSRN Research Candidates

Collection date: 2026-05-13

This document records arXiv downloads and SSRN-related discovery attempts for strategy research. It distinguishes verified local PDFs from candidates and metadata-only entries. No paywall, login wall, session control, or `403` response was bypassed.

## arXiv PDFs Downloaded

These files were downloaded from arXiv public PDF URLs and validated with `pdfinfo`.

| Local File | arXiv ID | Title | Authors | Project Relevance | Notes |
|---|---|---|---|---|---|
| `arxiv-introduction-risk-parity-budgeting.pdf` | `1403.1889v1` | Introduction to Risk Parity and Budgeting | Thierry Roncalli | Risk parity foundations, risk budgeting terminology, long-term allocation framing. | Long tutorial-style reference; useful for conceptual grounding, not direct MVP implementation. |
| `arxiv-mad-risk-parity.pdf` | `2110.12282v2` | MAD Risk Parity Portfolios | Cagin Ararat, Francesco Cesarone, Mustafa Celebi Pinar, Jacopo Maria Ricci | Alternative risk measure for risk parity. | Useful for later robustness tests beyond volatility-based MVP. |
| `arxiv-portfolio-optimization-evar.pdf` | `1708.05713v1` | Portfolio Optimization with Entropic Value-at-Risk | Amir Ahmadi-Javid, Malihe Fallah-Tafti | Tail-risk-aware portfolio optimization. | Relevant to future downside-risk constraints; more complex than current MVP. |
| `arxiv-factor-momentum.pdf` | `2009.04824v1` | Is Factor Momentum More than Stock Momentum? | Antoine Falck, Adam Rej, David Thesmar | Factor momentum vs stock momentum attribution. | Useful for avoiding double-counting momentum exposures across factor and ETF sleeves. |
| `arxiv-transaction-costs-execution-trading.pdf` | `2007.07998v1` | Transaction Costs in Execution Trading | David Marcos | Transaction cost and market impact framework. | Useful for later execution/slippage modeling; not a signal paper. |

## arXiv Candidates Not Downloaded

These appeared in arXiv queries but were not downloaded in this pass to avoid low-signal accumulation or because the fit was weaker.

| arXiv ID | Title | Reason Not Downloaded |
|---|---|---|
| `1409.7933v1` | Parametric Risk Parity | Relevant but more distribution-model-specific; deferred. |
| `2106.09055v3` | Diversified reward-risk parity in portfolio construction | Relevant; deferred for later broader risk-parity review. |
| `2604.16773v1` | Topological Risk Parity | Very recent and specialized long/short topology method; not suitable for current unlevered ETF MVP without deeper review. |
| `2002.08286v1` | Price impact equilibrium with transaction costs and TWAP trading | More theoretical market microstructure; not downloaded for first execution-cost pass. |
| `1603.06558v1` | Universal trading under proportional transaction costs | Has arXiv overlap warning; not prioritized. |
| `1402.3030v2` | Information ratio analysis of momentum strategies | Relevant momentum analysis; deferred. |
| `1702.07374v1` | Time series momentum and contrarian effects in the Chinese stock market | Market-specific; possible future China/HK research reference. |

## SSRN Discovery Attempts

Direct SSRN landing pages and delivery URLs often returned `403` or required browser/session behavior from this environment. The alternative approach used here was:

- Query Crossref for SSRN DOI metadata.
- Query OpenAlex for open-access locations and repository PDF URLs.
- Query Semantic Scholar for `openAccessPdf` where possible; this returned `429` rate-limit responses during this run.
- Check author/institution-hosted public PDFs when known.
- Keep only files that download as complete PDFs and pass `pdfinfo`.

## SSRN-Related Candidates

| Candidate | SSRN / DOI Metadata | Alternative Discovery Result | Local Status | Project Relevance |
|---|---|---|---|---|
| Momentum Crashes | Crossref found SSRN DOI `10.2139/ssrn.2486272` and `10.2139/ssrn.2632705`; formal JFE DOI `10.1016/j.jfineco.2015.12.002`. | Crossref metadata available; NBER-style direct PDF attempts were incomplete in this environment and failed `pdfinfo`. | Not downloaded. | Important for momentum drawdown/crash risk and regime risk controls. |
| Buffett's Alpha | Known SSRN/NBER-linked AQR paper by Frazzini, Kabiller, Pedersen. | Direct AQR legacy PDF returned HTML; NBER PDF attempt was incomplete and failed integrity checks. | Not downloaded. | Useful for quality/low-beta/leverage attribution; not core ETF timing. |
| Tactical Asset Allocation | SSRN abstract `962461`; author-hosted PDF available from Meb Faber. | Author-hosted public PDF downloaded and validated as `faber-tactical-asset-allocation.pdf`. | Downloaded via author site, not SSRN. | Direct support for monthly ETF trend allocation. |
| Adaptive Asset Allocation | Common SSRN topic around dynamic tactical allocation. | Crossref/Semantic Scholar attempts were rate-limited or noisy; no stable PDF selected. | Candidate only. | Potential source for future multi-asset allocation extensions. |
| 212 Years of Price Momentum | Crossref references SSRN DOI `10.2139/ssrn.2292544` from Momentum Crashes references. | No direct complete PDF obtained in this run. | Candidate only. | Long-horizon momentum robustness and historical out-of-sample framing. |

## Recommended Next Retrieval Paths

1. Retry Semantic Scholar queries later with lower frequency or an API key if available.
2. Use OpenAlex exact-title searches and inspect `best_oa_location.pdf_url` before downloading.
3. For SSRN-only papers, prefer author-hosted or institution repository PDFs over SSRN delivery URLs.
4. If a paper is only available from SSRN behind session controls, record metadata and leave it for manual browser download by the user.
5. Run `pdfinfo` on every downloaded PDF; reject any file with trailer/xref/page errors even if `file` reports `PDF document`.

## Quality Gate

A paper should be promoted from candidate to local reference only if:

- The source is public and legally accessible.
- The file is a complete PDF, not a moved-page HTML response.
- `pdfinfo` succeeds.
- The README records source URL, authors, theme, and project use.
- The paper's claims are treated as research hypotheses, not implementation requirements.
