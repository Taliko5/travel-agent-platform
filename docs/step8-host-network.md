# Step 8 — Host network failures during the 2026-08-12 load run

**Status: closed 2026-08-19**, with one residual that could not be explained and cannot now be investigated.

## What this turned out to be

The 2026-08-12 load run recorded six failed requests and three gaps in Prometheus' `up` series. That was read as a host DNS / self-signed-certificate fault, and 9-d was blocked behind fixing it. Direct evidence has since shown that most of that picture was macOS power management, and a controlled re-run on 2026-08-19 produced no failures at all.

**There is no configuration fault to fix.** What remains is one unexplained three-minute window, described at the end.

## The 2026-08-12 run, reconstructed

Reconstructed from the `prometheus_data` volume on 2026-08-18. All times UTC; the host is Europe/Berlin, UTC+2.

```
08:34:45  run starts (first success)
   ...    eleven minutes of normal operation
08:45:45  last success before the cluster (51st)
08:46:30  failure 1     35.31 s
08:47:00  failure 2     34.97 s
08:47:45  failure 3     34.46 s
08:48:30  failure 4     34.20 s
08:49:00  failure 5     34.13 s
09:06:15  failure 6   1025.74 s
09:06:45  successes resume (53rd)
09:22:00  run ends (54th success)
```

No successful request completed between the failures. Start times are inferred as completion minus duration, so they carry the 15-second scrape granularity.

The five short failures took 34–35 seconds each, within a second of one another. Network variance does not produce that. It is the shape of a retry budget being exhausted and given up on, and it means all five shared one failure mode.

## What was established, and how

### Every gap in `up` is the machine sleeping

`pmset -g log` covers both dates. All six gaps — three on 2026-08-12, three on 2026-08-18 — fall inside a sleep/wake pair. This is macOS' own record, not an inference.

The decisive observation came first, from the TSDB itself: **no `up=0` sample exists anywhere, in any gap, on any date.** A running Prometheus that fails to reach its target records the failure as `up=0`. A total absence of samples means no scrape was attempted, so Prometheus was not executing. Sleeping the Mac suspends the Docker Desktop VM, and Prometheus with it.

On 2026-08-18 the largest gap, 17:42:00Z–18:27:30Z, fell inside a period when nobody was at the machine.

### The 1025.74-second request was 999 seconds of sleep

```
10:49:09 +0200  (inferred)  request 6 starts
10:49:16 +0200              Sleep 'Clamshell Sleep'  Using Batt (Charge:64%)  999 s
11:05:55 +0200              Wake
11:06:15 +0200  (recorded)  request 6 recorded as error
```

The lid closed seven seconds after the request began, and it was recorded twenty seconds after wake. Of the 1025.74 seconds, 999 were spent suspended; roughly 27 seconds of work happened. The earlier account — that a `tenacity` retry loop ran unchecked for seventeen minutes — does not hold. Note also `Using Batt`: the run was on battery, where macOS power management is far more aggressive.

### A controlled re-run is clean

2026-08-19, on AC power, lid open, wrapped in `caffeinate`, which `pmset` confirms held for the full 12 m 26 s with no sleep or wake transition inside the window.

```
60 requests, 60 × HTTP 200, 0 failures
wall-clock 745.2 s
latency  min 5.22 s   mean 6.52 s   max 8.22 s
per intent: general 15, hotel 15, transportation 15, weather 15
```

`docker-compose logs backend` for that window contains no line mentioning name resolution, certificates, retries or timeouts.

The wall-clock is exactly `60 × 6.52 + 59 × 6.0`, which is what the script should produce.

### Both external dependencies are healthy

Called directly from inside the backend container on 2026-08-19, both Open-Meteo endpoints returned HTTP 200 on three consecutive attempts, and a live `/chat` weather request returned a real temperature.

Per-intent means for the 2026-08-19 run, against 2026-08-12:

| intent | 2026-08-12 | 2026-08-19 | note |
|---|---|---|---|
| weather | 8.60 s | 7.04 s | the only intent that makes an external call |
| general | 6.85 s | 6.78 s | local RAG |
| transportation | 6.56 s | 6.33 s | in-memory mock |
| hotel | 6.54 s | 5.83 s | in-memory mock |

`weather` carries a premium over the other three in both runs — its two Open-Meteo round trips — but the premium falls from about 1.95 s to about 0.73 s. That is consistent with those round trips being slow on 2026-08-12 and fast on 2026-08-19, which supports rather than undermines the reading that the earlier environment was degraded.

The 2026-08-19 ordering also matches the architecture exactly: in-memory mocks fastest, local RAG next, external HTTP slowest. `backend/mcp_servers/flight_server.py` and `hotel_server.py` import no HTTP client and make no network call at all — **`weather_server.py` is the application's only external dependency besides Gemini.**

## The residual

Five consecutive failures, from roughly 08:45:55Z to the lid closing at 08:49:16Z — **three minutes and twenty-one seconds**, not the twenty minutes the raw timestamps suggest, since the rest of that span was sleep. The machine was awake, and Prometheus was scraping normally throughout.

This is unexplained. Power management on battery, in the minutes before an idle machine sleeps, is the most plausible candidate, and it is only a candidate.

**It cannot be investigated further.** The load generator's stdout was never saved, and the backend container's logs from 2026-08-12 were destroyed when the container was recreated on 2026-08-18. Prometheus holds only timings and durations, and those have all been extracted into this document. The two error strings recorded in earlier notes — a name-resolution failure and a self-signed-certificate rejection — are second-hand; the originals are gone.

It did not reproduce under controlled conditions. Treat it as a known unknown rather than an open task.

## Consequences

- **9-d is unblocked.** Use the 2026-08-19 run for the end-to-end record, not the 2026-08-12 one.
- **Run load tests on AC power, lid open, under `caffeinate`.** `docs/step8.md`'s "Generating load" section says so. A run interrupted by sleep produces data indistinguishable from a network failure — that is the whole of this document.
- `observability/prometheus.yml` defines a single job and no self-scrape. That is why the TSDB could not, on its own, distinguish "Prometheus was stalled" from "Prometheus could not reach the backend"; `pmset` settled it from outside. A self-scrape job would make the next such question answerable from the data. Not done here.
- The 2026-08-12 samples age out of Prometheus around **2026-08-27** under the default 15-day retention. Every figure needed has been extracted above, so no re-query should be necessary, but `docker-compose down -v` before that date destroys them early for no reason.

## Findings log

- **2026-08-18** — Record opened while the cause was unknown. Timeline reconstructed from Prometheus. `pmset -g log` then showed every `up` gap covered by a sleep/wake pair, and the 1025.74-second request overlapping a 999-second Clamshell Sleep.
- **2026-08-19** — Controlled re-run: 60/60 successes, no sleep during the run. Open-Meteo reachable from inside the container on three consecutive attempts. Record closed, with the three-minute residual above left unexplained.
- **2026-08-19, record-keeping note** — the TSDB holds about 108 requests for 2026-08-19, not 60. An earlier attempt was killed by tooling after roughly 48 requests, all of which succeeded and all of which are recorded. The clean 60-request run is the one in the window 09:11:37Z–09:24:03Z; use that window when querying this date.
