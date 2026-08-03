Drop Grafana dashboard JSON files in this directory and they'll be picked up
automatically (see `../provisioning/dashboards/default.yml`).

Building the actual dashboards — panels, queries, layout — is the user's
hands-on task. See `docs/step8.md` for what metrics are available to query
once you've wired up recording calls in `backend/observability/metrics.py`.
