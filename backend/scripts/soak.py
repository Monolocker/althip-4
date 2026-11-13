"""Soak test recorder and summary (Milestone 25.2).

Record: samples the running backend every --interval seconds and appends
one CSV row per sample under backend/data/ (gitignored).

    .venv/bin/python scripts/soak.py record
    .venv/bin/python scripts/soak.py record --interval 10 --hours 0.05

Summary: reads a recording (and optionally the uvicorn log) and prints
how every measurement moved over the run.

    .venv/bin/python scripts/soak.py summary data/soak-20261113-210000.csv --log data/soak-uvicorn.log

Standard library only: a measuring tool should not add dependencies to
the app it measures.
"""

import argparse
import csv
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "history.sqlite3"
BASE_URL = "http://127.0.0.1:8000"

# /health timestamps become ages at sampling time: "how long since the
# task last did its job" is what reveals a task that died silently.
AGE_FIELDS = (
    "health.bookSweep.lastCompletedAt",
    "health.history.lastRecordedAt",
    "health.tradeWatch.lastTradeAt",
    "health.fillCollect.lastFetchAt",
)

# Assumptions for flagging, from each loop's own interval: a sweep pass
# takes 180 s and history slots are 300 s, so twice that plus a margin
# means a missed cycle. Trade and fill ages depend on market activity
# and on the queue, so they are reported but never flagged.
AGE_LIMITS = {
    "health.bookSweep.lastCompletedAtAgeSeconds": 400,
    "health.history.lastRecordedAtAgeSeconds": 660,
}


# ---------------------------------------------------------------
# Recording
# ---------------------------------------------------------------

def flatten(value: object, prefix: str, out: dict[str, object]) -> None:
    """{"a": {"b": 1}} -> {"prefix.a.b": 1}, so nested JSON fits a CSV row."""
    if isinstance(value, dict):
        for key, inner in value.items():
            flatten(inner, f"{prefix}.{key}", out)
    else:
        out[prefix] = value


def get_json(path: str) -> tuple[dict, float]:
    """GET one endpoint: (parsed JSON, milliseconds it took)."""
    started = time.perf_counter()
    with urllib.request.urlopen(BASE_URL + path, timeout=10) as response:
        body = json.load(response)
    return body, (time.perf_counter() - started) * 1000


def rss_kib(pid: int) -> int | None:
    """Resident memory of the backend process, read from outside it.

    `ps -o rss=` reports kibibytes on both macOS and Linux.
    """
    result = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, check=False
    )
    text = result.stdout.strip()
    return int(text) if text.isdigit() else None


def file_bytes(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return None


def age_seconds(stamp: object, now: datetime) -> float | None:
    if not isinstance(stamp, str):
        return None
    return round((now - datetime.fromisoformat(stamp)).total_seconds(), 1)


def take_sample(started: float) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    row: dict[str, object] = {
        "ts": now.isoformat(timespec="seconds"),
        "elapsedSeconds": round(time.monotonic() - started),
        "ok": 1,
        "error": "",
        # The database is measured from disk, so it is recorded even
        # when the backend does not answer.
        "dbBytes": file_bytes(DB_PATH),
        "walBytes": file_bytes(DB_PATH.with_name(DB_PATH.name + "-wal")),
        "shmBytes": file_bytes(DB_PATH.with_name(DB_PATH.name + "-shm")),
    }
    try:
        health, health_ms = get_json("/health")
        runtime, _ = get_json("/debug/runtime")
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
        row["ok"] = 0
        row["error"] = f"{type(exc).__name__}: {exc}"
        return row
    # /health is cheap, so its response time shows whether the event
    # loop was blocked by something else when the sample was taken.
    row["healthMs"] = round(health_ms, 1)
    flat: dict[str, object] = {}
    flatten(health, "health", flat)
    flatten(runtime, "runtime", flat)
    for field in AGE_FIELDS:
        flat[field + "AgeSeconds"] = age_seconds(flat.pop(field, None), now)
    pid = flat.get("runtime.process.pid")
    row["rssKib"] = rss_kib(pid) if isinstance(pid, int) else None
    row.update(flat)
    return row


def record(interval: float, hours: float | None) -> None:
    started = time.monotonic()
    first = take_sample(started)
    if not first["ok"]:
        sys.exit(f"Backend not reachable at {BASE_URL}: {first['error']}")
    # The first good sample fixes the columns; later failures leave the
    # backend's columns blank instead of changing the header.
    columns = list(first)
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"soak-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.csv"
    deadline = started + hours * 3600 if hours is not None else None
    rows = 0
    print(f"Recording to {path} every {interval:g}s (Ctrl-C to stop)")
    try:
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            row = first
            while True:
                writer.writerow(row)
                handle.flush()  # a crash or Ctrl-C keeps every row so far
                rows += 1
                print(
                    f"{row['ts']}  ok={row['ok']}  rss={row.get('rssKib')} KiB  "
                    f"gc={row.get('runtime.process.gcObjects')}  "
                    f"health={row.get('healthMs')} ms  {row['error']}"
                )
                if deadline is not None and time.monotonic() + interval > deadline:
                    break
                time.sleep(interval)
                row = take_sample(started)
    except KeyboardInterrupt:
        pass
    print(f"Wrote {rows} rows to {path}")


# ---------------------------------------------------------------
# Summary
# ---------------------------------------------------------------

def number(text: str | None) -> float | None:
    if text in (None, "", "None"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def slope_per_hour(points: list[tuple[float, float]]) -> float | None:
    """Least-squares trend: how much the value changes per hour."""
    if len(points) < 3 or len({x for x, _ in points}) < 2:
        return None
    hours = [x / 3600 for x, _ in points]
    return statistics.linear_regression(hours, [y for _, y in points]).slope


def fmt(value: float | None) -> str:
    if value is None:
        return "-"
    if abs(value) >= 100 or value == int(value):
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def summarize_csv(path: Path) -> None:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        sys.exit(f"{path} has no rows")
    good = [row for row in rows if row["ok"] == "1"]
    pids = [row.get("runtime.process.pid") for row in good]
    restarts = sum(1 for before, after in zip(pids, pids[1:]) if before != after)
    elapsed = number(rows[-1]["elapsedSeconds"]) or 0
    print(f"Run: {rows[0]['ts']} -> {rows[-1]['ts']} ({elapsed / 3600:.2f} h)")
    print(f"Samples: {len(rows)}, backend unreachable: {len(rows) - len(good)}, "
          f"process restarts: {restarts}")
    for row in rows:
        if row["ok"] != "1":
            print(f"  unreachable at {row['ts']}: {row['error']}")

    # Warm-up: caches fill as the app is used, then should level off.
    # The second half's slope says whether they are STILL growing.
    half = number(good[len(good) // 2]["elapsedSeconds"]) if good else 0
    trend_columns = ["rssKib", "dbBytes", "walBytes", "shmBytes"] + [
        column for column in rows[0]
        if column.startswith("runtime.") and column != "runtime.process.pid"
        and column != "runtime.process.uptimeSeconds"
    ]
    print()
    print(f"{'measurement':<42} {'first':>12} {'last':>12} {'min':>12} "
          f"{'max':>12} {'/h all':>10} {'/h 2nd half':>12}")
    for column in trend_columns:
        points = [
            (number(row["elapsedSeconds"]) or 0, value)
            for row in rows
            if (value := number(row.get(column))) is not None
        ]
        if not points:
            continue
        values = [y for _, y in points]
        late = [(x, y) for x, y in points if half is not None and x >= half]
        name = column.removeprefix("runtime.")
        print(f"{name:<42} {fmt(values[0]):>12} {fmt(values[-1]):>12} "
              f"{fmt(min(values)):>12} {fmt(max(values)):>12} "
              f"{fmt(slope_per_hour(points)):>10} {fmt(slope_per_hour(late)):>12}")

    latencies = sorted(v for row in good if (v := number(row.get("healthMs"))) is not None)
    if latencies:
        p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]
        print(f"\n/health response ms: median {fmt(statistics.median(latencies))}, "
              f"p95 {fmt(p95)}, max {fmt(latencies[-1])}")

    print("\nBackground tasks (max age = longest gap since the task last worked):")
    for field in AGE_FIELDS:
        column = field + "AgeSeconds"
        ages = [v for row in good if (v := number(row.get(column))) is not None]
        if not ages:
            print(f"  {column}: never set")
            continue
        limit = AGE_LIMITS.get(column)
        flag = f"  <- over {limit}s" if limit is not None and max(ages) > limit else ""
        print(f"  {column}: median {fmt(statistics.median(ages))}, max {fmt(max(ages))}{flag}")
    connected = [row.get("health.tradeWatch.connected") for row in good]
    if connected:
        share = sum(1 for c in connected if c == "True") / len(connected)
        print(f"  tradeWatch connected in {share:.0%} of samples")
    last = good[-1] if good else {}
    for column in (
        "health.bookSweep.lastFailures",
        "health.history.pendingSettlements",
        "health.fillCollect.tradersDue",
        "health.fillCollect.needsBackfill",
        "health.fillCollect.fillsStored",
        "health.tradeWatch.tradersKnown",
    ):
        print(f"  {column}: first {good[0].get(column) if good else '-'}, "
              f"last {last.get(column, '-')}")


# One log line from backend/logging.json: "<time> <LEVEL> <logger>: <message>"
LOG_LINE = re.compile(r"^(\S+) (DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+(\S+): (.*)$")
ACCESS = re.compile(r'"(GET|POST|DELETE|PUT|PATCH|OPTIONS|HEAD) (\S+) HTTP/[\d.]+" (\d{3})')


def message_shape(text: str) -> str:
    """Group similar messages: addresses and numbers become placeholders."""
    text = re.sub(r"0x[0-9a-fA-F]{6,}", "0x…", text)
    text = re.sub(r"#?\d+(\.\d+)?", "N", text)
    return text[:110]


def summarize_log(path: Path) -> None:
    levels: Counter[str] = Counter()
    problems: Counter[tuple[str, str, str]] = Counter()
    statuses: Counter[str] = Counter()
    requests: Counter[str] = Counter()
    server_errors: Counter[tuple[str, str]] = Counter()
    # A chained exception prints several "Traceback" headers, joined by
    # "The above exception was the direct cause..." or "During handling
    # of the above exception...". Count each chain once.
    chains = 0
    previous = ""
    with path.open(errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if line.startswith("Traceback") and not previous.startswith(("The above", "During handling")):
                chains += 1
            if line.strip():
                previous = line
            match = LOG_LINE.match(line)
            if match is None:
                continue
            _, level, logger, message = match.groups()
            levels[level] += 1
            if logger == "uvicorn.access":
                access = ACCESS.search(message)
                if access:
                    method, target, status = access.groups()
                    route = re.sub(r"/\d+", "/{id}", target.split("?")[0])
                    statuses[status[0] + "xx"] += 1
                    requests[f"{method} {route}"] += 1
                    if status.startswith("5"):
                        server_errors[(f"{method} {route}", status)] += 1
            elif level in ("WARNING", "ERROR", "CRITICAL"):
                problems[(level, logger, message_shape(message))] += 1

    print(f"\nLog {path.name}: lines by level {dict(levels)}, exception tracebacks {chains}")
    print(f"HTTP responses: {dict(sorted(statuses.items()))}")
    print("Requests by route (shows whether the open tab kept polling):")
    for route, count in requests.most_common():
        print(f"  {count:>7}  {route}")
    if server_errors:
        print("5xx responses:")
        for (route, status), count in server_errors.most_common():
            print(f"  {count:>7}  {status} {route}")
    if problems:
        print("Warnings and errors, grouped:")
        for (level, logger, shape), count in problems.most_common(15):
            print(f"  {count:>7}  {level:<8} {logger}: {shape}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    rec = commands.add_parser("record", help="sample the running backend into a CSV")
    rec.add_argument("--interval", type=float, default=60.0, help="seconds between samples")
    rec.add_argument("--hours", type=float, default=None, help="stop after this long")
    summ = commands.add_parser("summary", help="summarize a recording")
    summ.add_argument("csv", type=Path)
    summ.add_argument("--log", type=Path, default=None, help="uvicorn log from the same run")
    args = parser.parse_args()
    if args.command == "record":
        record(args.interval, args.hours)
    else:
        summarize_csv(args.csv)
        if args.log is not None:
            summarize_log(args.log)


if __name__ == "__main__":
    main()