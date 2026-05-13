# Public Data Import Boundary

B009 provides a manual local-file import boundary, not a downloader. The required workflow remains committed-fixture-first, offline, and CI-safe.

The code boundary is `trade.data.public_import`:

- `public_import_boundary()` returns the policy metadata.
- `import_public_data_stub()` fails closed for default/legacy callers and performs no network calls.
- `import_public_data()` copies an already-downloaded local file into `data/public-cache/` only when the caller passes explicit manual confirmation.
- The same call writes a snapshot manifest JSON next to the copied file, including provider, creation timestamp, ticker list, date range, row count, file hash, local path, and limitation labels.

Example manual invocation:

```bash
python -m trade.data.public_import \
  --source-file ~/Downloads/public-prices.csv \
  --provider stooq \
  --i-understand-this-is-manual-research-data
```

This command does not fetch from the network and does not read credentials. It only copies the local source file into the gitignored `data/` tree.

The generated manifest is research lineage metadata. It labels imported data as `public-best-effort`, `non-PIT`, `research-only`, and `not-live-trading-ready`.

Any future network downloader must be separately scoped and must remain:

- Manual only.
- Disabled by default.
- Excluded from required CI.
- Credential-free.
- Writing only to gitignored local directories such as `data/public-cache/`.
- Explicitly labeled as non-PIT / best-effort research data.

This boundary must not be interpreted as permission to use paid data, broker exports, account statements, secrets, or live/paper trading data.
