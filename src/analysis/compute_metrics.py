#!/usr/bin/env python3
"""MemProbe behavioral metrics computation.
Usage (as library):
    from compute_metrics import compute_all_metrics, format_report
    metrics = compute_all_metrics(results, episodes)
    print(format_report(metrics))

Usage (as CLI):
    python compute_metrics.py path/to/baselines_report.json \
        --episodes path/to/episodes.jsonl

"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))  
import paths as P  
P.add_src_to_path()

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def load_episodes(path: str) -> List[Dict]:
    episodes = []
    with open(path) as f:
        for line in f:
            if line.strip():
                episodes.append(json.loads(line))
    return episodes


def build_episode_meta(episodes: List[Dict]) -> Dict[str, Dict]:
    meta = {}
    for ep in episodes:
        is_split = any(
            s.get("session_type") in ("perturbation_p1", "perturbation_p2")
            for s in ep.get("sessions", [])
        )
        ep_expected = ep.get("expected_behavior", "")
        probe_expected = {}
        for p in ep.get("probes", []):
            probe_expected[p["probe_type"]] = p.get("expected_behavior", ep_expected)
        meta[ep["episode_id"]] = {
            "expected_behavior": ep_expected,
            "is_split": is_split,
            "paradigm": ep.get("paradigm", ""),
            "condition": ep.get("condition", ""),
            "probe_expected": probe_expected,
        }
    return meta


def iter_answers(baseline_data: Dict) -> List[Tuple[str, str, str, Optional[Dict]]]:
    out = []
    for eid, ep_data in baseline_data.items():
        if isinstance(ep_data, dict) and "answers" in ep_data:
            for a in ep_data["answers"]:
                out.append((
                    a.get("probe_type", ""),
                    a.get("match", ""),
                    eid,
                    a,
                ))
        elif isinstance(ep_data, list):
            for a in ep_data:
                out.append((
                    a.get("probe_type", ""),
                    a.get("match", ""),
                    eid,
                    a,
                ))
        elif isinstance(ep_data, dict):
            out.append((
                ep_data.get("probe_type", ""),
                ep_data.get("match", ""),
                eid,
                ep_data,
            ))
    return out


def is_scorable(match: str) -> bool:
    return match in ("correct", "incorrect", "partial")


def is_correct(match: str) -> bool:
    return match == "correct"


def accuracy_over(answers: List[Tuple[str, str, str, Optional[Dict]]],
                  pred: Optional[callable] = None) -> Tuple[int, int, float]:
    correct = total = 0
    for pt, m, eid, rec in answers:
        if pred and not pred(pt, m, eid, rec):
            continue
        if is_scorable(m):
            total += 1
            if is_correct(m):
                correct += 1
    pct = correct / total if total else 0.0
    return correct, total, pct


def compute_baseline_metrics(baseline_data: Dict,
                             episode_meta: Dict[str, Dict]) -> Dict:
    answers = iter_answers(baseline_data)
    if not answers:
        return {"n_answers": 0}

    c, t, overall_acc = accuracy_over(answers)

    by_pt = {}
    seen_pts = sorted(set(pt for pt, _, _, _ in answers if pt))
    for pt in seen_pts:
        cc, tt, p = accuracy_over(answers, pred=lambda pt2, m, e, r, _pt=pt: pt2 == _pt)
        by_pt[pt] = {"correct": cc, "total": tt, "accuracy": p}

    def is_update_probe(pt, m, eid, rec):
        meta = episode_meta.get(eid, {})
        return meta.get("probe_expected", {}).get(pt) == "should_update"

    def is_preserve_probe(pt, m, eid, rec):
        meta = episode_meta.get(eid, {})
        return meta.get("probe_expected", {}).get(pt) == "should_preserve"

    cu, tu, plasticity = accuracy_over(answers, pred=is_update_probe)
    cp, tp, stability = accuracy_over(answers, pred=is_preserve_probe)
    under_update = 1.0 - plasticity if tu else 0.0
    over_update = 1.0 - stability if tp else 0.0
    sp_balance = (
        2 * plasticity * stability / (plasticity + stability)
        if (plasticity + stability) > 0
        else 0.0
    )

    hc, ht, historical_fidelity = accuracy_over(
        answers, pred=lambda pt, m, e, r: pt == "previous_value"
    )

    sc1, st1, src_probe_acc = accuracy_over(
        answers, pred=lambda pt, m, e, r: pt == "source"
    )

    import re as _re
    cs_correct = cs_total = 0
    src_sub_correct = src_sub_total = 0  
    val_sub_correct = val_sub_total = 0  
    app_sub_correct = app_sub_total = 0  
    for pt, m, eid, rec in answers:
        if pt != "conflict_value":
            continue
        subs = rec.get("conflict_sub_scores") if isinstance(rec, dict) else None
        if not subs:
            reason = rec.get("reason", "") if isinstance(rec, dict) else ""
            subs = {}
            for key in ("value", "source", "status", "applicability"):
                match = _re.search(rf"{key}=(\w+)", reason)
                if match:
                    val = match.group(1)
                    if val in ("correct", "incorrect", "partial"):
                        canon = {
                            "value": "value_identified",
                            "source": "source_identified",
                            "status": "status_classified",
                            "applicability": "target_applicability",
                        }[key]
                        subs[canon] = val
        if not subs:
            continue
        status = subs.get("status_classified")
        if status in ("correct", "incorrect", "partial"):
            cs_total += 1
            if status == "correct":
                cs_correct += 1
        src = subs.get("source_identified")
        if src in ("correct", "incorrect", "partial"):
            src_sub_total += 1
            if src == "correct":
                src_sub_correct += 1
        val = subs.get("value_identified")
        if val in ("correct", "incorrect", "partial"):
            val_sub_total += 1
            if val == "correct":
                val_sub_correct += 1
        app = subs.get("target_applicability")
        if app in ("correct", "incorrect", "partial"):
            app_sub_total += 1
            if app == "correct":
                app_sub_correct += 1
    conflict_status_acc = cs_correct / cs_total if cs_total else 0.0
    conflict_source_acc = src_sub_correct / src_sub_total if src_sub_total else 0.0
    conflict_value_sub_acc = val_sub_correct / val_sub_total if val_sub_total else 0.0
    conflict_applicability_acc = app_sub_correct / app_sub_total if app_sub_total else 0.0

    src_pool_c = sc1 + cs_correct
    src_pool_t = st1 + cs_total
    source_fidelity = src_pool_c / src_pool_t if src_pool_t else 0.0

    tc, tt2, temporal_fidelity = accuracy_over(
        answers, pred=lambda pt, m, e, r: pt == "temporal"
    )

    def is_split(pt, m, eid, rec):
        return episode_meta.get(eid, {}).get("is_split", False)

    def is_nonsplit(pt, m, eid, rec):
        return not episode_meta.get(eid, {}).get("is_split", False)

    csp, tsp, split_acc = accuracy_over(answers, pred=is_split)
    cns, tns, nonsplit_acc = accuracy_over(answers, pred=is_nonsplit)
    split_penalty = nonsplit_acc - split_acc  

    split_by_pt = {}
    nonsplit_by_pt = {}
    for pt in seen_pts:
        ccs, tts, ps = accuracy_over(
            answers, pred=lambda pt2, m, e, r, _pt=pt: pt2 == _pt and episode_meta.get(e, {}).get("is_split", False)
        )
        split_by_pt[pt] = {"correct": ccs, "total": tts, "accuracy": ps}
        ccn, ttn, pn = accuracy_over(
            answers, pred=lambda pt2, m, e, r, _pt=pt: pt2 == _pt and not episode_meta.get(e, {}).get("is_split", False)
        )
        nonsplit_by_pt[pt] = {"correct": ccn, "total": ttn, "accuracy": pn}

    return {
        "n_answers": len(answers),
        "overall_accuracy": {"correct": c, "total": t, "accuracy": overall_acc},
        "per_probe_type": by_pt,
        "plasticity": {"correct": cu, "total": tu, "accuracy": plasticity},
        "stability": {"correct": cp, "total": tp, "accuracy": stability},
        "under_update": under_update,
        "over_update": over_update,
        "sp_balance": sp_balance,
        "historical_fidelity": {"correct": hc, "total": ht, "accuracy": historical_fidelity},
        "source_fidelity": {
            "correct": src_pool_c, "total": src_pool_t, "accuracy": source_fidelity,
            "source_probe": {"correct": sc1, "total": st1, "accuracy": src_probe_acc},
            "conflict_status": {"correct": cs_correct, "total": cs_total, "accuracy": conflict_status_acc},
            "conflict_source_sub": {"correct": src_sub_correct, "total": src_sub_total, "accuracy": conflict_source_acc},
            "conflict_value_sub": {"correct": val_sub_correct, "total": val_sub_total, "accuracy": conflict_value_sub_acc},
            "conflict_applicability_sub": {"correct": app_sub_correct, "total": app_sub_total, "accuracy": conflict_applicability_acc},
        },
        "temporal_fidelity": {"correct": tc, "total": tt2, "accuracy": temporal_fidelity},
        "non_split": {"correct": cns, "total": tns, "accuracy": nonsplit_acc},
        "split": {"correct": csp, "total": tsp, "accuracy": split_acc},
        "split_penalty": split_penalty,
        "split_per_probe": split_by_pt,
        "non_split_per_probe": nonsplit_by_pt,
        "split_current_value_accuracy": split_by_pt.get("current_value", {}).get("accuracy", 0.0),
        "split_change_detection_accuracy": split_by_pt.get("change_detection", {}).get("accuracy", 0.0),
    }


def compute_retrieval_metrics(metrics_fc: Dict, metrics_rag: Dict) -> Dict:
    acc_fc = metrics_fc["overall_accuracy"]["accuracy"]
    acc_rag = metrics_rag["overall_accuracy"]["accuracy"]
    return {
        "fc_rag_gap": acc_fc - acc_rag,
        "rag_norm": acc_rag / acc_fc if acc_fc > 0 else 0.0,
        "acc_fc": acc_fc,
        "acc_rag": acc_rag,
    }


def compute_all_metrics(report: Dict, episodes: List[Dict]) -> Dict:
    episode_meta = build_episode_meta(episodes)
    metrics_per_baseline = {}
    baseline_keys = [k for k in report.keys()
                     if k not in ("episode_metadata", "stored_memories", "meta")]
    for bl in baseline_keys:
        data = report[bl]
        if not isinstance(data, dict):
            continue
        metrics_per_baseline[bl] = compute_baseline_metrics(data, episode_meta)

    out = {"per_baseline": metrics_per_baseline}

    if "full_context" in metrics_per_baseline and "naive_rag" in metrics_per_baseline:
        out["retrieval_comparison"] = compute_retrieval_metrics(
            metrics_per_baseline["full_context"],
            metrics_per_baseline["naive_rag"],
        )

    if "mem0_full" in metrics_per_baseline and "full_context" in metrics_per_baseline:
        out["mem0_vs_fc"] = compute_retrieval_metrics(
            metrics_per_baseline["full_context"],
            metrics_per_baseline["mem0_full"],
        )
        out["mem0_vs_fc"]["gap"] = out["mem0_vs_fc"].pop("fc_rag_gap")
        out["mem0_vs_fc"]["mem0_norm"] = out["mem0_vs_fc"].pop("rag_norm")
        out["mem0_vs_fc"]["acc_mem0"] = out["mem0_vs_fc"].pop("acc_rag")

    return out


def _pct(d: Dict, key: str = "accuracy") -> str:
    if isinstance(d, dict):
        c = d.get("correct", 0)
        t = d.get("total", 0)
        a = d.get(key, 0.0)
        return f"{c:>3}/{t:<3} ({a*100:5.1f}%)"
    return f"{d:.3f}"


def format_baseline_report(name: str, m: Dict) -> str:
    if not m or m.get("n_answers", 0) == 0:
        return f"\n{name}: NO DATA\n"

    L = []
    L.append(f"\n{'=' * 80}")
    L.append(f"BASELINE: {name}  (n_answers={m['n_answers']})")
    L.append("=" * 80)
    L.append(f"  Overall accuracy:      {_pct(m['overall_accuracy'])}")

    L.append(f"\n  -- Stability/Plasticity --")
    L.append(f"  Plasticity (should_update):   {_pct(m['plasticity'])}")
    L.append(f"  Stability  (should_preserve): {_pct(m['stability'])}")
    L.append(f"  UnderUpdate (1-Plast):        {m['under_update']*100:.1f}%")
    L.append(f"  OverUpdate  (1-Stab):         {m['over_update']*100:.1f}%")
    L.append(f"  SP-Balance (harmonic mean):   {m['sp_balance']*100:.1f}%")

    L.append(f"\n  -- Fidelity --")
    L.append(f"  Historical (previous_value):  {_pct(m['historical_fidelity'])}")
    L.append(f"  Source     (source + conflict_status):")
    L.append(f"      pooled:                    {_pct(m['source_fidelity'])}")
    L.append(f"      source probe only:         {_pct(m['source_fidelity']['source_probe'])}")
    L.append(f"      conflict-status only:      {_pct(m['source_fidelity']['conflict_status'])}")
    L.append(f"  Temporal:                     {_pct(m['temporal_fidelity'])}")

    L.append(f"\n  -- Per probe type --")
    for pt in sorted(m["per_probe_type"].keys()):
        L.append(f"    {pt:<18} {_pct(m['per_probe_type'][pt])}")

    L.append(f"\n  -- Split vs Non-Split --")
    L.append(f"  Non-split: {_pct(m['non_split'])}")
    L.append(f"  Split:     {_pct(m['split'])}")
    L.append(f"  Split penalty (Δ):           {m['split_penalty']*100:+.1f}pp")
    L.append(f"  Split current_value acc:     {m['split_current_value_accuracy']*100:.1f}%")
    L.append(f"  Split change_detection acc:  {m['split_change_detection_accuracy']*100:.1f}%")
    L.append(f"  Split breakdown by probe:")
    for pt in sorted(m["split_per_probe"].keys()):
        sp = m["split_per_probe"][pt]
        ns = m["non_split_per_probe"][pt]
        if sp["total"] == 0 and ns["total"] == 0:
            continue
        L.append(f"    {pt:<18}  non-split {_pct(ns)}   split {_pct(sp)}")

    return "\n".join(L)


def format_retrieval_comparison(name_pair: str, comp: Dict) -> str:
    L = [f"\n{'=' * 80}", f"RETRIEVAL COMPARISON: {name_pair}", "=" * 80]
    if "fc_rag_gap" in comp:
        L.append(f"  Acc(FC):     {comp['acc_fc']*100:.1f}%")
        L.append(f"  Acc(RAG):    {comp['acc_rag']*100:.1f}%")
        L.append(f"  FC-RAG gap:  {comp['fc_rag_gap']*100:+.1f}pp")
        L.append(f"  RAG_norm:    {comp['rag_norm']*100:.1f}%")
    else:
        L.append(f"  Acc(FC):       {comp['acc_fc']*100:.1f}%")
        L.append(f"  Acc(Mem0):     {comp['acc_mem0']*100:.1f}%")
        L.append(f"  FC-Mem0 gap:   {comp['gap']*100:+.1f}pp")
        L.append(f"  Mem0_norm:     {comp['mem0_norm']*100:.1f}%")
    return "\n".join(L)


def format_report(metrics: Dict, model_label: str = "") -> str:
    L = []
    if model_label:
        L.append(f"\n{'#' * 80}")
        L.append(f"# {model_label}")
        L.append("#" * 80)
    for bl_name, m in metrics["per_baseline"].items():
        L.append(format_baseline_report(bl_name, m))
    if "retrieval_comparison" in metrics:
        L.append(format_retrieval_comparison("Full-Context vs Naive RAG",
                                             metrics["retrieval_comparison"]))
    if "mem0_vs_fc" in metrics:
        L.append(format_retrieval_comparison("Full-Context vs Mem0",
                                             metrics["mem0_vs_fc"]))
    return "\n".join(L)


def format_cross_model_table(all_metrics: Dict[str, Dict],
                              baseline: str = "full_context") -> str:
    L = []
    L.append(f"\n{'#' * 80}")
    L.append(f"# CROSS-MODEL COMPARISON — baseline = {baseline}")
    L.append("#" * 80)

    rows = []
    for label, metrics in all_metrics.items():
        m = metrics.get("per_baseline", {}).get(baseline)
        if not m:
            continue
        rows.append((label, m))

    if not rows:
        return "\n  No data for baseline=" + baseline

    def col(width, s):
        return f"{s:>{width}}"

    headers = ["Metric"] + [r[0] for r in rows]
    widths = [28] + [max(14, len(r[0]) + 2) for r in rows]

    def emit_header():
        L.append(" ".join(col(w, h) for w, h in zip(widths, headers)))
        L.append("-" * sum(widths))

    def emit_row(label, vals):
        L.append(" ".join([col(widths[0], label)] +
                          [col(widths[i + 1], v) for i, v in enumerate(vals)]))

    emit_header()
    fmt_acc = lambda m, key="overall_accuracy": (
        f"{m[key]['accuracy']*100:.1f}%" if isinstance(m[key], dict) and m[key]["total"] > 0 else "N/A"
    )
    emit_row("Overall acc",       [fmt_acc(m) for _, m in rows])
    emit_row("Plasticity",        [f"{m['plasticity']['accuracy']*100:.1f}%" for _, m in rows])
    emit_row("Stability",         [f"{m['stability']['accuracy']*100:.1f}%" for _, m in rows])
    emit_row("UnderUpdate",       [f"{m['under_update']*100:.1f}%" for _, m in rows])
    emit_row("OverUpdate",        [f"{m['over_update']*100:.1f}%" for _, m in rows])
    emit_row("SP-Balance",        [f"{m['sp_balance']*100:.1f}%" for _, m in rows])
    emit_row("Historical fidelity", [fmt_acc(m, "historical_fidelity") for _, m in rows])
    emit_row("Source fidelity",   [fmt_acc(m, "source_fidelity") for _, m in rows])
    emit_row("  source probe",    [f"{m['source_fidelity']['source_probe']['accuracy']*100:.1f}%"
                                    if m['source_fidelity']['source_probe']['total'] > 0 else "N/A"
                                    for _, m in rows])
    emit_row("  conflict-status", [f"{m['source_fidelity']['conflict_status']['accuracy']*100:.1f}%"
                                    if m['source_fidelity']['conflict_status']['total'] > 0 else "N/A"
                                    for _, m in rows])
    emit_row("Temporal fidelity", [fmt_acc(m, "temporal_fidelity") for _, m in rows])
    emit_row("Non-split acc",     [f"{m['non_split']['accuracy']*100:.1f}%" for _, m in rows])
    emit_row("Split acc",         [f"{m['split']['accuracy']*100:.1f}%" for _, m in rows])
    emit_row("Split penalty",     [f"{m['split_penalty']*100:+.1f}pp" for _, m in rows])
    emit_row("Split CV acc",      [f"{m['split_current_value_accuracy']*100:.1f}%" for _, m in rows])
    emit_row("Split CD acc",      [f"{m['split_change_detection_accuracy']*100:.1f}%" for _, m in rows])

    return "\n".join(L)


def main():
    parser = argparse.ArgumentParser(description="Compute MemProbe behavioral metrics")
    parser.add_argument("reports", nargs="+",
                        help="One or more baseline-report JSON files")
    parser.add_argument("--episodes",
                        default=str(P.EPISODES56),
                        help="Path to episodes JSONL")
    parser.add_argument("--label", action="append", default=None,
                        help="Label for each report (defaults to filename). Pass once per report.")
    parser.add_argument("--baseline-compare", default=None,
                        help="Show cross-model comparison for this baseline (e.g. 'full_context', 'mem0_full')")
    parser.add_argument("--out-json", default=None,
                        help="Save computed metrics to JSON file")
    args = parser.parse_args()

    episodes = load_episodes(args.episodes)
    labels = args.label or [Path(r).stem for r in args.reports]
    if len(labels) != len(args.reports):
        labels = [Path(r).stem for r in args.reports]

    all_metrics = {}
    for label, report_path in zip(labels, args.reports):
        with open(report_path) as f:
            report = json.load(f)
        metrics = compute_all_metrics(report, episodes)
        all_metrics[label] = metrics
        print(format_report(metrics, model_label=label))

    if args.baseline_compare:
        print(format_cross_model_table(all_metrics, baseline=args.baseline_compare))

    if args.out_json:
        with open(args.out_json, "w") as f:
            json.dump(all_metrics, f, indent=2)
        print(f"\nSaved metrics to {args.out_json}")


if __name__ == "__main__":
    main()
