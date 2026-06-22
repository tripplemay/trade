# VCR cassettes — offline replay of the three httpx loaders (B073 F001)

These cassettes let CI replay the Tiingo / SEC EDGAR / LLM-gateway HTTP calls
**fully offline** — no API key, no network — for deterministic, reproducible
runs. They are a *supplement* to the in-process fake-client unit tests
(`test_*_loader.py`), not a replacement: the fakes pin retry/error behaviour,
the cassettes pin the real wire shape and catch vendor API-shape drift (the B031
lesson).

## Layout

```
tests/cassettes/<test-module>/<test-name>.yaml   # one cassette per VCR test
tests/fixtures/frames/*.csv                       # non-HTTP frame fixtures
                                                  # (akshare / yfinance) — see below
```

The directory is centralised here (rather than next to each test) by the
`vcr_cassette_dir` fixture in `tests/conftest.py`.

## How replay works

Each loader builds a **real** `httpx.Client`; `pytest-recording` patches httpx's
transport during a `@pytest.mark.vcr` test and serves the recorded response.
Config (in `tests/conftest.py`):

- `record_mode = "none"` — replay only. A request with no matching cassette
  entry raises `CannotOverwriteExistingCassetteException` (never silently hits
  the network).
- `match_on = [method, scheme, host, port, path, query]` — **not** body. httpx
  serialises JSON bodies compactly and vcrpy matches bodies byte-for-byte, so
  matching a multi-kB prompt body is unmaintainable. Two POSTs to the same URL
  (advisor haiku, then Sonnet judge in the F002 eval) are disambiguated by
  **recorded order**.
- `filter_headers = [authorization]` + `filter_query_parameters` — the API
  key/token is scrubbed on **record**, so a cassette never carries a secret.

## Re-recording (when a vendor's API shape drifts)

Cassettes here are hand-authored from the known wire shape because the dev box
has no live keys. To refresh one against the **real** API:

1. Export the relevant secret(s):
   `export TIINGO_API_KEY=…` / `export AIGC_GATEWAY_API_KEY=…` /
   `export SEC_EDGAR_CONTACT_EMAIL=you@example.com`.
2. Delete the stale cassette file, then run the test in record mode:
   ```bash
   cd workbench/backend
   .venv/bin/python -m pytest tests/unit/test_tiingo_loader_vcr.py \
       --record-mode=once
   ```
   (Temporarily drop the test's hard-coded dummy `api_key="vcr-test-key"` so the
   loader resolves the real env key, and adjust the dummy SEC `ticker_cik_map`
   if recording a different ticker.)
3. **Verify no secret leaked** into the new YAML (the `authorization` header
   should read `[REDACTED]`/`DUMMY`; no real token in any `uri`). Then re-run
   without `--record-mode` to confirm offline replay is green, and commit.

## Non-HTTP frame fixtures (akshare / yfinance)

The akshare (A-share) and yfinance loaders are not httpx clients — they call a
lazily-imported data library returning a pandas-like frame. Their "recording" is
a committed CSV under `tests/fixtures/frames/`, replayed through the loader's
existing injection seam (`akshare_module=` / `ticker_factory=`) in
`tests/unit/test_frame_fixtures_replay.py`. To refresh, regenerate the CSV from a
live `stock_zh_a_hist` / `yfinance.Ticker(...).history()` call and commit it.
