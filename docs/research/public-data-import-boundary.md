# Public Data Import Boundary

B008 does not implement a public data downloader. The required workflow remains committed-fixture-first, offline, and CI-safe.

The code boundary is `trade.data.public_import`:

- `public_import_boundary()` returns the policy metadata.
- `import_public_data_stub()` fails closed and performs no network calls.

Any future public data importer must be separately scoped and must remain:

- Manual only.
- Disabled by default.
- Excluded from required CI.
- Credential-free.
- Writing only to gitignored local directories such as `data/public-cache/`.
- Explicitly labeled as non-PIT / best-effort research data.

This boundary must not be interpreted as permission to use paid data, broker exports, account statements, secrets, or live/paper trading data.
