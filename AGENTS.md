# AGENTS.md

ha-cfmoto is a Home Assistant custom integration for CFMoto motorcycles with a T-Box. It reads telemetry from the CFMoto cloud API and ships its own Lovelace card. BLE control is experimental. Details are in the [README](README.md).

## Layout

| Path | What |
|---|---|
| `custom_components/cfmoto/` | The integration (cloud client, coordinator, entities, BLE module) |
| `custom_components/cfmoto/frontend/` | The Lovelace card and its editor |
| `probe.py` | Standalone cloud API probe, stdlib only |
| `tools/ble_probe.py` | Interactive BLE client for debugging next to the bike |
| `tests/` | Python tests (signing, BLE codec and auth) and Node tests for the card |

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install cryptography
.venv/bin/python -m unittest discover -s tests
node --test tests/test_card.mjs tests/test_card_render.mjs
```

The card tests run against a DOM shim, so no browser is needed. The browser caches `/cfmoto-static/`, so when the card file changes, bump the `?v=` query of the card resource (README, "Dashboard card").

## Pull requests

- Branch off `main` with `feat/`, `fix/`, `docs/`, `chore/` or `refactor/`, and open the PR against `main`.
- Write the PR title as a Conventional Commit (`feat(card): …`). PRs are squash-merged, so the title becomes the commit message.
- Start the PR body with the issue line: `Closes #N`, `Refs #N` or `No issue: <reason>`.
- Direct pushes to `main` are blocked by the repository ruleset and the global pre-push hook. Merge only when the checks are green.
- This repository is public. Use made-up example data such as `example.com`, never real accounts, credentials, VINs or locations.

## Code Review Rules

- Review for correctness and security only. No style comments.
- Skip generated files and lockfiles.
