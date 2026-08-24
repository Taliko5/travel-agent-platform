# 9-d End-to-end verification — Pass 1 (evidence)

Per `openspec/changes/step8-metric-design/tasks.md` Section 2. Observations only —
no application code, container configuration or dashboard JSON was touched. No
interpretive prose beyond what is needed to state the verdict; "Verified
End-to-End" wording is composed in pass 2, from this file, not from the running
system.

## Entry gates

**G3 — working tree clean.** NOT clean. Reported before anything else ran, per the gate:

```
$ git status --short
 M openspec/changes/step8-metric-design/specs/observability/spec.md
```

`git diff` shows this is a wording tightening of scenario text already present
(e.g. "raises before producing a response" → "raises before returning a
response"; "the intent... resolved if the graph run had already produced one,
and `unknown` otherwise" replacing a shorter phrasing) — no scenario was added,
removed, or reversed. The file read for scenario text in this pass is the
on-disk (modified) version quoted above. Gate does not block per its own text
("or its contents are reported before anything else runs") — reported, proceeding.

**G1 — backend has not restarted since the run.**

```
$ docker inspect -f '{{.State.StartedAt}}' "$(docker-compose ps -q backend)"
2026-08-19T08:53:38.587770245Z
```

Run window: 2026-08-19T09:11:37Z–09:24:03Z. Container start (08:53:38Z) precedes
the run window. PASS — gate satisfied.

**G2 — TSDB still holds the run.**

```
$ curl -s 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22travel-agent-backend%22%7D&time=2026-08-19T09:20:00Z'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"__name__":"up","instance":"backend:8000","job":"travel-agent-backend"},"value":[1787131200,"1"]}]}}
```

`up` returns a point (value `1`) at the evaluation instant. PASS — gate satisfied.

All three entry gates clear (G3 reported, non-blocking). Proceeding with the eight items.

---

## Coverage table (verdicts)

| Item | Scenario in `specs/observability/spec.md` | Verdict |
|---|---|---|
| 1 | An instrument with no recording call site | PASS |
| 1 | A /chat request completes successfully | PASS |
| 1 | No third status value is ever produced | PASS |
| 2 | The metrics path is requested without a trailing slash | PASS |
| 3 | Prometheus scrapes the configured path | PASS |
| 4 | Panel queries are evaluated against recorded data | PASS |
| 4 | A ratio panel is evaluated before its numerator has ever occurred | PASS |
| 5 | Grafana starts with the repository's provisioning configuration | PASS |
| 6 | A single request's log lines | PASS |
| 7 | The stack idles with no user traffic | PASS |

Item 8 maps to no scenario (open question, recorded in `design.md`) — recorded below, no verdict.

---

## Item 1 — `/metrics/` contents

Maps to: *An instrument with no recording call site*; *A /chat request completes
successfully* (indirectly — labels observed on the histogram); *No third status
value is ever produced* (status label enumeration).

```
$ curl -s -w '\n---HTTP_STATUS:%{http_code}---\n' localhost:8000/metrics/
...
---HTTP_STATUS:200---

$ grep -c "^chat_request_duration_seconds_bucket" metrics_body.txt
48
$ grep -c "^intent_classification_total" metrics_body.txt
8
$ grep "llm_call_duration_seconds" metrics_body.txt
(no output — absent)
$ grep "rag_retrieval_total" metrics_body.txt
# HELP rag_retrieval_total Count of RAG context retrievals.
# TYPE rag_retrieval_total counter
rag_retrieval_total{otel_scope_name="travel-agent-backend",otel_scope_schema_url="",otel_scope_version=""} 0.0
```

Also checked which `status` label values appear on `chat_request_duration_seconds_bucket`
(scenario: *No third status value is ever produced*):

```
$ grep -oE 'status="[a-z]*"' metrics_body.txt | sort -u
status="ok"
```

Only `status="ok"` appears anywhere in the exposed series (consistent with the
run under verification returning HTTP 200 throughout — no error path was
exercised, so this observation cannot show a third value being *rejected*, only
that none was *produced*).

**Verdict: PASS.** `/metrics/` returns 200, `chat_request_duration_seconds_bucket`
(48 series) and `intent_classification_total` (8 series) are present,
`llm_call_duration_seconds` is absent, `rag_retrieval_total` is present at a
label-less 0 — matching the corrected item text exactly. Only `status="ok"`
observed, no third value.

---

## Item 2 — the trailing slash

Maps to: *The metrics path is requested without a trailing slash*.

```
$ curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/metrics
307

$ curl -s -D - -o /dev/null localhost:8000/metrics
HTTP/1.1 307 Temporary Redirect
date: Fri, 21 Aug 2026 14:32:56 GMT
server: uvicorn
content-length: 0
location: http://localhost:8000/metrics/

$ curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/metrics/
200

$ curl -s -L -o /dev/null -w 'final_status=%{http_code} size=%{size_download}\n' localhost:8000/metrics
final_status=200 size=35033
```

**Verdict: PASS.** No-slash path redirects (307) to `/metrics/` via `Location`
header; a redirect-following client (`curl -L`) ends up at 200 with a
non-trivial body (35033 bytes).

---

## Item 3 — the scrape target

Maps to: *Prometheus scrapes the configured path*.

```
$ curl -s 'http://localhost:9090/api/v1/targets' | python3 -m json.tool
...
"job": "travel-agent-backend"
"scrapeUrl": "http://backend:8000/metrics"
"lastError": ""
"health": "up"
"scrapeInterval": "15s"
"scrapeTimeout": "10s"
```

`observability/prometheus.yml`:
```
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: travel-agent-backend
    metrics_path: /metrics
    static_configs:
      - targets: ["backend:8000"]
```
No per-job `scrape_interval` override — the job's effective 15s is the global
default, confirmed by the `/targets` API echoing 15s.

Continuity check (`up` series, no sample absent) over the run window, step 15s:
```
$ curl -s 'http://localhost:9090/api/v1/query_range?query=up%7Bjob%3D%22travel-agent-backend%22%7D&start=2026-08-19T09:11:00Z&end=2026-08-19T09:25:00Z&step=15s'
num samples: 57
first: [1787130660, '1']
last: [1787131500, '1']
non-1 values: []
```
All 57 samples across the 14-minute window equal `1`; none absent, none `0`.

Cross-check at 09:24:00Z:
```
$ curl -s 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22travel-agent-backend%22%7D&time=2026-08-19T09:24:00Z'
value: [1787131440, "1"]
```

**Verdict: PASS.** Target reports `health: up`, `lastError` empty, effective
scrape interval 15s (unoverridden global default), and the `up` series is
continuous (all 1) across the run window at 15s resolution.

---

## Item 4 — the panel queries

Maps to: *Panel queries are evaluated against recorded data*; *A ratio panel is
evaluated before its numerator has ever occurred*.

Expressions read from `targets[].expr` in
`observability/grafana/dashboards/travel-agent-overview.json` (8 total, panel 1
contributing 3):

```
Panel1-p50:  histogram_quantile(0.50, sum by (le) (rate(chat_request_duration_seconds_bucket{status="ok"}[5m])))
Panel1-p95:  histogram_quantile(0.95, sum by (le) (rate(chat_request_duration_seconds_bucket{status="ok"}[5m])))
Panel1-p99:  histogram_quantile(0.99, sum by (le) (rate(chat_request_duration_seconds_bucket{status="ok"}[5m])))
Panel2:      histogram_quantile(0.95, sum by (le, intent) (rate(chat_request_duration_seconds_bucket{status="ok"}[5m])))
Panel3:      sum by (intent) (rate(chat_request_duration_seconds_count[5m]))
Panel4:      (sum(rate(chat_request_duration_seconds_count{status="error"}[5m])) or vector(0)) / sum(rate(chat_request_duration_seconds_count[5m]))
Panel5:      (sum(rate(intent_classification_total{fallback="true"}[5m])) or vector(0)) / sum(rate(intent_classification_total[5m]))
Panel6:      sum by (le) (rate(chat_request_duration_seconds_bucket[5m]))
```

Evaluated via instant query with explicit `time=`, at both 09:20:00Z and
09:24:00Z (cross-check):

```
time=2026-08-19T09:20:00Z
Panel1-p50            -> success, 1 result:  6.294117647058823
Panel1-p95             -> success, 1 result:  9.34
Panel1-p99             -> success, 1 result:  9.867999999999999
Panel2-p95-by-intent  -> success, 4 results: weather=9.625 general=9.75 hotel=6.9 transportation=6.9
Panel3-request-rate    -> success, 4 results: general=0.0175 hotel=0.0211 transportation=0.0211 weather=0.0175
Panel4-error-rate      -> success, 1 result:  0
Panel5-fallback-rate   -> success, 1 result:  0
Panel6-heatmap         -> success, 12 results (le buckets, e.g. +Inf=0.0772, 10.0=0.0772, rest 0)

time=2026-08-19T09:24:00Z — same shape, all non-empty (p50=6.4667 p95=9.5286 p99=9.9057; per-intent and per-le results all present)
```

All 8 expressions return non-empty results at both timestamps.

**Guard investigation** (per tasks.md "Two guards, probably only one exercised" —
checking which of panel 4 / panel 5's `or vector(0)` actually fires):

```
$ # numerator alone, no guard, at 09:20:00Z
panel4 numerator only (no or-guard): sum(rate(chat_request_duration_seconds_count{status="error"}[5m]))
  -> result: []   (absent — no status="error" series exists at all)
panel5 numerator only (no or-guard): sum(rate(intent_classification_total{fallback="true"}[5m]))
  -> result: [{'metric': {}, 'value': [1787131200, '0']}]   (present, already at 0 — seeded)
```

Panel 4's raw numerator is an empty vector (absent) at this instant — its
`or vector(0)` guard is the one doing work, matching the scenario text exactly
("numerator is absent rather than present at zero"). Panel 5's raw numerator is
already present at 0 (counter seeding), so its guard is present but not the one
exercised here — consistent with tasks.md's hint.

**Grafana-side cross-check** (see item 5 below) confirms the same three
representative expressions return identical values through Grafana's datasource
proxy, not just raw Prometheus.

**Verdict: PASS** (both scenarios — non-empty panel data, and the absent-numerator
guard confirmed via panel 4 specifically).

---

## Item 5 — Grafana

Maps to: *Grafana starts with the repository's provisioning configuration*.

```
$ curl -s -u admin:admin http://localhost:3001/api/dashboards/uid/travel-agent-overview
dashboard title: Travel Agent — Overview
meta.provisioned: True
meta.provisionedExternalId: travel-agent-overview.json
num panels: 7
```

Provisioning config on disk:
```
observability/grafana/provisioning/dashboards/*.yml:
apiVersion: 1
providers:
  - name: default
    orgId: 1
    folder: ""
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/dashboards
      foldersFromFilesStructure: true
```

Grafana-to-Prometheus path, queried through Grafana's own API (datasource proxy,
uid `PBFA97CFB590B2093`, not raw Prometheus) for 3 representative expressions at
`time=2026-08-19T09:20:00Z`:

```
Panel1-p50           -> success [{'metric': {}, 'value': [1787131200, '6.294117647058823']}]
Panel4-error-rate     -> success [{'metric': {}, 'value': [1787131200, '0']}]
Panel5-fallback-rate  -> success [{'metric': {}, 'value': [1787131200, '0']}]
```

Values match the raw-Prometheus figures in item 4 exactly, confirming Grafana
reaches the same data through its configured datasource.

Note: whether the panels visually render correctly on screen is explicitly a
human check per tasks.md and is not claimed by this pass.

**Verdict: PASS.** `meta.provisioned: true`, `meta.provisionedExternalId:
"travel-agent-overview.json"` — Grafana's API reports the dashboard as
provisioned and names the source file. Datasource-proxy queries return the same
data as raw Prometheus.

---

## Item 6 — trace and log correlation

Maps to: *A single request's log lines*.

Picked one `/chat` request's pair of log lines (trace_id
`9a75bc31101b2cb8156d96849500cec1`):

```
$ grep '"chat request received"' trace_logs.txt | head -1
{"asctime": "2026-08-19 08:54:57,885", "levelname": "INFO", "name": "api.main", "message": "chat request received", "trace_id": "9a75bc31101b2cb8156d96849500cec1", "span_id": "94e320a01c42d99b"}

$ grep '"chat request completed"' trace_logs.txt | head -1
{"asctime": "2026-08-19 08:55:10,660", "levelname": "INFO", "name": "api.main", "message": "chat request completed", "intent": "weather", "status": "ok", "duration_seconds": 12.766357621992938, "trace_id": "9a75bc31101b2cb8156d96849500cec1", "span_id": "94e320a01c42d99b"}
```

**Verdict: PASS.** Both lines carry a non-null `trace_id`; both share the
identical value (`9a75bc31101b2cb8156d96849500cec1`); the completion line
additionally carries `intent` (`"weather"`), `status` (`"ok"`), and
`duration_seconds` (`12.766357621992938`).

---

## Item 7 — span exclusion

Maps to: *The stack idles with no user traffic*.

Recent-idle check (last 2 minutes, stack currently receiving only compose
healthcheck `/health` polls and Prometheus `/metrics` scrapes, no `/chat`
traffic):

```
$ docker-compose logs backend --since 2m
[26 lines, all plain-text uvicorn access-log lines: "GET /health ... 200 OK",
 "GET /metrics ... 307", "GET /metrics/ ... 200 OK" — no JSON lines]

$ grep '"trace_id"' idle_logs.txt
(no output — zero matches)
```

Full-history check (entire backend log since container start 2026-08-19T08:53:38Z,
covering >2 days and 109 `/chat` requests):

```
$ docker-compose logs backend > full_backend_log.txt; wc -l full_backend_log.txt
47949 full_backend_log.txt

$ grep -cE '"http.target": "/health"|"http.target": "/metrics' full_backend_log.txt
0

$ grep '"name":' full_backend_log.txt | sort | uniq -c | sort -rn
    247 "ChatGoogleGenerativeAI"
    218 "POST /chat http send"
    109 "route_by_intent"
    109 "generate_response"
    109 "classify_intent"
    109 "POST /chat"
    109 "POST /chat http receive"
    109 "LangGraph"
     29 "call_weather_tool"
     27 "call_hotel_tool"
     27 "call_flight_tool"
     26 "retrieve_context"
```

Every exported span name traces back to `/chat` (109 requests, matching the
109-request TSDB figure noted in tasks.md's preconditions). Zero spans name
`/health` or `/metrics` anywhere in the container's lifetime — not just the
idle window.

**Verdict: PASS.** No HTTP spans for `/health` or `/metrics` at any point
observed, including the current idle window; plain-text access-log lines for
those paths exist (expected — see item 8) but carry no `trace_id` / span data.

---

## Item 8 — record, do not fix

Maps to no scenario (open question in `design.md`). Recorded, not fixed, per the item's own instruction.

```
$ docker-compose logs backend --since 2026-08-19T09:11:30Z --until 2026-08-19T09:12:20Z
backend-1  | INFO:     127.0.0.1:40348 - "GET /health HTTP/1.1" 200 OK
backend-1  | INFO:     192.168.97.2:52250 - "GET /metrics HTTP/1.1" 307 Temporary Redirect
backend-1  | INFO:     192.168.97.2:52250 - "GET /metrics/ HTTP/1.1" 200 OK
backend-1  | {"asctime": "2026-08-19 09:11:38,897", "levelname": "INFO", "name": "api.main", "message": "chat request received", "trace_id": "f36271d6aeaf90f71fd5eb4f0277d26b", "span_id": "a893667e46e9afc9"}
backend-1  | {"asctime": "2026-08-19 09:11:38,909", "levelname": "INFO", "name": "google_genai.models", "message": "AFC is enabled with max remote calls: 10.", ...}
...
backend-1  | {
backend-1  |     "name": "POST /chat http receive",
backend-1  |     "context": {
backend-1  |         "trace_id": "0xf36271d6aeaf90f71fd5eb4f0277d26b",
...
```

Three distinct log shapes interleave in the same stream, in this order as
observed: (1) plain-text uvicorn access-log lines (`INFO:     <addr> - "..." <code>`),
(2) single-line structured JSON from the app logger (`{"asctime": ..., "trace_id": ...}`),
(3) multi-line pretty-printed JSON from the OTel span exporter (`{\n  "name": ...`).
Recorded as observed — no fix applied, no `design.md` edit made in this pass.

---

## Scenarios out of scope for this pass (per tasks.md, recorded not tested)

- `Backend has started and no request has been made` — needs a restart, forbidden by G1.
- `A /chat request fails` — run returned HTTP 200 throughout; no failure occurred.
- Both scenarios of `Metric Recording Is Additive` — test-suite question, not end-to-end.
- `Seeding is attempted before the provider is installed`, `A new intent is added to the classifier`, all three scenarios of `Reproducible Load Generation`.

---

## Stop rule applied

No failures encountered in G1–G3, item 1, or item 3 — nothing triggered the stop
condition. Items 6, 7, 8 all completed (their independence from each other was
not tested since none failed). All items ran; verification did not stop early.

---

# Pass 1b — items 3 and 6 re-run (2026-08-21, later same day)

Items 3 and 6 were re-scoped in `tasks.md` after pass 1: pass 1's methods could
not detect what their scenarios actually require (see the "Method gap" notes
under each item in Section 2 of `tasks.md`). This section supersedes pass 1's
entries for items 3 and 6 only. Pass 1's entries for items 1, 2, 4, 5, 7 and 8
stand unchanged above.

Run order: item 6 first, then item 3, per instruction.

## Entry gates (re-checked)

**G1 — backend has not restarted since the run.**
```
$ docker inspect -f '{{.State.StartedAt}}' "$(docker-compose ps -q backend)"
2026-08-19T08:53:38.587770245Z
```
Unchanged since pass 1; still precedes the run window (09:11:37Z–09:24:03Z). PASS.

**G2 — TSDB still holds the run.**
```
$ curl -s 'http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22travel-agent-backend%22%7D&time=2026-08-19T09:20:00Z'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{"__name__":"up","instance":"backend:8000","job":"travel-agent-backend"},"value":[1787131200,"1"]}]}}
```
PASS.

**G3 — working tree clean.**
```
$ git status --short
(no output)
```
Clean. PASS — no contents to report this time (the spec.md wording diff present
during pass 1 is no longer in the working tree).

All three gates clear. Proceeding.

---

## Item 6 (re-run) — trace and log correlation

**Supersedes the item 6 entry in pass 1**, which checked only the two named
application log lines (`"chat request received"` / `"chat request completed"`)
for a `trace_id`. This entry enumerates every log line one `/chat` request
emits, per the re-scoped item text, and does not grep for `"trace_id"` as the
selection method (grepping for the string that should be present cannot find
the lines where it's missing).

Maps to: *A single request's log lines*.

**Request chosen:** trace_id `f36271d6aeaf90f71fd5eb4f0277d26b`, the first
`/chat` request in the run window (received 2026-08-19T09:11:38.897Z).

**Window boundary.** "While it was being handled" is taken as the receipt log
line through the line marking the response actually leaving the server — the
uvicorn access log line for that request — not the application's own
`"chat request completed"` line, which fires one line earlier. The next
request's own `"chat request received"` line does not appear until well after
this window closes, confirming the load generator ran these two requests
sequentially rather than concurrently, so nothing outside this request's own
lines falls inside the window:

```
$ docker-compose logs backend > full_backend_log_1b.txt   # 49030 lines, full history
$ grep -n '"chat request received"' full_backend_log_1b.txt | head -1
17814:{"asctime": "2026-08-19 09:11:38,897", ..., "message": "chat request received", "trace_id": "f36271d6aeaf90f71fd5eb4f0277d26b", ...}
$ grep -n '"chat request completed"' full_backend_log_1b.txt | head -1
18005:{"asctime": "2026-08-19 09:11:46,708", ..., "message": "chat request completed", "intent": "weather", "status": "ok", "duration_seconds": 7.81067069596611, "trace_id": "f36271d6aeaf90f71fd5eb4f0277d26b", ...}
$ sed -n '18005,18007p' full_backend_log_1b.txt
{"asctime": "2026-08-19 09:11:46,708", ..., "message": "chat request completed", ...}
INFO:     192.168.97.1:41712 - "POST /chat HTTP/1.1" 200 OK
{
    "name": "ChatGoogleGenerativeAI",
    ...
```
Window taken: lines 17814–18006 inclusive (193 physical lines).

**Method.** Parsed the window into logical log records — reconstructing the
OTel console exporter's multi-line pretty-printed JSON span blocks into single
records (they are one `logger`/exporter call each, just wrapped across many
physical lines), so that the unit being counted matches "a log line it
emits" rather than an artifact of pretty-printing. For each record, checked for
a `trace_id` field (top-level for app-logger JSON, `context.trace_id` for
OTel span-export JSON) or, for a record with no JSON structure at all, recorded
it as carrying no `trace_id`:

```
Total records: 17
[ 0] json1  trace_id=f36271d6aeaf90f71fd5eb4f0277d26b   "chat request received"
[ 1] json1  trace_id=f36271d6aeaf90f71fd5eb4f0277d26b   google_genai.models
[ 2] json1  trace_id=f36271d6aeaf90f71fd5eb4f0277d26b   httpx (generateContent)
[ 3] json1  trace_id=f36271d6aeaf90f71fd5eb4f0277d26b   google_genai.models
[ 4] json1  trace_id=f36271d6aeaf90f71fd5eb4f0277d26b   httpx (generateContent)
[ 5] json1  trace_id=f36271d6aeaf90f71fd5eb4f0277d26b   httpx (geocoding-api)
[ 6] json1  trace_id=f36271d6aeaf90f71fd5eb4f0277d26b   httpx (open-meteo forecast)
[ 7] json1  trace_id=f36271d6aeaf90f71fd5eb4f0277d26b   google_genai.models
[ 8] jsonN  trace_id=0xf36271d6aeaf90f71fd5eb4f0277d26b  (OTel span export block)
[ 9] jsonN  trace_id=0xf36271d6aeaf90f71fd5eb4f0277d26b  (OTel span export block)
[10] jsonN  trace_id=0xf36271d6aeaf90f71fd5eb4f0277d26b  (OTel span export block)
[11] jsonN  trace_id=0xf36271d6aeaf90f71fd5eb4f0277d26b  (OTel span export block)
[12] jsonN  trace_id=0xf36271d6aeaf90f71fd5eb4f0277d26b  (OTel span export block)
[13] jsonN  trace_id=0xf36271d6aeaf90f71fd5eb4f0277d26b  (OTel span export block)
[14] json1  trace_id=f36271d6aeaf90f71fd5eb4f0277d26b   httpx (generateContent)
[15] json1  trace_id=f36271d6aeaf90f71fd5eb4f0277d26b   "chat request completed"
[16] plain  trace_id=MISSING                             INFO:     192.168.97.1:41712 - "POST /chat HTTP/1.1" 200 OK

Records WITHOUT a trace_id: 1 / 17
  [16] plain: 'INFO:     192.168.97.1:41712 - "POST /chat HTTP/1.1" 200 OK'

Distinct trace_id values (0x-prefix normalized) among records that carry one: {'f36271d6aeaf90f71fd5eb4f0277d26b'}
```

The completion line (`[15]`) carries `intent: "weather"`, `status: "ok"`,
`duration_seconds: 7.81067069596611`, and the same `trace_id` — that part of
the scenario holds.

16 of the 17 records this request emits while being handled carry
`trace_id: f36271d6aeaf90f71fd5eb4f0277d26b` (or the same value 0x-prefixed, in
the OTel span-export context object) — all one value, consistent with "all of
that request's log lines SHALL share the same trace_id". The 17th record — the
uvicorn access log line uvicorn itself emits when the response leaves the
server — carries no `trace_id` field at all; it is plain text, not JSON, and
has no structured fields of any kind.

**Verdict: FAIL.** The scenario requires "each log line it emits SHALL carry a
non-null trace_id" without qualification. One of the seventeen log lines this
request emits while being handled does not. This is not a hypothetical: the
line exists, is emitted by the same process while handling this exact request,
and is findable without special-casing. Whether that line is properly
in-scope for the requirement — i.e., whether "log lines it emits" was meant to
reach uvicorn's own access-logging rather than only the application's own
logger — is the open question already recorded in `design.md`, restated there
per the pass-1-follow-up edit. This entry supplies the evidence that question
was waiting on; the requirement as written does not hold against the system as
built.

---

## Item 3 (re-run) — the scrape target

**Supersedes the item 3 entry in pass 1**, whose continuity check used
`query_range` at a 15s step — a method that cannot distinguish a real gap
shorter than Prometheus's 5-minute staleness lookback from an unbroken series,
because a missing sample is silently filled by carrying the preceding one
forward. This entry counts raw stored samples instead.

Maps to: *Prometheus scrapes the configured path*.

**Target health and effective interval** (re-checked fresh):
```
$ curl -s 'http://localhost:9090/api/v1/targets' | jq '.data.activeTargets[] | select(.labels.job=="travel-agent-backend")'
{
  "discoveredLabels": { ..., "__scrape_interval__": "15s", "__scrape_timeout__": "10s", ... },
  "labels": {"instance": "backend:8000", "job": "travel-agent-backend"},
  "scrapeUrl": "http://backend:8000/metrics",
  "lastError": "",
  "health": "up",
  "scrapeInterval": "15s",
  "scrapeTimeout": "10s"
}
```
`health: up`, `lastError` empty. `observability/prometheus.yml` sets no
per-job `scrape_interval`, so 15s is the unoverridden global default — echoed
back by the target's own `__scrape_interval__` discovered label, not just
inferred from the config file.

**Continuity, by raw sample count.** A range-vector selector evaluated via
the *instant* query endpoint (`/api/v1/query`, not `/api/v1/query_range`)
returns the actual stored samples inside the lookback window — not values
resampled at a chosen step — because `[Ns]` on a selector is Prometheus's raw
range-vector matrix, and only `/api/v1/query` returns it as a matrix rather
than reducing it. `count_over_time`/`query_range` at any step still evaluate
the selector at chosen instants and would repeat the same staleness-masking
flaw as pass 1; this does not, because no resampling happens between the raw
samples and the output points.

```
$ python3 -c "... query = 'up{job=\"travel-agent-backend\"}[900s]', time='2026-08-19T09:24:30Z' ..."
resultType: matrix
total raw samples fetched (900s lookback): 60
samples strictly inside run window [09:11:37Z, 09:24:03Z]: 49
window duration: 746s
expected count at 15s interval (746/15): 49.73
first in-window sample: 2026-08-19 09:11:51.577000+00:00  value=1
last in-window sample:  2026-08-19 09:23:51.566000+00:00  value=1
gap min/max across all 60 fetched samples: 14.909s / 15.091s
any value != 1: none
```

49 raw samples fall inside the 746-second run window against an expectation of
~49.73 for an unbroken 15s-interval scrape (the fractional difference is
window-edge alignment, not a missing sample — the window's own boundaries do
not land exactly on scrape instants). Across all 60 samples fetched in the
wider 900s lookback, the largest gap between any two consecutive raw samples
is 15.091s — essentially one scrape interval, with sub-second jitter, and
nowhere near large enough to represent a skipped scrape. Every sample value
is `1`.

**Verdict: PASS.** The scrape succeeds (`health: up`, no error), the `up`
series is 1 throughout, and the raw-sample-count method — the one the
scenario's continuity clause actually requires — finds no gap: sample spacing
stays within jitter of the effective 15s interval for the full run window.

---

## Pass 1b stop rule

Item 6 (re-run) is a **failure**. Per the stop rule, items 6, 7 and 8 are
"record and continue" — independent of one another and of item 3 — so this
failure does not block item 3 or invalidate work already recorded for items 1,
2, 4, 5, 7, 8. Item 3 (re-run) passed. No stop condition was triggered; both
re-runs completed.
