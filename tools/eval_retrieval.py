#!/usr/bin/env python3
"""Measure retrieval quality against a hand-made question set.

CSV columns: question,department,cohort_id,expected_title
Usage:  AI_SERVICE_KEY=... python tools/eval_retrieval.py eval.csv
"""
import csv
import os
import sys

import requests

BASE = os.environ.get("AI_SERVICE_URL", "http://localhost:8000")
KEY = os.environ["AI_SERVICE_KEY"]
K = int(os.environ.get("TOP_K", "5"))

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
hits_at_k, rr_sum = 0, 0.0

for row in rows:
    r = requests.post(
        f"{BASE}/v1/search",
        headers={"x-api-key": KEY},
        json={"query": row["question"], "department": row["department"],
              "cohort_id": row["cohort_id"], "top_k": K, "score_threshold": 0.0},
        timeout=30,
    )
    r.raise_for_status()
    titles = [h["title"] for h in r.json()["hits"]]
    rank = next((i for i, t in enumerate(titles, 1) if t == row["expected_title"]), None)
    if rank:
        hits_at_k += 1
        rr_sum += 1 / rank
    else:
        print("MISS:", row["question"], "->", titles[:3])

n = len(rows)
print(f"hit@{K}: {hits_at_k}/{n} = {hits_at_k / n:.0%}    MRR: {rr_sum / n:.3f}")
