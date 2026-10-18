#!/usr/bin/env python3
"""Exit 0 if this week's digest run looks healthy. Schedule it on Mondays, about 2 hours
after the digest job (for example 08:00 when the job runs at 06:00).

Exit codes: 0 healthy, 1 alert (no run, failures, or undelivered digests), 2 still running.
"""
import os
import sys

import requests

BASE = os.environ.get("AI_SERVICE_URL", "http://localhost:8000")
HEADERS = {"x-api-key": os.environ["AI_SERVICE_KEY"]}


def get(path):
    return requests.get(f"{BASE}{path}", headers=HEADERS, timeout=15)


r = get("/v1/digests/run-status")
if r.status_code == 404:
    print("ALERT: no digest run recorded for this week")
    sys.exit(1)
r.raise_for_status()
s = r.json()
total, done, empty, failed = (int(s[k]) for k in ("total", "done", "empty", "failed"))
print(f"week {s['week']}: total={total} done={done} empty={empty} failed={failed}")

problems = []
if failed:
    problems.append(f"{failed} segment(s) failed")

listing = get("/v1/digests").json()["digests"]
undelivered = [d["segment_id"] for d in listing if d["status"] == "published" and not d["delivered"]]
if undelivered:
    problems.append(f"published but not delivered: {', '.join(undelivered)}")

if problems:
    print("ALERT:", "; ".join(problems))
    sys.exit(1)
if done + empty + failed < total:
    print("Run still in progress")
    sys.exit(2)
print("OK")
