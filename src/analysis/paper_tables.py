"""
regenerate every numeric table of the paper from the raw reports.

Inputs (resolved through src/paths.py):
  episodes.jsonl, baselines_report_ALL_gemini.json           Tables 1,2,3,5,7,10, T4 Gemini column, T14/15 Gemini column
  bootstrap_ci.json (output of `bootstrap.py overall`, 2000 iters, seed 42)   Table 1 confidence intervals
  baselines_report_<sys>_qwen3.json                                     Table 4 Qwen3 column
  source_error_classification_final_56.json                             Table 6 (manual audit)
  baselines_report_merged_56.json (GPT-5.4 direct reader, scorer v1)    Tables 11,12,13
  baselines_report_gpt54_v2.json, baselines_report_qwen3_v2.json        Tables 14,15
  data/suite40/episodes.jsonl, results/suite40/reports/baselines_report_<sys>_gpt.json   Table 16

Usage:  python src/analysis/paper_tables.py [--out /tmp/paper_tables.md] [--iters 2000] [--seed 42]
"""
import argparse, json, sys, random
from pathlib import Path
from statistics import mean

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import paths as P  # noqa: E402
P.add_src_to_path()
from compute_metrics import (load_episodes, build_episode_meta, iter_answers,   
                             accuracy_over, compute_baseline_metrics, is_scorable, is_correct)
try:
    from scipy.stats import pearsonr, spearmanr, kendalltau
except ImportError:                                                          
    pearsonr = spearmanr = kendalltau = None

SYS = [("mem0_full", "Mem0"), ("graphiti_full", "Graphiti"), ("langmem_full", "LangMem"),
       ("cognee_full", "Cognee"), ("amem_full", "A-MEM"), ("memoryos_full", "MemoryOS")]
REFS = [("oracle_rag", "Oracle RAG (diag.)"), ("full_context", "Full-context")]
RAGS = [("naive_rag", "Naive RAG"), ("time_aware_rag", "Time-aware RAG")]
PARADIGMS = ["interference", "misinformation", "consolidation", "reconsolidation"]
PROBES = ["current_value", "previous_value", "change_detection", "source", "conflict_value", "temporal"]
PROBE_LABEL = {"current_value": "Current value", "previous_value": "Previous value",
               "change_detection": "Change detection", "source": "Source",
               "conflict_value": "Conflict value", "temporal": "Temporal"}

def pct(x): return f"{100*x:.1f}"
def md(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)

def paradigm_acc(data, meta):
    ans = iter_answers(data)
    return {p: accuracy_over(ans, lambda pt, m, eid, rec, p=p: meta[eid]["paradigm"] == p)[2] for p in PARADIGMS}

def episode_bootstrap_ci(data, iters, seed):
    per_ep = {}
    for pt, m, eid, rec in iter_answers(data):
        if is_scorable(m):
            c, t = per_ep.get(eid, (0, 0)); per_ep[eid] = (c + is_correct(m), t + 1)
    eps = list(per_ep); rng = random.Random(seed); accs = []
    for _ in range(iters):
        s = [per_ep[rng.choice(eps)] for _ in eps]
        accs.append(sum(c for c, _ in s) / sum(t for _, t in s))
    accs.sort()
    return accs[int(0.025 * iters)], accs[int(0.975 * iters) - 1]

def offdiag(matrix_cols):
    pr, sp = [], []
    for i in range(len(matrix_cols)):
        for j in range(i + 1, len(matrix_cols)):
            pr.append(pearsonr(matrix_cols[i], matrix_cols[j])[0]); sp.append(spearmanr(matrix_cols[i], matrix_cols[j])[0])
    return mean(pr), min(pr), mean(sp), min(sp)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None); ap.add_argument("--iters", type=int, default=2000); ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(); L = []

    eps56 = load_episodes(str(P.EPISODES56)); meta56 = build_episode_meta(eps56)
    R = json.load(open(P.REPORTS56 / "baselines_report_ALL_gemini.json"))
    M = {k: compute_baseline_metrics(v, meta56) for k, v in R.items() if isinstance(v, dict)}

    L.append("## Table 1 — Overall accuracy [95% CI] (56 suite, Gemini-3-Flash reader)\n")
    bs_path = P.ANALYSIS56 / "bootstrap_ci.json"
    BS = json.load(open(bs_path))["per_baseline"] if bs_path.exists() else None
    cells = []
    for k, n in REFS + SYS + RAGS:
        acc = M[k]["overall_accuracy"]["accuracy"]
        if BS and k in BS: lo, hi = BS[k]["overall"]["ci_low"], BS[k]["overall"]["ci_high"]
        else: lo, hi = episode_bootstrap_ci(R[k], a.iters, a.seed)
        cells.append((n, f"{pct(acc)} [{pct(lo)}, {pct(hi)}]"))
    L.append(md(["Metric"] + [n for n, _ in cells], [["Overall [95% CI]"] + [c for _, c in cells]]))
    L.append("\n(CI source: " + ("bootstrap_ci.json, 2000 iters, seed 42" if BS else f"in-process bootstrap, {a.iters} iters, seed {a.seed}") + ")")
    L.append("\n### Table 1 (extended) — all headline metrics\n")
    rows = []
    for k, n in REFS + SYS + RAGS:
        m = M[k]
        rows.append([n, pct(m["overall_accuracy"]["accuracy"]), pct(m["plasticity"]["accuracy"]), pct(m["stability"]["accuracy"]),
                     pct(m["sp_balance"]), pct(m["historical_fidelity"]["accuracy"]), pct(m["source_fidelity"]["accuracy"]),
                     pct(m["temporal_fidelity"]["accuracy"]), pct(m["non_split"]["accuracy"]), pct(m["split"]["accuracy"]),
                     f"{100*m['split_penalty']:+.1f}"])
    L.append(md(["System", "Overall", "Plast.", "Stab.", "SP-Bal", "Hist.", "Source", "Temp.", "Non-split", "Split", "Δsplit"], rows))

    L.append("\n## Table 2 — Stability–plasticity metrics\n")
    rows = [[n, pct(M[k]["plasticity"]["accuracy"]), pct(M[k]["stability"]["accuracy"]), pct(M[k]["sp_balance"]),
             pct(M[k]["over_update"]), pct(M[k]["under_update"])] for k, n in SYS]
    L.append(md(["System", "Plast.", "Stab.", "SP-Bal", "PreserveErr.", "UpdateErr."], rows))

    L.append("\n## Table 3 — Paradigm-wise accuracy\n")
    rows = []
    for k, n in REFS + SYS + RAGS:
        pa = paradigm_acc(R[k], meta56)
        rows.append([n] + [pct(pa[p]) for p in PARADIGMS] + [pct(M[k]["overall_accuracy"]["accuracy"])])
    L.append(md(["System"] + [p.capitalize() for p in PARADIGMS] + ["Overall"], rows))

    L.append("\n## Table 4 — Reader ablation (Gemini-3-Flash direct run vs Qwen3-32B)\n")
    ge, qw, rows = [], [], []
    for k, n in sorted(SYS, key=lambda kn: -M[kn[0]]["overall_accuracy"]["accuracy"]):
        q = json.load(open(P.REPORTS56 / f"baselines_report_{k.replace('_full','')}_qwen3.json"))[k]
        g_acc = M[k]["overall_accuracy"]["accuracy"]; q_acc = compute_baseline_metrics(q, meta56)["overall_accuracy"]["accuracy"]
        ge.append(g_acc); qw.append(q_acc); rows.append([n, pct(g_acc), pct(q_acc)])
    L.append(md(["System", "Gemini", "Qwen3"], rows))
    if spearmanr: L.append(f"\nSpearman ρ = {spearmanr(ge, qw)[0]:.2f}, Kendall τ = {kendalltau(ge, qw)[0]:.2f}")

    L.append("\n## Table 5 — Historical / source / temporal fidelity\n")
    rows = [[n, pct(M[k]["historical_fidelity"]["accuracy"]), pct(M[k]["source_fidelity"]["accuracy"]),
             pct(M[k]["temporal_fidelity"]["accuracy"])] for k, n in REFS + SYS + RAGS]
    L.append(md(["System", "Hist.", "Source", "Temp."], rows))

    L.append("\n## Table 6 — Manual classification of source-probe errors (source_error_classification_final_56.json)\n")
    C = json.load(open(P.ANALYSIS56 / "source_error_classification_final_56.json"))["source_errors_by_system"]
    rows = [[n, C[s]["B"], C[s]["A"] + C[s]["A_prime"]] for s, n in
            [("amem", "A-MEM"), ("cognee", "Cognee"), ("langmem", "LangMem"), ("graphiti", "Graphiti"), ("memoryos", "MemoryOS"), ("mem0", "Mem0")]]
    L.append(md(["System", "Read-out (B)", "Storage-side (A + A′)"], rows))

    L.append("\n## Table 7 — Diagnostic RAG ablation\n")
    fc = M["full_context"]["overall_accuracy"]["accuracy"]; cols = ["naive_rag", "time_aware_rag", "oracle_rag", "full_context"]
    def row(label, f): return [label] + [f(M[c], c) for c in cols]
    rows = [row("Δ_FC (pp)", lambda m, c: "--" if c == "full_context" else f"{100*(fc-m['overall_accuracy']['accuracy']):.1f}"),
            row("RAG_norm", lambda m, c: "--" if c == "full_context" else f"{m['overall_accuracy']['accuracy']/fc:.3f}"),
            row("Non-split", lambda m, c: pct(m["non_split"]["accuracy"])), row("Split", lambda m, c: pct(m["split"]["accuracy"])),
            row("Split CV", lambda m, c: pct(m["split_current_value_accuracy"])), row("Split CD", lambda m, c: pct(m["split_change_detection_accuracy"]))]
    L.append(md(["Metric", "Naive RAG", "Time-aware RAG", "Oracle RAG", "Full-context"], rows))

    L.append("\n## Table 10 — Off-diagonal correlation summary (6 memory systems)\n")
    if pearsonr:
        par_cols = [[paradigm_acc(R[k], meta56)[p] for k, _ in SYS] for p in PARADIGMS]
        pr_cols = [[M[k]["per_probe_type"].get(pt, {}).get("accuracy", 0.0) for k, _ in SYS] for pt in PROBES]
        rows = []
        for label, cols_ in [("4 paradigms", par_cols), ("6 probe types", pr_cols)]:
            pm, pmin, sm, smin = offdiag(cols_); rows.append([label, f"{pm:.2f}", f"{pmin:.2f}", f"{sm:.2f}", f"{smin:.2f}"])
        L.append(md(["Axis", "Pearson mean", "Pearson min", "Spearman mean", "Spearman min"], rows))

    V = json.load(open(P.REPORTS56 / "baselines_report_merged_56.json"))
    MV = {k: compute_baseline_metrics(v, meta56) for k, v in V.items() if isinstance(v, dict)}
    L.append("\n## Table 11 — Probe-level validation (GPT-5.4 reader, baselines_report_merged_56.json)\n")
    rows = [[PROBE_LABEL[pt]] + [pct(MV[b]["per_probe_type"].get(pt, {}).get("accuracy", 0.0)) for b in ("judge", "full_context", "naive_rag")] for pt in PROBES]
    L.append(md(["Probe type", "Judge", "Full-context", "Naive RAG"], rows))
    L.append("\n## Table 12 — Suite validation\n")
    rows = [[n, pct(MV[b]["overall_accuracy"]["accuracy"])] for b, n in
            [("judge", "LLM judge"), ("full_context", "Full-context reader"), ("naive_rag", "Naive RAG"), ("latest_value", "Latest-value heuristic")]]
    rows.append(["FC–RAG gap (pp)", f"{100*(MV['full_context']['overall_accuracy']['accuracy']-MV['naive_rag']['overall_accuracy']['accuracy']):.1f}"])
    L.append(md(["Baseline", "Accuracy"], rows))
    L.append("\n## Table 13 — Split vs non-split validation\n")
    rows = [["Split episodes"] + [pct(MV[b]["split"]["accuracy"]) for b in ("judge", "full_context", "naive_rag")],
            ["Non-split episodes"] + [pct(MV[b]["non_split"]["accuracy"]) for b in ("judge", "full_context", "naive_rag")]]
    L.append(md(["Subset", "Judge", "Full-context", "Naive RAG"], rows))

    X = {"GPT-5.4": json.load(open(P.REPORTS56 / "baselines_report_gpt54_v2.json")), "Gemini-3-Flash": R,
         "Qwen3-32B": json.load(open(P.REPORTS56 / "baselines_report_qwen3_v2.json"))}
    MX = {name: {k: compute_baseline_metrics(v, meta56) for k, v in rep.items() if k in ("judge", "full_context", "naive_rag")} for name, rep in X.items()}
    L.append("\n## Table 14 — Cross-model validation summary\n")
    rows = [[n] + [pct(MX[r][b]["overall_accuracy"]["accuracy"]) for r in X] for b, n in [("judge", "Judge"), ("full_context", "Full-context"), ("naive_rag", "Naive RAG")]]
    rows.append(["FC–RAG gap (pp)"] + [f"{100*(MX[r]['full_context']['overall_accuracy']['accuracy']-MX[r]['naive_rag']['overall_accuracy']['accuracy']):.1f}" for r in X])
    L.append(md(["Baseline"] + list(X), rows))
    L.append("\n## Table 15 — Full-context accuracy by probe type across readers\n")
    rows = [[PROBE_LABEL[pt]] + [pct(MX[r]["full_context"]["per_probe_type"].get(pt, {}).get("accuracy", 0.0)) for r in X] for pt in PROBES]
    rows.append(["Overall"] + [pct(MX[r]["full_context"]["overall_accuracy"]["accuracy"]) for r in X])
    L.append(md(["Probe type"] + list(X), rows))

    L.append(f"\n## Table 16 — Second suite (gen40), GPT-5.6 reader; episode bootstrap CI ({a.iters} iters, seed {a.seed})\n")
    eps40 = load_episodes(str(P.EPISODES40)); meta40 = build_episode_meta(eps40)
    rows = []
    for k, n in SYS:
        d = json.load(open(P.REPORTS40 / f"baselines_report_{k.replace('_full','')}_gpt.json"))[k]
        pa = paradigm_acc(d, meta40); acc = compute_baseline_metrics(d, meta40)["overall_accuracy"]["accuracy"]
        lo, hi = episode_bootstrap_ci(d, a.iters, a.seed)
        rows.append((acc, [n] + [pct(pa[p]) for p in PARADIGMS] + [f"{pct(acc)} [{pct(lo)}, {pct(hi)}]"]))
    L.append(md(["System", "Interf.", "Misinf.", "Consol.", "Recons.", "Overall [95% CI]"], [r for _, r in sorted(rows, key=lambda x: -x[0])]))

    text = "\n".join(L); print(text)
    if a.out: Path(a.out).write_text(text + "\n"); print(f"\n[paper_tables] wrote {a.out}", file=sys.stderr)

if __name__ == "__main__":
    main()
