# Genesis

A fantasy world simulation where AI agents start from nothing — no knowledge,
no tools — and figure out how to survive. Each agent's mind will be a different
LLM (Plan 3); the world itself is a deterministic engine.

## Status

Plan 2 (discovery, crafting & building) — agents experiment to discover fire,
stone tools, and cooked food; build campfires and huts; and gain real payoffs
(better yields, warm nights). Still rule-driven; LLM minds come next.

## Run

    uv sync
    uv run pytest
    uv run python -m genesis.cli --days 2 --db world.db

## Docs

- Design spec: docs/superpowers/specs/2026-08-29-genesis-phase1-design.md
- Plans: docs/superpowers/plans/
