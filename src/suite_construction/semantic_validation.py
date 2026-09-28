#!/usr/bin/env python3
"""
Usage:
    # Run semantic validation on generated episodes
    python semantic_validation.py --episodes episodes_all.jsonl --specs latent_specs.json

    # Run only specific checks
    python semantic_validation.py --episodes episodes_all.jsonl --specs latent_specs.json --checks source probe

    # Limit to specific episodes
    python semantic_validation.py --episodes episodes_all.jsonl --specs latent_specs.json --only EP-0001 EP-0038
"""

from __future__ import annotations

import json
import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import paths as P  
P.add_src_to_path()
from validation_prompts import (
    source_clarity_prompt,
    probe_consistency_check_prompt,
    filler_leak_semantic_check_prompt,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def _session_to_text(session: Dict) -> str:
    lines = []
    for turn in session.get("dialogue", []):
        role = turn["role"].upper()
        lines.append(f"[{role}] {turn['content']}")
    return "\n".join(lines)


def _parse_json_response(raw: str) -> Dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        log.warning(f"Failed to parse JSON response: {text[:200]}...")
        return {"parse_error": True, "raw": text[:500]}


def _expected_source(spec: Dict) -> str:
    condition = spec["condition"]
    source_map = {
        "standard": "user",
        "high": "user",
        "low": "user",
        "reactivated": "user",
        "direct": "user",
        "user_explicit": "user",
        "assistant_noise": "assistant",
        "third_party_noise": "third_party",
        "noise": "third_party",
        "scope_restricted": "user",
        "high_challenge": "third_party",
        "low_challenge": "third_party",
        "reactivated_weak": "third_party",
    }
    return source_map.get(condition, "user")


def check_source_clarity(episode: Dict, spec: Dict, call_fn) -> Dict:
    pert_sessions = [s for s in episode["sessions"] if s["session_type"] == "perturbation"]
    if not pert_sessions:
        return {"skipped": True, "reason": "no perturbation session"}

    pert_text = _session_to_text(pert_sessions[0])
    expected = _expected_source(spec)
    system, prompt = source_clarity_prompt(pert_text, expected)
    raw = call_fn(system, prompt)
    result = _parse_json_response(raw)
    result["expected_source"] = expected
    return result


def check_probe_consistency(episode: Dict, spec: Dict, call_fn) -> Dict:
    probes = episode.get("probes", [])
    if len(probes) < 4:
        return {"skipped": True, "reason": f"only {len(probes)} probes (need 4)"}

    system, prompt = probe_consistency_check_prompt(probes, spec)
    raw = call_fn(system, prompt)
    return _parse_json_response(raw)


def check_filler_leaks(episode: Dict, spec: Dict, call_fn) -> Dict:
    near_miss = [s for s in episode["sessions"] if s["session_type"] == "filler_near_miss"]
    if not near_miss:
        return {"skipped": True, "reason": "no near-miss fillers"}

    sample = near_miss[:3]
    results = []
    any_leak = False

    for i, filler in enumerate(sample):
        filler_text = _session_to_text(filler)
        system, prompt = filler_leak_semantic_check_prompt(
            filler_text, spec["fact_type"], spec["initial_value"], spec["new_value"]
        )
        raw = call_fn(system, prompt)
        r = _parse_json_response(raw)
        r["filler_index"] = i
        results.append(r)
        if r.get("has_leak"):
            any_leak = True

    return {"any_leak": any_leak, "filler_checks": results}


def classify_failures(
    episode_id: str,
    rule_validation: Dict,
    semantic_results: Dict,
) -> List[Dict]:
    failures = []

    for check in rule_validation.get("rule_checks", []):
        if not check["passed"]:
            name = check["check"]
            msg = check["message"]

            if name == "initial_value_present":
                failures.append({
                    "category": "support_mismatch",
                    "severity": "critical",
                    "detail": msg,
                    "action": "regenerate",
                })
            elif name == "perturbation_value":
                failures.append({
                    "category": "support_mismatch",
                    "severity": "critical",
                    "detail": msg,
                    "action": "regenerate",
                })
            elif name == "filler_leak":
                failures.append({
                    "category": "target_leak",
                    "severity": "critical",
                    "detail": msg,
                    "action": "regenerate",
                })
            elif name == "speaker_roles":
                failures.append({
                    "category": "source_unclear",
                    "severity": "major",
                    "detail": msg,
                    "action": "regenerate",
                })
            elif name == "probe_coverage":
                failures.append({
                    "category": "probe_ambiguous",
                    "severity": "major",
                    "detail": msg,
                    "action": "regenerate",
                })
            else:
                failures.append({
                    "category": "structural",
                    "severity": "minor",
                    "detail": msg,
                    "action": "review",
                })

    source = semantic_results.get("source_clarity", {})
    if source and not source.get("skipped"):
        if not source.get("source_clear"):
            failures.append({
                "category": "source_unclear",
                "severity": "critical",
                "detail": source.get("issues", "source not clear"),
                "action": "regenerate",
            })
        elif not source.get("matches_expected"):
            failures.append({
                "category": "source_mismatch",
                "severity": "major",
                "detail": f"Expected {source.get('expected_source')}, "
                          f"identified {source.get('identified_source')}",
                "action": "regenerate",
            })

    probes = semantic_results.get("probe_consistency", {})
    if probes and not probes.get("skipped"):
        if not probes.get("consistent"):
            sev = probes.get("severity", "minor")
            failures.append({
                "category": "probe_ambiguous",
                "severity": "critical" if sev == "critical" else "major",
                "detail": "; ".join(probes.get("issues", [])),
                "action": "regenerate" if sev == "critical" else "review",
            })

    filler = semantic_results.get("filler_leak", {})
    if filler and not filler.get("skipped") and filler.get("any_leak"):
        for fc in filler.get("filler_checks", []):
            if fc.get("has_leak") and fc.get("severity") in ("critical", "moderate"):
                failures.append({
                    "category": "target_leak",
                    "severity": "critical" if fc["severity"] == "critical" else "major",
                    "detail": fc.get("details", "semantic leak detected"),
                    "action": "regenerate",
                })

    return failures


def run_semantic_validation(
    episodes_path: str,
    specs_path: str,
    output_path: str = "semantic_validation_report.json",
    checks: Optional[List[str]] = None,
    episode_ids: Optional[List[str]] = None,
    backend: str = "huggingface",
):
    from llm import call_llm, set_llm_backend
    set_llm_backend(backend)

    specs_data = json.loads(Path(specs_path).read_text())
    specs_by_id = {s["episode_id"]: s for s in specs_data["specs"]}

    episodes = []
    with open(episodes_path) as f:
        for line in f:
            line = line.strip()
            if line:
                episodes.append(json.loads(line))

    if episode_ids:
        id_set = set(episode_ids)
        episodes = [e for e in episodes if e["episode_id"] in id_set]

    log.info(f"Running semantic validation on {len(episodes)} episodes")

    run_checks = set(checks or ["source", "probe", "filler"])

    all_results = {}
    all_failures = {}
    summary = {
        "total": len(episodes),
        "source_clear": 0, "source_unclear": 0,
        "probes_consistent": 0, "probes_inconsistent": 0,
        "filler_clean": 0, "filler_leak": 0,
        "fully_passed": 0, "has_failures": 0,
    }

    for i, episode in enumerate(episodes):
        eid = episode["episode_id"]
        spec = specs_by_id.get(eid)
        if not spec:
            log.warning(f"No spec for {eid}, skipping")
            continue

        log.info(f"[{i+1}/{len(episodes)}] Validating {eid} "
                 f"({spec['paradigm']}/{spec['condition']})")

        semantic = {}

        if "source" in run_checks:
            try:
                result = check_source_clarity(episode, spec, call_llm)
                semantic["source_clarity"] = result
                if result.get("source_clear"):
                    summary["source_clear"] += 1
                elif not result.get("skipped"):
                    summary["source_unclear"] += 1
            except Exception as e:
                log.error(f"  {eid} source_clarity failed: {e}")
                semantic["source_clarity"] = {"error": str(e)}

        if "probe" in run_checks:
            try:
                result = check_probe_consistency(episode, spec, call_llm)
                semantic["probe_consistency"] = result
                if result.get("consistent"):
                    summary["probes_consistent"] += 1
                elif not result.get("skipped"):
                    summary["probes_inconsistent"] += 1
            except Exception as e:
                log.error(f"  {eid} probe_consistency failed: {e}")
                semantic["probe_consistency"] = {"error": str(e)}

        if "filler" in run_checks:
            try:
                result = check_filler_leaks(episode, spec, call_llm)
                semantic["filler_leak"] = result
                if not result.get("any_leak"):
                    summary["filler_clean"] += 1
                elif not result.get("skipped"):
                    summary["filler_leak"] += 1
            except Exception as e:
                log.error(f"  {eid} filler_leak failed: {e}")
                semantic["filler_leak"] = {"error": str(e)}

        all_results[eid] = semantic

        rule_val = episode.get("validation", {})
        failures = classify_failures(eid, rule_val, semantic)
        if failures:
            all_failures[eid] = failures
            summary["has_failures"] += 1
            log.warning(f"  {eid}: {len(failures)} issues — "
                        + ", ".join(f['category'] for f in failures))
        else:
            summary["fully_passed"] += 1

        time.sleep(0.5)

    report = {
        "summary": summary,
        "episodes_to_regenerate": [
            eid for eid, fails in all_failures.items()
            if any(f["action"] == "regenerate" for f in fails)
        ],
        "episodes_to_review": [
            eid for eid, fails in all_failures.items()
            if all(f["action"] == "review" for f in fails)
        ],
        "failure_details": all_failures,
        "semantic_results": all_results,
    }

    Path(output_path).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log.info(f"\nSemantic validation complete:")
    log.info(f"  Total episodes: {summary['total']}")
    log.info(f"  Fully passed:   {summary['fully_passed']}")
    log.info(f"  Has failures:   {summary['has_failures']}")
    log.info(f"  Source clear:   {summary['source_clear']}")
    log.info(f"  Source unclear: {summary['source_unclear']}")
    log.info(f"  Probes OK:      {summary['probes_consistent']}")
    log.info(f"  Probes bad:     {summary['probes_inconsistent']}")
    log.info(f"  Fillers clean:  {summary['filler_clean']}")
    log.info(f"  Fillers leak:   {summary['filler_leak']}")
    log.info(f"  To regenerate:  {len(report['episodes_to_regenerate'])}")
    log.info(f"  To review:      {len(report['episodes_to_review'])}")
    log.info(f"  Report:         {output_path}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="MemProbe Semantic Validation (Step 5b)",
        epilog="""
Examples:
  python semantic_validation.py --episodes episodes_all.jsonl --specs latent_specs.json
  python semantic_validation.py --episodes episodes_all.jsonl --specs latent_specs.json --checks source probe
  python semantic_validation.py --episodes episodes_all.jsonl --specs latent_specs.json --only EP-0001 EP-0038
        """,
    )
    parser.add_argument("--episodes", required=True, help="Path to episodes JSONL")
    parser.add_argument("--specs", default="latent_specs.json", help="Path to latent_specs.json")
    parser.add_argument("--output", default="semantic_validation_report.json", help="Output report path")
    parser.add_argument("--checks", nargs="+", default=None,
                        choices=["source", "probe", "filler"],
                        help="Which checks to run (default: all)")
    parser.add_argument("--only", nargs="+", default=None, help="Only validate these episode IDs")
    parser.add_argument("--backend", default="dashscope",
                        choices=["dashscope", "azure", "local", "huggingface", "groq", "anthropic"],
                        help="LLM backend for judge calls")

    args = parser.parse_args()
    run_semantic_validation(
        episodes_path=args.episodes,
        specs_path=args.specs,
        output_path=args.output,
        checks=args.checks,
        episode_ids=args.only,
        backend=args.backend,
    )


if __name__ == "__main__":
    main()
