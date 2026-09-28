#!/usr/bin/env python3
"""Reader-swap runner: reads cached (memory-system, dataset) prompts and re-answers with a different reader LLM.

USAGE
-----
    python reader_swap.py \\
        --cache results/suite56/prompt_caches/baselines_report_amem_qwen3_prompts.json \\
        --specs data/suite56/latent_specs.json \\
        --output results/suite56/reports/baselines_report_amem_gemini.json \\
        --backend gemini --model gemini-3-flash-preview \\
        --baseline-key amem_full
"""
import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import paths as P  # noqa: E402
P.add_src_to_path()
from llm import call_llm, set_llm_backend
from protocol import READER_SYSTEM, score_answer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache",   required=True, help="prompts.json cache file")
    ap.add_argument("--specs",   required=True, help="latent_specs JSON")
    ap.add_argument("--output",  required=True)
    ap.add_argument("--backend", required=True)
    ap.add_argument("--model",   required=True)
    ap.add_argument("--baseline-key", required=True,
                    help="Top-level key in output JSON (e.g. amem_full).")
    args = ap.parse_args()

    cache = json.loads(Path(args.cache).read_text())
    specs = {s["episode_id"]: s for s in json.loads(Path(args.specs).read_text())["specs"]}
    print(f"[reader-swap] cache has {len(cache)} episodes, backend={args.backend} model={args.model}")

    set_llm_backend(args.backend)

    results = {args.baseline_key: {}}
    if Path(args.output).exists():
        results = json.loads(Path(args.output).read_text())
        done = set(results.get(args.baseline_key, {}).keys())
        print(f"[reader-swap] resuming, {len(done)} eps done")
    else:
        done = set()

    t0 = time.time()
    for eid, probes in cache.items():
        if eid in done:
            continue
        spec = specs.get(eid, {})
        ep_results = []
        for p in probes:
            try:
                pred = call_llm(READER_SYSTEM, p["prompt"], model=args.model,
                                temperature=0.0, max_tokens=4096)
            except Exception as e:
                pred = f"[ERROR: {e.__class__.__name__}]"
            sc = score_answer(pred, p.get("gold_answer", ""), p["probe_type"], spec=spec)
            ep_results.append({
                "probe_type": p["probe_type"],
                "gold": p.get("gold_answer", ""),
                "predicted": pred,
                "match": sc["match"],
                "reason": sc["reason"],
            })
        results[args.baseline_key][eid] = ep_results
        Path(args.output).write_text(json.dumps(results, indent=2))
        nc = sum(1 for a in ep_results if a["match"] == "correct")
        print(f"  {eid}: {nc}/{len(ep_results)}  total={time.time()-t0:.0f}s", flush=True)

    total_c = sum(1 for eid, ans in results[args.baseline_key].items() for a in ans if a["match"] == "correct")
    total_n = sum(1 for eid, ans in results[args.baseline_key].items() for a in ans if a["match"] in ("correct","incorrect","partial"))
    print(f"\n[reader-swap] DONE. {total_c}/{total_n} = {100*total_c/total_n:.1f}%")


if __name__ == "__main__":
    main()
