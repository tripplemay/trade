# B014 Regime-Adaptive Stress Validation Acquisition Log 2026-05-14

- Snapshot ID: regime-adaptive:8e923fbfdfb7ffad
- Source: regime-adaptive-public-import
- Date range: 2018-01-01 -> 2025-12-31

## Files
- SPY: rows=2011, start=2018-01-02, end=2025-12-31, sha256=a06dd3099bfe308e69084262284bd1330ea121306750f87bf8c3961890c45aca, short_history_exempt=False
- QQQ: rows=2011, start=2018-01-02, end=2025-12-31, sha256=6aab1b03b8618ea0941f2e2199f6782393302462f4b259ad95d09027800105fc, short_history_exempt=False
- VEA: rows=2011, start=2018-01-02, end=2025-12-31, sha256=f401e0a106f72b1789168339397b0a6a728c494db9d7bdb66ae3edb4ee494f32, short_history_exempt=False
- VWO: rows=2011, start=2018-01-02, end=2025-12-31, sha256=446eb1803c261770daef82ed11ca7a948676b45fd20e7be4c2cf3367f3f9c181, short_history_exempt=False
- IEF: rows=2011, start=2018-01-02, end=2025-12-31, sha256=b76bf2ac2c893997062da6d8aa9219219f0c09eeca34ee2214fdc9537b9097d1, short_history_exempt=False
- TLT: rows=2011, start=2018-01-02, end=2025-12-31, sha256=8a39db26c579371125e417d06180fa137e45d19b50ab6f9bc660ce8f19ae255e, short_history_exempt=False
- GLD: rows=2011, start=2018-01-02, end=2025-12-31, sha256=bde2d6890a8f8d171fd0b193b8930d1134e9d5db5907ebcdc8592c10e916b961, short_history_exempt=False
- DBC: rows=2011, start=2018-01-02, end=2025-12-31, sha256=de391da28eca7a9f7a7689614ff3a891de8b33f5f63a4a68b26560f40260d6c7, short_history_exempt=False
- SGOV: rows=1405, start=2020-06-01, end=2025-12-31, sha256=966deb7569d0eebf2b35d6517be7e4134c597bf5bfb488ac2b6a12a9b9cb37bf, short_history_exempt=True

## Notes
- 8 non-SGOV tickers cleared the 95% coverage bar in the original yfinance fetch.
- SGOV began on 2020-06-01 and is marked short-history exempt in the manifest.
- Current on-disk CSV hashes match the manifest sha256 values.
- Raw CSVs remain under data/public-cache/ and are gitignored.
