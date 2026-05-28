# News ingest fixtures (B033)

Offline CI fixtures for `workbench_api.news.adapters`. The SEC EDGAR /
Yahoo RSS adapters are unit-tested by mocking `httpx.Client` and feeding
these payloads — production CI never hits the real upstream endpoints.

## Files

| File | Source | Form / Type | Used by |
|---|---|---|---|
| `edgar-submissions-AAPL.json` | SEC EDGAR `/submissions/CIK0000320193.json` | mixed forms incl. 10-K / 10-Q / 8-K / 4 / noise (S-1 / 13F) | `tests/unit/test_news_adapter_edgar.py` |
| `edgar-submissions-NVDA.json` | SEC EDGAR `/submissions/CIK0001045810.json` | 8-K + 10-Q | `tests/unit/test_news_adapter_edgar.py` |
| `edgar-submissions-MSFT.json` | SEC EDGAR `/submissions/CIK0000789019.json` | Form 4 + 10-Q | `tests/unit/test_news_adapter_edgar.py` |
| `edgar-primary-10k-AAPL.htm` | sample 10-K body | sample raw HTML | snapshot writer assertion |
| `edgar-primary-8k-NVDA.htm` | sample 8-K body | sample raw HTML | snapshot writer assertion |
| `edgar-primary-form4-MSFT.xml` | sample Form 4 body | sample raw XML | snapshot writer assertion |
| `yahoo-sample-AAPL.xml` | Yahoo Finance RSS | RSS 2.0 feed (F003) | `tests/unit/test_news_adapter_yahoo.py` |
| `yahoo-sample-SPY.xml` | Yahoo Finance RSS | RSS 2.0 feed (F003) | `tests/unit/test_news_adapter_yahoo.py` |

## Live-validation snapshot

SEC EDGAR `/submissions/` envelope was live-validated against
`https://data.sec.gov/submissions/CIK0000320193.json` on **2026-05-28**.
Field paths the adapter relies on:

- `name` (entity name)
- `cik` (zero-padded string)
- `filings.recent` (parallel arrays):
  - `accessionNumber`, `form`, `filingDate`, `reportDate`,
    `primaryDocument`, `primaryDocDescription`, `items`

`workbench_api.news.adapters.sec_edgar.SECEdgarNewsAdapter._iter_recent_filings`
raises `ValueError` if these paths drift; the unit test
`test_sec_edgar_submissions_envelope_field_paths` pins them so a SEC
schema change fails loudly rather than yielding empty results.

## Why fixtures and not VCR cassettes

The B029 / B027 / B028 adapters all use hand-built JSON fixtures. We
keep the same pattern here so all data-source CI is consistent —
fixtures are trivially diffable, regenerable, and let us include
**deliberate noise** (S-1, 13F filings) to verify the form-type
filter on read.
