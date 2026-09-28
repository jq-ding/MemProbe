#!/usr/bin/env python3
"""
merge_reports.py — combine several report JSONs into one so that the multi-system analysis scripts (bootstrap.py paired / probe, paper_tables.py) can compare your system against the paper's systems on the same episodes.

    python src/analysis/merge_reports.py \
        results/suite56/reports/baselines_report_ALL_gemini.json results/mine/report.json \
        --out results/mine/merged.json
    python src/analysis/bootstrap.py paired --report results/mine/merged.json \
        --only-pairs mysys_full:amem_full,mysys_full:full_context

"""
import argparse, json, sys
from pathlib import Path

SKIP = {"stored_memories", "meta", "episode_metadata"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("reports", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()
    merged, origin = {}, {}
    for r in a.reports:
        d = json.load(open(r))
        for k, v in d.items():
            if k in SKIP or not isinstance(v, dict):
                continue
            if k in merged and not a.overwrite:
                sys.exit(f"baseline key '{k}' in both {origin[k]} and {r}; pass --overwrite or rename with --name")
            merged[k] = v; origin[k] = r
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(merged, open(a.out, "w"), indent=2)
    print(f"wrote {a.out} with {len(merged)} baselines: {', '.join(merged)}")
    sizes = {k: len(v) for k, v in merged.items()}
    if len(set(sizes.values())) > 1:
        print(f"[warn] episode counts differ across baselines: {sizes}")


if __name__ == "__main__":
    main()
