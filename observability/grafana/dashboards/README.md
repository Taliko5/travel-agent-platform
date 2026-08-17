Drop Grafana dashboard JSON files in this directory and they'll be picked up
automatically (see `../provisioning/dashboards/default.yml`). Files are read
from `/etc/grafana/dashboards` inside the container, bind-mounted from this
directory — no provisioning config changes are needed to add another one.

## `travel-agent-overview.json`

Seven panels covering the `/chat` request path:

1. `/chat` p50/p95/p99 latency, successful requests only
2. p95 latency by intent, successful requests only
3. request rate by intent
4. error rate
5. intent classifier fallback rate
6. latency distribution heatmap — per-bucket view of the same histogram
   panels 1–2 read as quantiles, so you can see whether the bucket
   boundaries are placed where the data actually is
7. a text panel noting which declared metrics (`llm_call_duration_seconds`,
   `rag_retrieval_total`) have no recording call sites yet, so their
   absence from `/metrics` isn't mistaken for a bug

The full specification — panel-by-panel PromQL, the reasoning behind each
query (in particular why panels 4 and 5 wrap only their numerator in
`or vector(0)`), and the measurement figures quoted in the panel
descriptions — lives in `docs/step8-task9c9d.md`. That document is
authoritative; don't restate its numbers here or in a panel description
from memory, since that's exactly how the dashboard and the docs drift out
of sync.

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
