"""API field-name snapshots: a safety net for refactors (Milestone 27.0a).

Record what the API sends, change the code, record again, and diff:

    .venv/bin/python scripts/key_snapshot.py record before
    .venv/bin/python scripts/key_snapshot.py record after
    .venv/bin/python scripts/key_snapshot.py diff before after

Two views per snapshot:
  - the OpenAPI schema (/openapi.json): every response model's field
    names as clients see them. Deterministic: independent of data.
  - real GET responses: the key paths actually sent. Data-dependent
    (a null today may be an object tomorrow), so differences there can
    be noise; snake_case keys appearing are the sign of an alias bug.

Standard library only; run it with the backend up on port 8000.
"""

import json
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "history.sqlite3"
BASE_URL = "http://127.0.0.1:8000"
SNAKE = re.compile(r"[a-z0-9]_[a-z0-9]")


def get_json(path: str) -> object:
    with urllib.request.urlopen(BASE_URL + path, timeout=60) as response:
        return json.load(response)


def key_paths(value: object, prefix: str = "") -> set[str]:
    """{"a": {"b": 1}, "c": [{"d": 2}]} -> {"a", "a.b", "c", "c[].d"}.

    Every item of a list adds to one shared "[]" path, so the shape does
    not depend on how many items there are.
    """
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, inner in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            paths |= key_paths(inner, path)
    elif isinstance(value, list):
        for item in value:
            paths |= key_paths(item, f"{prefix}[]")
    return paths


def schema_fields(openapi: dict) -> dict[str, list[str]]:
    """Schema name -> its property names, from /openapi.json."""
    schemas = openapi.get("components", {}).get("schemas", {})
    return {
        name: sorted(schema.get("properties", {}))
        for name, schema in sorted(schemas.items())
    }


def endpoints_to_check() -> dict[str, str]:
    """Name -> path, choosing real ids from the running app and the database."""
    paths = {
        "health": "/health",
        "markets": "/markets",
        "deployers": "/deployers",
        "feed": "/feed",
        "leaderboard": "/leaderboard?window=7d&limit=20",
    }
    markets = get_json("/markets")
    live = next((m for m in markets if any(s.get("price") is not None for s in m.get("sides", []))), None)
    if live is not None:
        market_id = live["id"]
        paths.update({
            "market_detail": f"/markets/{market_id}",
            "book": f"/markets/{market_id}/book?side=0",
            "candles": f"/markets/{market_id}/candles?range=1d",
            "elsewhere": f"/markets/{market_id}/elsewhere",
            "links": f"/markets/{market_id}/links",
            "execution": f"/markets/{market_id}/execution?size=100",
        })
    match = next(
        (m for m in markets
         if m.get("category") == "sports" and m.get("parent") and " v " in (m["parent"].get("title") or "")),
        None,
    )
    if match is not None:
        paths["suggestions"] = f"/questions/{match['parent']['id']}/suggestions"
    with sqlite3.connect(DB_PATH) as connection:
        settled = connection.execute(
            "SELECT market_id FROM settlements ORDER BY detected_at DESC LIMIT 1"
        ).fetchone()
    if settled is not None:
        paths["settled_detail"] = f"/markets/{settled[0]}"
    rows = get_json("/leaderboard?window=7d&limit=1").get("rows", [])
    if rows:
        paths["trader"] = f"/traders/{rows[0]['address']}?window=7d"
    return paths


def record(label: str) -> None:
    snapshot: dict[str, object] = {"schemas": schema_fields(get_json("/openapi.json")), "endpoints": {}}
    for name, path in endpoints_to_check().items():
        try:
            body = get_json(path)
            snapshot["endpoints"][name] = {"path": path, "keys": sorted(key_paths(body))}
            print(f"  {name:<15} {len(snapshot['endpoints'][name]['keys']):>4} key paths  {path}")
        except urllib.error.HTTPError as exc:
            snapshot["endpoints"][name] = {"path": path, "error": exc.code}
            print(f"  {name:<15} HTTP {exc.code}  {path}")
    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"keys-{label}.json"
    out.write_text(json.dumps(snapshot, indent=2))
    print(f"{len(snapshot['schemas'])} schemas, {len(snapshot['endpoints'])} endpoints -> {out}")


def diff(before_label: str, after_label: str) -> None:
    before = json.loads((DATA_DIR / f"keys-{before_label}.json").read_text())
    after = json.loads((DATA_DIR / f"keys-{after_label}.json").read_text())
    problems = 0

    print("Schemas (must match exactly):")
    for name in sorted(set(before["schemas"]) | set(after["schemas"])):
        old, new = set(before["schemas"].get(name, [])), set(after["schemas"].get(name, []))
        if name not in after["schemas"] or name not in before["schemas"]:
            problems += 1
            print(f"  {name}: {'removed' if name not in after['schemas'] else 'added'}")
        elif old != new:
            problems += 1
            print(f"  {name}: removed {sorted(old - new)} added {sorted(new - old)}")
    print(f"  {len(after['schemas'])} schemas compared")

    print("Responses (differences may be data noise; snake_case is not):")
    for name in sorted(set(before["endpoints"]) | set(after["endpoints"])):
        old_entry, new_entry = before["endpoints"].get(name, {}), after["endpoints"].get(name, {})
        old, new = set(old_entry.get("keys", [])), set(new_entry.get("keys", []))
        if old == new:
            continue
        added, removed = sorted(new - old), sorted(old - new)
        snake = [path for path in added if SNAKE.search(path.split(".")[-1])]
        problems += bool(snake)
        print(f"  {name}: removed {removed[:6]}{' …' if len(removed) > 6 else ''} "
              f"added {added[:6]}{' …' if len(added) > 6 else ''}")
        if snake:
            print(f"    !! snake_case keys appeared: {snake[:6]}")
    print("NO CONTRACT CHANGES" if problems == 0 else f"{problems} PROBLEM(S): see above")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "record":
        record(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "diff":
        diff(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)