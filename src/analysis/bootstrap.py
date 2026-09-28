#!/usr/bin/env python3
"""
Common options: --report (default ALL_gemini), --episodes, --iters (2000), --seed (42), --out (JSON).
Outputs are JSON only; the shipped results are in results/suite56/analysis/.
"""
from __future__ import annotations
import argparse, json, math, random, sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))  
import paths as P  
P.add_src_to_path()
from compute_metrics import build_episode_meta, compute_baseline_metrics, load_episodes  

METRICS: List[Tuple[str, str, Any]] = [
    ("overall",             "Overall accuracy",    lambda m: m["overall_accuracy"]["accuracy"]),
    ("plasticity",          "Plasticity",          lambda m: m["plasticity"]["accuracy"]),
    ("stability",           "Stability",           lambda m: m["stability"]["accuracy"]),
    ("sp_balance",          "SP-Balance",          lambda m: m["sp_balance"]),
    ("historical_fidelity", "Historical fidelity", lambda m: m["historical_fidelity"]["accuracy"]),
    ("source_fidelity",     "Source fidelity",     lambda m: m["source_fidelity"]["accuracy"]),
    ("temporal_fidelity",   "Temporal fidelity",   lambda m: m["temporal_fidelity"]["accuracy"]),
    ("non_split_accuracy",  "Non-split accuracy",  lambda m: m["non_split"]["accuracy"]),
    ("split_accuracy",      "Split accuracy",      lambda m: m["split"]["accuracy"]),
    ("split_penalty",       "Split penalty (Δ)",   lambda m: m["split_penalty"]),
]
PROBES = ["current_value", "previous_value", "change_detection", "source", "conflict_value", "temporal"]
MEMORY_SYSTEMS = ["amem_full", "cognee_full", "langmem_full", "graphiti_full", "memoryos_full", "mem0_full"]


def normalize_baseline(data: Dict) -> Dict[str, Dict[str, Any]]:
    out = {}
    for eid, ev in data.items():
        if isinstance(ev, list):
            out[eid] = {"answers": ev}
        elif isinstance(ev, dict) and "answers" in ev:
            out[eid] = ev
    return out


def quantile(sv: List[float], q: float) -> float:
    n = len(sv)
    if n == 0: return float("nan")
    if n == 1: return sv[0]
    pos = q * (n - 1); lo = math.floor(pos); hi = math.ceil(pos)
    return sv[lo] if lo == hi else sv[lo] + (sv[hi] - sv[lo]) * (pos - lo)


def summarize(vals: List[float], point: float) -> Dict[str, Any]:
    v = [x for x in vals if not (isinstance(x, float) and math.isnan(x))]
    n = len(v)
    if n == 0:
        return {"point": point, "mean": float("nan"), "se": float("nan"), "ci_low": float("nan"),
                "ci_high": float("nan"), "p_two_sided": float("nan"), "significant_5pct": False,
                "prob_gt_0": float("nan"), "n_iter": 0}
    mean = sum(v) / n; se = math.sqrt(sum((x - mean) ** 2 for x in v) / max(1, n - 1))
    sv = sorted(v); lo, hi = quantile(sv, 0.025), quantile(sv, 0.975)
    n_pos = sum(1 for x in v if x > 0); n_neg = sum(1 for x in v if x < 0); n_zero = n - n_pos - n_neg
    tail_pos = (n_pos + 0.5 * n_zero) / n; tail_neg = (n_neg + 0.5 * n_zero) / n
    p = min(1.0, max(0.0, 2 * min(tail_pos, tail_neg)))
    return {"point": float(point), "mean": float(mean), "se": float(se), "ci_low": float(lo), "ci_high": float(hi),
            "p_two_sided": float(p), "significant_5pct": bool(lo > 0 or hi < 0), "prob_gt_0": float(tail_pos), "n_iter": n}


def resample(eids: List[str], rng: random.Random) -> List[Tuple[str, str]]:
    N = len(eids)
    return [(f"{eids[i]}#{k}", eids[i]) for k, i in enumerate(rng.randrange(N) for _ in range(N))]


def metrics_on(norm: Dict, meta: Dict, sample: List[Tuple[str, str]]) -> Dict[str, float]:
    m = compute_baseline_metrics({sid: norm[eid] for sid, eid in sample}, {sid: meta[eid] for sid, eid in sample})
    return {k: float(g(m)) for k, _, g in METRICS}


def cfg(args):
    out = {}
    for k, v in vars(args).items():
        if k == "fn": continue
        if isinstance(v, str) and Path(v).is_absolute():
            try: v = str(Path(v).resolve().relative_to(P.ROOT))
            except ValueError: pass
        out[k] = v
    return out


def load(args):
    R = json.loads(Path(args.report).read_text())
    episodes = load_episodes(args.episodes); meta = build_episode_meta(episodes)
    return R, meta, [e["episode_id"] for e in episodes]


def parse_pairs(s: str) -> List[Tuple[str, str]]:
    return [tuple(x.strip() for x in tok.split(":")) for tok in s.split(",") if tok.strip()]


def cmd_overall(args):
    R, meta, all_eids = load(args)
    rng_master = random.Random(args.seed)
    out = {"config": cfg(args) | {"method": "episode-level bootstrap, percentile CI"}, "per_baseline": {}}
    for bname, data in R.items():
        if not isinstance(data, dict): continue
        norm = normalize_baseline(data); eids = [e for e in all_eids if e in norm]
        if not eids: continue
        point = metrics_on(norm, meta, [(e, e) for e in eids])
        rng = random.Random(rng_master.randrange(2 ** 32))
        vals = {k: [] for k, _, _ in METRICS}
        for _ in range(args.iters):
            it = metrics_on(norm, meta, resample(eids, rng))
            for k in vals: vals[k].append(it[k])
        out["per_baseline"][bname] = {k: summarize(vals[k], point[k]) for k in vals}
        o = out["per_baseline"][bname]["overall"]
        print(f"  {bname:18s} overall {o['point']*100:5.1f}%  CI [{o['ci_low']*100:5.1f}, {o['ci_high']*100:5.1f}]  SE {o['se']*100:.2f}pp", flush=True)
    Path(args.out).write_text(json.dumps(out, indent=2)); print(f"[bootstrap overall] wrote {args.out}")


def cmd_paired(args):
    R, meta, all_eids = load(args)
    pairs = parse_pairs(args.only_pairs) if args.only_pairs else \
        [(m, "full_context") for m in MEMORY_SYSTEMS] + list(combinations(MEMORY_SYSTEMS, 2)) + parse_pairs(args.extra_pairs)
    needed = sorted({b for p in pairs for b in p})
    missing = [b for b in needed if b not in R]
    if missing: sys.exit(f"baselines missing from report: {missing}")
    norm = {b: normalize_baseline(R[b]) for b in needed}
    eids = [e for e in all_eids if all(e in norm[b] for b in needed)]
    point = {b: metrics_on(norm[b], meta, [(e, e) for e in eids]) for b in needed}
    rng = random.Random(args.seed)
    diffs = {pr: {k: [] for k, _, _ in METRICS} for pr in pairs}
    for _ in range(args.iters):
        sample = resample(eids, rng)
        it = {b: metrics_on(norm[b], meta, sample) for b in needed}
        for A, B in pairs:
            for k in diffs[(A, B)]: diffs[(A, B)][k].append(it[A][k] - it[B][k])
    out = {"config": cfg(args) | {"n_episodes": len(eids), "method": "paired episode-level bootstrap; two-sided p = 2·min(P(Δ≤0), P(Δ≥0))"}, "pairs": []}
    print(f"{'A vs B':42s} {'Δ overall (pp)':>16s} {'95% CI':>18s} {'p':>7s}")
    for A, B in pairs:
        per = {k: summarize(diffs[(A, B)][k], point[A][k] - point[B][k]) for k, _, _ in METRICS}
        out["pairs"].append({"A": A, "B": B, "metrics": per}); s = per["overall"]
        pv = "<0.001" if s["p_two_sided"] < 0.001 else f"{s['p_two_sided']:.3f}"
        print(f"{A + ' vs ' + B:42s} {s['point']*100:+15.1f}  [{s['ci_low']*100:+6.1f}, {s['ci_high']*100:+6.1f}] {pv:>7s} {'★' if s['significant_5pct'] else ''}")
    Path(args.out).write_text(json.dumps(out, indent=2)); print(f"[bootstrap paired] wrote {args.out}")


def cmd_probe(args):
    R, meta, all_eids = load(args)
    def by_probe(data):
        out = {}
        for eid, ev in normalize_baseline(data).items():
            out[eid] = [(a.get("probe_type", ""), a.get("match", "")) for a in ev["answers"]]
        return out
    per_sys = {s: by_probe(R[s]) for s in args.systems}
    eids = sorted(e for e in all_eids if all(e in per_sys[s] for s in args.systems))
    def acc(d, sample):
        c, t = defaultdict(int), defaultdict(int)
        for _, eid in sample:
            for pt, m in d.get(eid, []):
                if m in ("correct", "incorrect", "partial"):
                    t[pt] += 1; c[pt] += (m == "correct")
        return {p: (100 * c[p] / t[p] if t[p] else float("nan")) for p in PROBES}
    ident = [(e, e) for e in eids]
    point = {s: acc(per_sys[s], ident) for s in args.systems}
    pairs = list(combinations(args.systems, 2)); rng = random.Random(args.seed)
    diffs = {pr: {p: [] for p in PROBES} for pr in pairs}
    for _ in range(args.iters):
        sample = resample(eids, rng); it = {s: acc(per_sys[s], sample) for s in args.systems}
        for A, B in pairs:
            for p in PROBES: diffs[(A, B)][p].append(it[A][p] - it[B][p])
    n_tests = len(pairs) * len(PROBES)
    out = {"config": cfg(args) | {"n_episodes": len(eids), "bonferroni_alpha": 0.05 / n_tests, "n_tests": n_tests}, "point": point, "results": {}}
    print(f"{'pair':36s} {'probe':18s} {'A':>6s} {'B':>6s} {'Δ(pp)':>8s} {'95% CI':>16s} {'p':>7s}  (Bonferroni α={0.05/n_tests:.4f})")
    for A, B in pairs:
        out["results"][f"{A}_vs_{B}"] = {}
        for p in PROBES:
            s = summarize(diffs[(A, B)][p], point[A][p] - point[B][p]); out["results"][f"{A}_vs_{B}"][p] = s
            pv = "<0.001" if s["p_two_sided"] < 0.001 else f"{s['p_two_sided']:.3f}"
            flag = "★★" if s["p_two_sided"] < 0.05 / n_tests else ("★" if s["significant_5pct"] else "")
            print(f"{A + ' vs ' + B:36s} {p:18s} {point[A][p]:6.1f} {point[B][p]:6.1f} {s['point']:+8.1f} [{s['ci_low']:+6.1f}, {s['ci_high']:+6.1f}] {pv:>7s} {flag}")
    Path(args.out).write_text(json.dumps(out, indent=2)); print(f"[bootstrap probe] wrote {args.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    def common(p, out_name):
        p.add_argument("--report", default=str(P.REPORTS56 / "baselines_report_ALL_gemini.json"))
        p.add_argument("--episodes", default=str(P.EPISODES56))
        p.add_argument("--iters", type=int, default=2000); p.add_argument("--seed", type=int, default=42)
        p.add_argument("--out", default=str(P.ANALYSIS56 / out_name))
    p = sub.add_parser("overall"); common(p, "bootstrap_ci.json"); p.set_defaults(fn=cmd_overall)
    p = sub.add_parser("paired"); common(p, "paired_bootstrap_ci.json")
    p.add_argument("--only-pairs", default="", help="'A:B,C:D' — use only these pairs")
    p.add_argument("--extra-pairs", default="", help="'A:B,...' added to the default 21 pairs"); p.set_defaults(fn=cmd_paired)
    p = sub.add_parser("probe"); common(p, "pairwise_probe_bootstrap.json")
    p.add_argument("--systems", nargs="+", default=["graphiti_full", "langmem_full", "memoryos_full"]); p.set_defaults(fn=cmd_probe)
    args = ap.parse_args(); args.fn(args)


if __name__ == "__main__":
    main()
