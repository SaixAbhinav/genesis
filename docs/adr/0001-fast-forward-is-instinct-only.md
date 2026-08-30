# 1. Catch-up fast-forward runs Instinct-only (no LLM minds)

**Date:** 2026-08-30
**Status:** Accepted

## Context

Genesis decouples the **world clock** (cheap deterministic ticks) from the
**thinking clock** (LLM Brain calls). The sim also supports *lives-on-return*:
when the world is reopened after being idle, `advance_world(last_tick → now)`
fast-forwards the missed sim-time so the world feels always-on.

Plan 4a introduces LLM **Brains** as one kind of **Mind**. The free tier we build
against (Groq) allows roughly **1,000 requests per day**, shared across all agents.
A single catch-up of a few idle hours spans thousands of ticks and would demand
far more than 1,000 Decisions — exhausting the entire daily budget in seconds and
leaving no requests for the live watching the user actually came back to see.

## Decision

**Catch-up fast-forward runs Instinct-only.** During `advance_world` catch-up,
no Agent consults an LLM Brain and the ThinkQueue receives no jobs; every Agent
is driven by deterministic **Instinct**. LLM Brains engage only while the world
is being watched live (foreground), where ticks advance at human-watchable speed
and Decisions are spaced by the Goal layer and the per-agent decision cooldown.

## Consequences

- The daily request budget is spent on live, observable Decisions, not on
  invisible skipped time. A returning viewer always has budget to watch.
- Fast-forward stays fully deterministic and testable — no network, no flakiness,
  no rate-limit failures on reopen.
- **Trade-off:** skipped time is "lived on Instinct." Agents survive and act
  plausibly during catch-up but do not exercise LLM judgment, so nothing that
  *requires* a Brain (novel experimentation, reasoned diving) happens off-screen.
  This is acceptable: the point of the project is to *watch* minds decide, and
  off-screen reasoning would be unobservable anyway.
- A future budget expansion (mixing providers, paid tier) could relax this, but
  the Instinct-only catch-up remains the correct default and safety floor.
