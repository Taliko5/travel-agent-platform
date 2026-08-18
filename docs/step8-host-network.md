# Step 8 — Host network failures (DNS / TLS) during load runs

**Status: open, undiagnosed.** Last updated 2026-08-18.

This is the investigation record for the outbound-connectivity failures that contaminated the 2026-08-12 load run. It is the authoritative place for the symptoms, the evidence, and the hypotheses; Section 9 of `openspec/changes/step8-observability-scaffold/tasks.md` points here rather than restating any of it. It is not a runbook — nothing is diagnosed yet.

## Why this blocks work

Task 9-d cannot be recorded against the current environment, because a re-run reproduces the same contaminated dataset. Re-running the load generator before this is fixed burns Gemini free-tier quota and produces another unusable run.

## Symptoms

From the load run of 2026-08-12 — 60 requests at the load generator's defaults: 60 requests, concurrency 1, 6 seconds apart. (`scripts/generate_load.py` was subsequently found to be missing from the repo and is being recreated; the defaults quoted here come from its specification in `docs/step8-task9c9d.md`, Task 1.)

- **6 of the 60 requests failed.** The remaining 54 are uncontaminated.
- Two error strings appeared, both raised on the backend container's outbound call to Gemini:
  - `Temporary failure in name resolution` — getaddrinfo `EAI_AGAIN`
  - `[SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate`
- **One failed request ran for 1025.74 seconds** before giving up: `google_genai`'s internal `tenacity` retry loop kept going because `/chat` has no server-side deadline. That defect is an application bug and is tracked separately, not here.
- Prometheus' `up` series has **three gaps in its samples** over the same period.

Consequences recorded elsewhere, repeated here only as pointers:

- `intent_classification_total` sums to **54**, not 60 — the six failures died inside `classify_intent`, so no intent was recorded for them. Panels 4 and 5 consequently have different denominators.
- The `chat_request_duration_seconds` histogram's `20.0` / `60.0` / `+Inf` buckets hold environmental failures, not application latency. That tail is not a property of the application.

## Environment

- macOS host running Docker Desktop; the compose stack runs there.
- Home network behind an AVM FRITZ!Box. **No VPN, no corporate network** — confirmed 2026-08-18.
- The failing traffic is *backend container → Gemini*, outbound through Docker. The load generator runs on the host and talks only to `http://localhost:8000`; it is not the thing failing to resolve.

## Ruled out

- **A constant man-in-the-middle proxy, or a misconfigured resolver.** Either would fail 100% of requests. 54 of 60 succeeded.
- **A corporate TLS-inspection CA.** No VPN and no corporate network.
- **Docker's embedded DNS resolver dropping UDP queries under concurrent load.** The run was serial — `--concurrency 1` with `--delay 6.0`, roughly 10 requests per minute. That cannot saturate a resolver.

## Open hypotheses

None of these is established. They are written down so evidence can be gathered *against* them rather than around them.

- **H1 — the failures fall inside one bounded outage window rather than scattering across the run.** The 1025-second retry means connectivity stayed broken for about 17 minutes for at least one request. If H1 holds, the 6-in-60 failure rate is an artefact of when the run overlapped the window, and the fault will not reproduce on demand.
- **H2 — resolution sometimes returns a wrong answer rather than no answer.** Two different error strings in one run suggest a single cause upstream of TLS: if the connection lands on a host that is not Google, the certificate it presents will not validate, and a self-signed certificate is what a router or appliance admin interface typically serves. The mechanism is **not** established — a FRITZ!Box normally returns SERVFAIL rather than its own address. Confirming or killing H2 requires the resolved IP address and the peer certificate's subject and issuer captured at the moment of failure, which no existing log contains.
- **H3 — Docker Desktop for Mac's VM lost DNS after a host network change or a sleep/wake cycle.** A known failure mode, and it fits a multi-minute window that ends only when something is restarted. Separating H3 from H1 requires knowing whether the window closed on its own.

## Evidence still available

The 2026-08-12 data is **still in the `prometheus_data` volume**, and the stack is up. The failure timeline can be reconstructed without re-running anything:

- `up{job="travel-agent-backend"}` across 2026-08-12 — where the three sample gaps sit and how wide each one is
- `chat_request_duration_seconds_count` increments — when each request actually completed

Whether those gaps cluster into a single window or scatter across the run is what separates H1 from a per-request failure mode. **Do this before anything else**: it costs nothing, needs no working network, and it decides which of the hypotheses above is worth pursuing.

**Do not run `docker-compose down -v`.** It destroys `prometheus_data`, and with it the only surviving record of this run — the load generator's stdout was not saved.

## Next steps

1. Reconstruct the failure timeline from Prometheus, as above. Record the result in the findings log.
2. Capture a healthy baseline from inside the backend container: `/etc/resolv.conf`, the addresses `generativelanguage.googleapis.com` resolves to, and the subject and issuer chain the TLS peer presents. Without a known-good picture, a capture taken during a failure cannot be read.
3. Run a watchdog that attempts resolution and a TLS handshake on an interval and appends timestamped results to a file, so the next window is captured with the evidence H2 needs instead of being missed.
4. Only once this is understood: re-run the load, saving stdout to a file.

## Findings log

Append dated entries below as evidence arrives. Do not overwrite earlier entries — a hypothesis that was ruled out is worth as much as one that was confirmed.

- **2026-08-18** — Record opened. Nothing measured yet beyond the above, all of which is carried over from the 2026-08-12 run and from the load generator's specification.
