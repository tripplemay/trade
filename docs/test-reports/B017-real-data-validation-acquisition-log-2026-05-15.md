# B017-real-data-validation-acquisition-log-2026-05-15

- Batch: B017
- Purpose: real-data snapshot acquisition for B015/B016 research validation
- Range requested: 2018-01-01..2025-12-31
- Expected weekday count (approx): 2088
- Manifest snapshot id: regime-adaptive:b69883b08eedea7d

## Per-Ticker Acquisition Summary
| ticker | rows | first | last | coverage_vs_weekdays | sha256 |
|---|---:|---|---|---:|---|
| SPY | 2011 | 2018-01-02 | 2025-12-31 | 96.3123% | a7bd73a7714f015376706b07082c466e34816a401a0fc8af31f66a37d4903e68 |
| QQQ | 2011 | 2018-01-02 | 2025-12-31 | 96.3123% | efc1fe5f6bdbe0becd019c4bedc3479a7e5d4e4f8098bb80e6b56cbfd9602b91 |
| VEA | 2011 | 2018-01-02 | 2025-12-31 | 96.3123% | 4cd60953d3a1dffb9dce646ecf6c7e245ff24589bfc5785e47f3e3574cf0e150 |
| VWO | 2011 | 2018-01-02 | 2025-12-31 | 96.3123% | cd93bc77e4eda467f9a7a463e89aaef76d4a558e2e43a9a0cced2d9da65f1a09 |
| IEF | 2011 | 2018-01-02 | 2025-12-31 | 96.3123% | 12e82c117658f58e584cd14859bccce5a32358c3ef3f638021f2b21e2923598e |
| TLT | 2011 | 2018-01-02 | 2025-12-31 | 96.3123% | de256f8703d07cba7f8245d4c667129811f0bb16e28a26d4ffb93868bb8396dc |
| GLD | 2011 | 2018-01-02 | 2025-12-31 | 96.3123% | bde2d6890a8f8d171fd0b193b8930d1134e9d5db5907ebcdc8592c10e916b961 |
| DBC | 2011 | 2018-01-02 | 2025-12-31 | 96.3123% | 86a87cfe7229189015e87134648024dc4796cd29a403bc1e9586ea248e852e4a |
| SGOV | 1405 | 2020-06-01 | 2025-12-31 | 67.2893% | a11a78ff9997dbf95beb967fb16cbd5efecc4b1bef4c4acccec7587a37038f45 |

## Verification Notes
- 8 non-SGOV tickers exceed the 95% coverage gate.
- SGOV is exempted for short history due to its 2020-05-28 inception.
- Raw CSVs remain gitignored in `data/public-cache/`.

_Disclaimer: research-only public-best-effort non-PIT data; never authorizes paper or live trading._
