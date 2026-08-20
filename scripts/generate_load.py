#!/usr/bin/env python3
"""Generate POST /chat load against a running travel-agent-platform backend.

PromQL `rate()` needs several scrape intervals of data before it produces
anything readable. Hand-issued `curl` calls produce a handful of points and
near-zero rates, which makes the Grafana dashboard look broken when it isn't.
This script sends a configurable number of `/chat` requests, cycling through
prompts that exercise all four `route_by_intent` branches (weather,
transportation/flight, hotel, general), so every `intent` label value shows
up in the resulting metrics.

Runs on the host against the docker-compose stack (not inside a container)
and talks to the backend over HTTP, so it needs only the standard library
plus `httpx` (already in backend/requirements.txt) -- no new dependency.

Rate limiting matters: the backend's classify_intent/generate_response calls
go to the Gemini free tier, which enforces a requests-per-minute cap. The
defaults below (60 requests, concurrency 1, 6.0s delay) work out to roughly
10 requests/minute, which the free tier tolerates -- this rate was run by
hand on 2026-08-11, 60 requests at 6s intervals, all 200, no throttling.
Do not raise these defaults casually: --concurrency 2 --delay 1.0 works out
to roughly 120 requests/minute, which the free tier rejects. --requests,
--concurrency, --delay, and --base-url exist so a caller with a paid Gemini
key can opt into more load explicitly.

A single run at the defaults takes roughly 13 minutes, not the six that the
delay alone suggests: --delay is the gap *between* requests, and each request
itself takes about 7s against the Gemini free tier (the measured per-intent
latencies are in docs/step8-task9c9d.md). 60 x (~7s + 6s) is about 13
minutes. That is expected -- if the script appears to hang, it probably
hasn't. Scale the estimate up if the backend is slower than that.
"""

import argparse
import asyncio
import itertools
import statistics
import sys
import time
from dataclasses import dataclass

import httpx

# At least two variants per branch, per the load-generation spec, so the
# resulting data isn't perfectly uniform.
PROMPTS: dict[str, list[str]] = {
    "weather": [
        "What is the weather in Fukuoka?",
        "What's the weather like in Riga right now?",
    ],
    "transportation": [
        "Cheap flights to Riga",
        "Show me flights from Tokyo to Lima",
    ],
    "hotel": [
        "Find me a hotel in Lima",
        "Best hotels in Fukuoka?",
    ],
    "general": [
        "What should I know before visiting Abu Dhabi?",
        "What food should I try in Kyoto?",
    ],
}


@dataclass
class RequestResult:
    target_branch: str
    intent: str | None
    status: int | str
    latency: float


def _build_request_sequence() -> list[tuple[str, str]]:
    """Interleave branches and variants: weather1, transportation1, hotel1,
    general1, weather2, transportation2, ... so consecutive requests don't
    repeat the same branch or the same wording."""
    branches = list(PROMPTS)
    max_variants = max(len(variants) for variants in PROMPTS.values())
    sequence: list[tuple[str, str]] = []
    for i in range(max_variants):
        for branch in branches:
            variants = PROMPTS[branch]
            sequence.append((branch, variants[i % len(variants)]))
    return sequence


async def _run_worker(
    worker_id: int,
    batch: list[tuple[str, str]],
    base_url: str,
    delay: float,
    client: httpx.AsyncClient,
    results: list[RequestResult],
) -> None:
    last_index = len(batch) - 1
    for index, (target_branch, prompt) in enumerate(batch):
        started = time.perf_counter()
        try:
            response = await client.post(f"{base_url}/chat", json={"message": prompt})
            elapsed = time.perf_counter() - started
            status: int | str = response.status_code
            intent: str | None = None
            if response.status_code == 200:
                try:
                    intent = response.json().get("intent")
                except ValueError:
                    intent = None
            else:
                print(
                    f"[worker {worker_id}] non-200 response: "
                    f"status={response.status_code} body={response.text}",
                    file=sys.stderr,
                )
            # flush: piped into tee, so an interrupted run still leaves its log
            print(
                f"[worker {worker_id}] target={target_branch} "
                f"intent={intent or '-'} status={status} latency={elapsed:.2f}s",
                flush=True,
            )
        except httpx.HTTPError as exc:
            elapsed = time.perf_counter() - started
            status = "error"
            intent = None
            print(f"[worker {worker_id}] request failed: {exc!r}", file=sys.stderr)
        results.append(
            RequestResult(
                target_branch=target_branch,
                intent=intent,
                status=status,
                latency=elapsed,
            )
        )
        if delay > 0 and index != last_index:
            await asyncio.sleep(delay)


def _print_summary(
    results: list[RequestResult], wall_clock: float, requested: int, concurrency: int
) -> None:
    print()
    print("=== Summary ===")
    print(
        f"Requests sent: {len(results)} (requested: {requested}, concurrency: {concurrency})"
    )
    print(f"Wall-clock time: {wall_clock:.1f}s")
    print()

    intent_counts: dict[str, int] = {}
    for result in results:
        if result.intent:
            intent_counts[result.intent] = intent_counts.get(result.intent, 0) + 1
    print("Per-intent counts (classified intent, successful requests only):")
    if intent_counts:
        for intent, count in sorted(intent_counts.items()):
            print(f"  {intent}: {count}")
    else:
        print("  (none -- no successful responses)")
    print()

    status_counts: dict[str, int] = {}
    for result in results:
        key = str(result.status)
        status_counts[key] = status_counts.get(key, 0) + 1
    print("HTTP status counts:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    print()

    latencies = [result.latency for result in results]
    print("Latency (client-observed, seconds):")
    if latencies:
        print(f"  min:  {min(latencies):.2f}")
        print(f"  mean: {statistics.mean(latencies):.2f}")
        print(f"  max:  {max(latencies):.2f}")
    else:
        print("  (no requests completed)")


async def _run(args: argparse.Namespace) -> None:
    sequence = _build_request_sequence()
    assignments = list(itertools.islice(itertools.cycle(sequence), args.requests))

    worker_batches: list[list[tuple[str, str]]] = [[] for _ in range(args.concurrency)]
    for i, item in enumerate(assignments):
        worker_batches[i % args.concurrency].append(item)

    results: list[RequestResult] = []
    overall_start = time.perf_counter()

    # Client-side ceiling, not a spec requirement: it stops one pathological
    # request from wedging the whole run, as happened on 2026-08-12. Know the
    # consequence before comparing logs: the backend keeps working after the
    # client gives up, and chat_request_duration_seconds is recorded
    # server-side, so Prometheus can report a much larger duration than the
    # latency printed here. See docs/step8-host-network.md.
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        await asyncio.gather(
            *(
                _run_worker(
                    worker_id, batch, args.base_url, args.delay, client, results
                )
                for worker_id, batch in enumerate(worker_batches)
            )
        )

    wall_clock = time.perf_counter() - overall_start
    _print_summary(results, wall_clock, args.requests, args.concurrency)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="generate_load.py",
        description=(
            "Generate POST /chat load against a running travel-agent-platform "
            "backend so Prometheus has enough scrape intervals of data for "
            "rate()-based Grafana panels to read as more than noise. Runs on "
            "the host against the docker-compose stack, not inside a container."
        ),
        epilog=(
            "Rate limiting: the backend's LLM calls go to the Gemini free tier, "
            "which enforces a requests-per-minute cap. The defaults below "
            "(60 requests, concurrency 1, 6.0s delay) work out to roughly "
            "10 requests/minute, which the free tier tolerates -- this was run "
            "by hand on 2026-08-11 with no throttling. Do not raise these "
            "defaults casually: --concurrency 2 --delay 1.0 works out to "
            "roughly 120 requests/minute and will be rejected by the free "
            "tier. --requests, --concurrency, --delay, and --base-url exist so "
            "a caller with a paid Gemini key can opt into more load "
            "explicitly. A single run at the defaults takes roughly 13 "
            "minutes: --delay is the gap between requests, and each request "
            "itself takes about 7 seconds, so 60 x (7 + 6) seconds -- that "
            "is expected, not a hang."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=60,
        help="Total number of POST /chat requests to send (default: 60).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help=(
            "Number of concurrent workers (default: 1). Keep at 1 unless "
            "using a paid Gemini key -- see the rate-limiting note below."
        ),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=6.0,
        help=(
            "Seconds between requests, per worker (default: 6.0). Keep at "
            "6.0 or higher unless using a paid Gemini key."
        ),
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the running backend (default: http://localhost:8000).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.requests <= 0:
        print("error: --requests must be positive", file=sys.stderr)
        return 2
    if args.concurrency <= 0:
        print("error: --concurrency must be positive", file=sys.stderr)
        return 2

    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
