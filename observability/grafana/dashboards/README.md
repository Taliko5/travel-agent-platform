Drop Grafana dashboard JSON files in this directory and they'll be picked up
automatically (see `../provisioning/dashboards/default.yml`). Files are read
from `/etc/grafana/dashboards` inside the container, bind-mounted from this
directory — no provisioning config changes are needed to add another one.

## `travel-agent-overview.json`

Nine panels covering the `/chat` request path:

1. `/chat` p50/p95/p99 latency, successful requests only
2. p95 latency by intent, successful requests only
3. request rate by intent
4. error rate
5. intent classifier fallback rate
6. latency distribution heatmap — per-bucket view of the same histogram
   panels 1–2 read as quantiles, so you can see whether the bucket
   boundaries are placed where the data actually is
7. LLM call duration by node (classification / city extraction / generation),
   mean latency (`_sum/_count`, not a quantile — see the panel's own
   description for why) for successful calls only
8. RAG retrieval rate as a fraction of all requests — a ratio, not a raw
   count, since retrieval only fires on some routing branches
9. LLM call error rate — the counterpart that makes panel 7's
   successful-calls-only filter legitimate, the way panel 4 does for panel 1

An earlier text panel, noting that `llm_call_duration_seconds`/
`rag_retrieval_total` had no recording call sites yet, was removed once both
were wired up (`openspec/changes/step8-metric-design` design.md D19) — its
one still-true residual fact (histograms don't appear on `/metrics` until a
real observation lands, unlike seeded counters) now lives in panel 7's own
description, where a reader actually meets it empty.

Each panel carries its own reasoning in its `description` field — why panels
4 and 5 wrap only their numerator in `or vector(0)`, why panels 1 and 2
filter `status="ok"`, and the measurement figures those descriptions quote.
That field is the only place those numbers live. Don't copy them into this
README or into another panel, and don't restate one from memory: a second
copy drifting from the first is how the 2026-08-11 and 2026-08-12 figures
came to disagree.

The dashboard has `"id": null` and a stable `"uid": "travel-agent-overview"`
so it keeps the same URL across Grafana restarts. It reads its datasource
through a `${datasource}` template variable (type `datasource`, query
`prometheus`) rather than a hardcoded UID — provisioned dashboards that
hardcode a datasource UID are the most common cause of a "Datasource not
found" render.

## Adding another dashboard

Export or hand-write a raw Grafana dashboard JSON model (not the API
`{"dashboard": {...}}` wrapper — the file must be the dashboard model
itself, top-level `title`/`panels`/`templating`/`time`/...), give it a
stable `uid`, set `"id": null`, and reference the datasource through a
`${datasource}` template variable rather than a hardcoded UID. Drop the
file in this directory; Grafana picks it up within
`updateIntervalSeconds` (30s, see `../provisioning/dashboards/default.yml`)
without a restart. To confirm it loaded, check
`docker-compose logs grafana | grep -i -E "provisioning|dashboard"` for the
read from `/etc/grafana/dashboards` with no error — a JSON parse failure or
schema problem shows up there, not in the UI.
