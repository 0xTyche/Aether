# Vendored from worldmonitor

The following files in this directory and in `frontend/public/vendor/worldmonitor/`
are vendored from the [worldmonitor](https://github.com/koala73/worldmonitor)
project by [@koala73](https://github.com/koala73), licensed under
**GNU AGPL-3.0-only** (see [./LICENSE](./LICENSE)).

| File | Source path in worldmonitor |
|---|---|
| `country-geometry.ts` | `src/services/country-geometry.ts` |
| `country-codes.ts` | `src/utils/country-codes.ts` |
| `../../public/vendor/worldmonitor/countries.geojson` | `public/data/countries.geojson` |
| `../../public/vendor/worldmonitor/country-boundary-overrides.geojson` | `public/data/country-boundary-overrides.geojson` |

## Provenance

- **Upstream commit**: [`a0e4c241d27ec9e70310910ba5c747aca946c78d`](https://github.com/koala73/worldmonitor/commit/a0e4c241d27ec9e70310910ba5c747aca946c78d)
- **Vendored on**: 2026-06-09

## Modifications

Per AGPL-3.0, modifications must be tracked. All edits to these files are
visible in this repository's git history. Notable modifications at vendor time:

- `country-geometry.ts`: Updated `COUNTRY_GEOJSON_URL` and `COUNTRY_OVERRIDES_URL`
  constants to point at local `/vendor/worldmonitor/` paths instead of upstream
  CDN URLs.

## Updating from upstream

See [`CLAUDE.md`](../../../../CLAUDE.md) → "从 worldmonitor upstream 同步 bug fix"
for the workflow.
