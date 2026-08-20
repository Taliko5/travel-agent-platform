## Why

Section 9 of `step8-observability-scaffold` was headed "reference only — not implemented by this change". Between 2026-08-11 and 2026-08-20 it became the place where the metric design work actually happened: the recording call sites and their label sets, a counter-seeding defect and its fix, a seven-panel Grafana dashboard, a load generator, and an end-to-end verification that is still outstanding. That scaffold change's spec delta still describes instruments that are "declared but not yet recorded", which stopped being true some time ago. This change takes ownership of the work so the specification can describe what the system does.

## What Changes

- Record `chat_request_duration_seconds` from the `/chat` handler's `finally` block, labelled `{intent, status}`, so failed requests are measured too.
- Record `intent_classification_total`, labelled `{intent, fallback}` — classifier health, not intent distribution.
- Establish `status` as `ok` | `error` and nothing else. The dashboard's error-rate panel filters on that value exactly, and a third value would silently remove those requests from it.
- Seed counters at zero from `seed_counters()`, called after `set_meter_provider()`. Deliberately never seed histograms.
- Hoist `VALID_INTENTS` into a module constant in `backend/agent/nodes.py` so the classifier and the seeding loop share one definition.
- Provision `observability/grafana/dashboards/travel-agent-overview.json` — seven panels, `uid: travel-agent-overview` — through Grafana's file provider.
- Add `scripts/generate_load.py`, rate-limited by default to what the Gemini free tier tolerates.
- Re-tune `chat_request_duration_seconds`'s bucket boundaries from measured data. Agreed, not yet applied.
- Wire recording call sites for `llm_call_duration_seconds` and `rag_retrieval_total`. Not started.
- Decide span names and attributes for the events `OTelCallbackHandler` receives. Not started.
- Verify the pipeline end-to-end and record the result in `docs/step8.md`. In progress.
- **BREAKING**: none — additive instrumentation and configuration only.

## Capabilities

### New Capabilities
(none — this change works entirely within the `observability` capability that `step8-observability-scaffold` introduced.)

### Modified Capabilities
- `observability`: `step8-observability-scaffold` ADDed this capability with placeholder instruments that were explicitly declared-but-unrecorded. This change MODIFIES those requirements to describe recorded metrics with defined label sets and bucket boundaries, and ADDs requirements for the provisioned dashboard, the seeding rule, the `status` invariant, load generation and end-to-end verification.

## Impact

- **Affected code**: `backend/api/main.py` (recording call sites, `seed_counters()` invocation), `backend/observability/metrics.py` (label sets, bucket boundaries, seeding), `backend/agent/nodes.py` (`VALID_INTENTS`), `backend/tests/`.
- **New files**: `observability/grafana/dashboards/travel-agent-overview.json`, `scripts/generate_load.py`, `docs/step8-task9c9d.md`, `docs/step8-host-network.md`.
- **Docs**: `docs/step8.md` gains a "Generating load" section and, from 9-d, a "Verified End-to-End" section.
- **CI**: `.github/workflows/ci.yml` gates the backend jobs on `backend/**`, so nothing under `scripts/` or `observability/` is linted or tested there. The local `ruff check scripts/` is the only check those files get.
- **Cross-change dependency**: `chat-request-deadline`'s spec delta already requires that no `status` value other than `ok` or `error` is produced. That invariant is specified here.

## Non-Goals

- The OTel SDK wiring, `OTelCallbackHandler`, structured logging and the compose services — owned by `step8-observability-scaffold`.
- A server-side deadline on `/chat` — owned by `chat-request-deadline`.
- Alerting or SLO burn-rate rules.
- The host power-management behaviour that contaminated the 2026-08-12 load run — closed in `docs/step8-host-network.md`.
