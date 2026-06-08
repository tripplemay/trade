# Strategy Literature Library

This directory stores publicly accessible strategy research references collected for this project. The files are supporting research material only. They are not trading advice, not implementation specifications, and not permission to relax the repository's no-live/no-broker/no-paper safety boundaries.

Collection date: 2026-05-13

## Selection Criteria

- Publicly accessible without bypassing paywalls or access controls.
- Authored by recognized academics, institutional researchers, or established practitioners.
- Directly relevant to this project's current strategy themes: global ETF momentum, tactical allocation, risk parity, volatility targeting, factor tilts, and news/narrative risk filters.
- Useful for forming testable research hypotheses rather than copying unverified live-trading rules.

## Downloaded References

| File | Source / Authors | Theme | Project Use |
|---|---|---|---|
| `aqr-time-series-momentum.pdf` | Moskowitz, Ooi, Pedersen; AQR / academic author-hosted copy | Time-series momentum across asset classes | Supports absolute momentum / trend filters for global ETF rotation and cross-asset risk-on/risk-off regimes. |
| `aqr-value-and-momentum-everywhere.pdf` | Asness, Moskowitz, Pedersen; AQR / academic author-hosted copy | Value and momentum premia across markets | Supports separating cross-sectional momentum from valuation/factor overlays; useful for avoiding single-factor overfit. |
| `faber-tactical-asset-allocation.pdf` | Mebane Faber | Tactical asset allocation with moving-average trend filters | Directly relevant to ETF-level monthly rebalancing, simple trend-following rules, and drawdown-aware allocation. |
| `aqr-understanding-risk-parity.pdf` | AQR | Risk parity portfolio construction | Supports the project's inverse-volatility / risk parity design, while highlighting assumptions around leverage, diversification, and asset-class risk contributions. |
| `aqr-betting-against-beta.pdf` | Frazzini, Pedersen; academic author-hosted copy | Low-beta / leverage constraints / factor anomaly | Useful for evaluating whether low-volatility and quality tilts belong in later equity sleeves; not a direct ETF timing rule. |
| `aqr-quality-minus-junk.pdf` | Asness, Frazzini, Pedersen; AQR | Quality factor | Supports possible future U.S. quality-momentum equity selection or quality ETF sleeve; relevant to `docs/strategy/03-us-quality-momentum.md`. |
| `aqr-carry.pdf` | Koijen, Moskowitz, Pedersen, Vrugt; academic author-hosted copy | Carry premia across asset classes | Useful for future cross-asset factor research and for separating carry exposure from momentum or risk-parity effects. |
| `arxiv-introduction-risk-parity-budgeting.pdf` | Thierry Roncalli; arXiv | Risk parity and risk budgeting | Supports conceptual vocabulary and portfolio construction context for risk parity. |
| `arxiv-mad-risk-parity.pdf` | Ararat, Cesarone, Pinar, Ricci; arXiv | MAD-based risk parity | Supports later robustness tests using alternative risk measures. |
| `arxiv-portfolio-optimization-evar.pdf` | Ahmadi-Javid, Fallah-Tafti; arXiv | Entropic VaR portfolio optimization | Supports future downside-risk and tail-risk-aware portfolio constraints. |
| `arxiv-factor-momentum.pdf` | Falck, Rej, Thesmar; arXiv | Factor momentum | Supports factor-vs-stock momentum attribution and avoids double-counting momentum exposure. |
| `arxiv-transaction-costs-execution-trading.pdf` | David Marcos; arXiv | Transaction costs and execution | Supports later slippage/market-impact modeling; not a signal paper. |

## Strategy Hypotheses To Carry Forward

1. Global ETF momentum should distinguish absolute momentum from relative momentum.
   - Absolute momentum can act as a regime/risk filter.
   - Relative momentum can rank eligible ETF candidates.
   - Both should be tested separately before combining.

2. Monthly ETF rebalancing has credible precedent but needs strict point-in-time data handling.
   - Faber-style moving-average rules are simple enough for MVP validation.
   - Backtests must preserve the project's existing T-day/T+1 execution assumptions and snapshot semantics.

3. Risk parity should remain unlevered at MVP stage.
   - AQR risk parity research often discusses risk-balanced allocations where leverage can matter.
   - This project currently prohibits leveraged exposure; any leverage extension requires a separate spec, safety review, and user approval.

4. Factor ideas should be treated as sleeves or overlays, not mixed into the ETF momentum MVP without attribution.
   - Value/momentum, low-beta, and quality papers justify future factor research.
   - They should not be used to retrofit undocumented scoring rules into the current ETF momentum or risk-parity backtests.

5. Carry, value, momentum, quality, and low-beta should be treated as distinct hypotheses.
   - Cross-asset factor papers support a multi-factor research roadmap.
   - The project should avoid blending factor definitions unless each factor contribution is separately measured.

## Application Map

| Existing Project Area | Most Relevant References | Notes |
|---|---|---|
| `docs/strategy/01-global-etf-momentum-rotation.md` | `aqr-time-series-momentum.pdf`, `faber-tactical-asset-allocation.pdf`, `aqr-value-and-momentum-everywhere.pdf` | Use for trend/ranking design and robustness framing. |
| `docs/strategy/02-risk-parity-vol-target.md` | `aqr-understanding-risk-parity.pdf` | Use for conceptual support, but keep MVP unlevered. |
| `docs/strategy/03-us-quality-momentum.md` | `aqr-quality-minus-junk.pdf`, `aqr-value-and-momentum-everywhere.pdf`, `aqr-betting-against-beta.pdf` | Use for future factor sleeve design. |
| Future cross-asset factor research | `aqr-carry.pdf`, `aqr-value-and-momentum-everywhere.pdf`, `aqr-betting-against-beta.pdf` | Use to design factor attribution experiments separate from ETF timing rules. |
| Future risk-model robustness | `arxiv-mad-risk-parity.pdf`, `arxiv-portfolio-optimization-evar.pdf`, `arxiv-introduction-risk-parity-budgeting.pdf` | Use to compare volatility, MAD, CVaR/EVaR, and other risk-budgeting assumptions. |
| Future execution-cost modeling | `arxiv-transaction-costs-execution-trading.pdf` | Use as background before adding slippage/impact models. |
| `docs/strategy/00-master-portfolio-allocation.md` | All references | Use for portfolio construction assumptions, diversification rationale, and risk-control boundaries. |

## Limitations

- These references are research inputs, not validated project requirements.
- Many reported results are based on long historical samples, broad asset universes, institutional cost assumptions, or leverage availability that may not match this project.
- Download availability can change; the original source URL should be rechecked before external citation.
- The repository should continue to require fixture/mock-first tests and explicit point-in-time data semantics before any strategy rule is accepted.

## Source URLs Used

- https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf
- https://pages.stern.nyu.edu/~lpederse/papers/ValMomEverywhere.pdf
- https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf
- https://www.aqr.com/-/media/AQR/Documents/Insights/White-Papers/Understanding-Risk-Parity.pdf
- https://pages.stern.nyu.edu/~lpederse/papers/BettingAgainstBeta.pdf
- https://www.aqr.com/-/media/AQR/Documents/Insights/Working-Papers/Quality-Minus-Junk.pdf
- https://pages.stern.nyu.edu/~lpederse/papers/Carry.pdf
- https://arxiv.org/pdf/1403.1889v1
- https://arxiv.org/pdf/2110.12282v2
- https://arxiv.org/pdf/1708.05713v1
- https://arxiv.org/pdf/2009.04824v1
- https://arxiv.org/pdf/2007.07998v1
- docs/research/strategy-literature/arxiv-ssrn-candidates.md records arXiv candidates and SSRN discovery attempts.

## Expanded Search Surface

The following sources were reviewed as part of a broader search. They are useful candidates for future research, data validation, or macro context, but were not added as downloaded report PDFs in this pass because the pages were data directories, HTML insight pages, blocked by the host, moved, or not reliably downloadable as complete PDF files from this environment.

| Source | URL | Reason Not Added As Downloaded PDF | Potential Use |
|---|---|---|---|
| Kenneth French Data Library | https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html | Data directory, not a single research report PDF. | Factor benchmark data for momentum, reversal, value, profitability, investment, beta, variance, and international factors. |
| AQR Data Sets | https://www.aqr.com/Insights/Datasets | Data directory and dataset pages rather than stable report PDFs. | External factor data candidates for QMJ, BAB, value/momentum, HML Devil, and momentum indices. |
| MSCI Research & Insights | https://www.msci.com/research-and-insights | Research portal returned HTML; no specific stable PDF was selected. | Index methodology, factor investing, multi-asset, and risk research candidates. |
| BlackRock Investment Institute | https://www.blackrock.com/us/individual/insights/blackrock-investment-institute | Public insight portal returned HTML and extensive disclaimers. | Macro regime, portfolio construction, and ETF allocation context. |
| Bridgewater Research & Insights | https://www.bridgewater.com/research-and-insights | Public insight pages are mostly HTML/video/article pages. | Macro regime, portfolio resilience, inflation, gold, and geopolitical-risk context. |
| S&P Dow Jones Indices Research | https://www.spglobal.com/spdji/en/research-insights/ | Returned 403 in this environment. | Index construction, factor indices, SPIVA, and ETF benchmark context if accessible separately. |
| NBER working papers | https://www.nber.org/ | Partial downloads from this environment failed PDF integrity checks. | Narrative economics, Buffett's alpha, and momentum-crash papers should be retried from a more stable network if needed. |
| arXiv API | https://export.arxiv.org/api/query | Used successfully for public metadata and PDF discovery. | Risk parity, portfolio optimization, transaction cost, and factor momentum references. |
| Crossref API | https://api.crossref.org/works | Used successfully for SSRN DOI and formal publication metadata. | SSRN candidate tracking and formal DOI resolution. |
| OpenAlex API | https://api.openalex.org/works | Used for open-access location discovery; results can be noisy and need manual filtering. | Repository PDF discovery and OA metadata. |
| Semantic Scholar API | https://api.semanticscholar.org/ | Returned `429` rate-limit responses during this run. | Retry later for `openAccessPdf` discovery. |

## Attempted But Not Included

- SSRN landing pages returned access-denied responses from this environment.
- Several AQR article URLs had moved and returned site HTML instead of PDF content; those invalid downloads were removed.
- Some Fama/French historical PDF URLs returned 404 from this environment and were not included.
- NBER PDF downloads for Shiller narrative economics, Buffett's Alpha, and Momentum Crashes started but failed `pdfinfo` integrity checks; those incomplete files were removed.
- SSRN alternatives were attempted through Crossref, OpenAlex, Semantic Scholar, author-hosted pages, and known institution/NBER paths; only complete and validated PDFs were retained locally.
