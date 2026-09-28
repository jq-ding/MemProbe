#!/usr/bin/env python3
"""
USAGE
-----
    python expand_specs.py \
        --mini-specs   mini_specs.jsonl \
        --domain-config domain_config.json \
        --out          latent_specs.json

"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from presets import (  
    CONDITIONS_BY_PARADIGM, ENCODING_COUNT_OVERRIDES, EXPECTED_BEHAVIOR,
    LENGTH_TIERS, PARADIGM_METADATA_TEMPLATES, PARADIGMS,
    PERTURBATION_TEMPLATES, PROBE_TEMPLATES, build_gold, make_filler_plan,
)


def readable(fact_type: str) -> str:
    return fact_type.replace("_", " ")


def short_canonical(text: str, fallback_max_words: int = 3) -> str:
    if not text:
        return text
    words = text.replace(",", " ").replace(".", " ").split()
    take = []
    for w in words:
        if w[:1].isupper() and len(take) < fallback_max_words:
            take.append(w)
    return " ".join(take) if take else " ".join(words[:fallback_max_words])


def template_fill(s: str, mapping: Dict[str, str]) -> str:
    out = s
    for k, v in mapping.items():
        out = out.replace("{" + k + "}", v)
    return out


def load_domain_config(path: Optional[str]) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def pick_distractors(initial: str, new: str, pool: List[str], k: int = 3) -> List[str]:
    seen = {initial.lower(), new.lower()}
    out: List[str] = []
    for v in pool:
        if v.lower() in seen:
            continue
        if v.lower() in initial.lower() or v.lower() in new.lower():
            continue
        out.append(v)
        if len(out) == k:
            break
    return out


def default_encoding_contexts(fact: str, initial: str) -> List[str]:
    f = readable(fact)
    return [
        f"user asks a question whose answer naturally involves the {f} '{initial}'",
        f"user plans an activity around their {f} of '{initial}'",
        f"user mentions '{initial}' while comparing notes on {f}",
    ]


REQUIRED_MINI_FIELDS = (
    "episode_id", "paradigm", "condition", "domain",
    "fact_type", "initial_value", "new_value",
)


def expand_one(mini: Dict[str, Any], domain_cfg: Dict[str, Any]) -> Dict[str, Any]:
    missing = [f for f in REQUIRED_MINI_FIELDS if not mini.get(f)]
    if missing:
        raise ValueError(f"{mini.get('episode_id', '???')}: missing required fields {missing}")

    paradigm = mini["paradigm"]
    condition = mini["condition"]
    if paradigm not in PARADIGMS:
        raise ValueError(f"{mini['episode_id']}: unknown paradigm '{paradigm}' "
                         f"(supported: {PARADIGMS})")
    if condition not in CONDITIONS_BY_PARADIGM[paradigm]:
        raise ValueError(f"{mini['episode_id']}: condition '{condition}' "
                         f"not valid for paradigm '{paradigm}'. Supported: "
                         f"{CONDITIONS_BY_PARADIGM[paradigm]}")

    fact_type = mini["fact_type"]
    initial = mini["initial_value"]
    new = mini["new_value"]
    fact_cfg = (domain_cfg.get("fact_types", {}) or {}).get(fact_type, {})

    canonical_initial = mini.get("canonical_initial") or fact_cfg.get("canonical_initial") \
        or short_canonical(initial)
    canonical_new = mini.get("canonical_new") or fact_cfg.get("canonical_new") \
        or short_canonical(new)

    distractors = mini.get("distractor_values")
    if not distractors:
        pool = fact_cfg.get("distractor_values_pool", [])
        distractors = pick_distractors(initial, new, pool, k=3)
    if len(distractors) < 3:
        while len(distractors) < 3:
            distractors.append(f"{fact_type}_alt_{len(distractors)+1}")

    enc_contexts = mini.get("encoding_contexts") \
        or fact_cfg.get("encoding_contexts") \
        or default_encoding_contexts(fact_type, initial)

    length_tier = mini.get("length_tier", "core")
    if length_tier not in LENGTH_TIERS:
        raise ValueError(f"{mini['episode_id']}: unknown length_tier '{length_tier}' "
                         f"(supported: {list(LENGTH_TIERS)})")
    counts = dict(LENGTH_TIERS[length_tier])
    enc_override = ENCODING_COUNT_OVERRIDES.get((paradigm, condition))
    n_encoding = enc_override if enc_override is not None else counts["num_encoding_sessions"]
    enc_contexts = enc_contexts[:n_encoding] + enc_contexts[:max(0, n_encoding - len(enc_contexts))]
    encoding_block = {"support_count": n_encoding, "mention_contexts": enc_contexts[:n_encoding]}

    pt = PERTURBATION_TEMPLATES[(paradigm, condition)]
    wording = mini.get("perturbation_wording") or template_fill(
        pt["wording_hint"],
        {"initial": initial, "new": new, "fact": readable(fact_type)},
    )
    perturbation = {**{k: v for k, v in pt.items() if k != "wording_hint"},
                    "wording_hint": wording}

    filler_plan = make_filler_plan(length_tier)

    probe_templates = mini.get("probe_overrides") or PROBE_TEMPLATES[(paradigm, condition)]
    probes = [
        {"type": p["type"],
         "question_hint": template_fill(p["question_hint"], {"fact": readable(fact_type)})}
        for p in probe_templates
    ]

    gold = build_gold(initial, new, paradigm, condition)

    spec = {
        "episode_id":              mini["episode_id"],
        "group_id":                mini.get("group_id", mini["episode_id"]),
        "group_role":              mini.get("group_role", "primary"),
        "matched_variables":       ["fact_type", "encoding", "distractor_values",
                                    "filler_plan", "length_tier"],
        "variant_variables":       ["perturbation", "gold", "expected_behavior"],
        "paradigm":                paradigm,
        "condition":               condition,
        "domain":                  mini["domain"],
        "fact_type":               fact_type,
        "length_tier":             length_tier,
        "initial_value":           initial,
        "new_value":               new,
        "canonical_initial":       canonical_initial,
        "canonical_new":           canonical_new,
        "distractor_values":       distractors,
        "expected_behavior":       EXPECTED_BEHAVIOR[(paradigm, condition)],
        "encoding":                encoding_block,
        "perturbation":            perturbation,
        "filler_plan":             filler_plan,
        "num_encoding_sessions":   n_encoding,
        "num_pre_perturbation_fillers":  counts["num_pre_perturbation_fillers"],
        "num_perturbation_sessions":     1,
        "num_post_perturbation_fillers": counts["num_post_perturbation_fillers"],
        "perturbation_type":       _perturbation_type(paradigm, condition),
        "probes":                  probes,
        "gold":                    gold,
        "probe_types":             [p["type"] for p in probes],
        "base_fact_type":          mini.get("base_fact_type", fact_type),
        "difficulty_target":       mini.get("difficulty_target", "core"),
        "group_design":            mini.get("group_design", "singleton"),
        "generation_batch":        mini.get("generation_batch", "user_authored"),
        "paradigm_metadata":       PARADIGM_METADATA_TEMPLATES[(paradigm, condition)],
        "num_perturbation_events": 1,
        "perturbation_parts":      ["perturbation"],
        "split_perturbation":      False,
    }
    return spec


def _perturbation_type(paradigm: str, condition: str) -> str:
    if EXPECTED_BEHAVIOR[(paradigm, condition)] == "should_update":
        return "direct_update"
    return f"weak_challenge_{condition}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mini-specs",   required=True,
                    help="Path to user-authored JSONL of minimal specs.")
    ap.add_argument("--domain-config",
                    help="Optional domain_config.json with per-fact-type defaults.")
    ap.add_argument("--out", required=True,
                    help="Output latent_specs JSON path "
                         "(same shape as data/suite56/latent_specs.json).")
    ap.add_argument("--description", default="",
                    help="Description string to put in the output JSON.")
    args = ap.parse_args()

    domain_cfg = load_domain_config(args.domain_config)

    mini_specs = []
    with open(args.mini_specs) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            mini_specs.append(json.loads(line))
    print(f"[expand] read {len(mini_specs)} mini-specs from {args.mini_specs}")

    specs: List[Dict[str, Any]] = []
    errors: List[str] = []
    for i, mini in enumerate(mini_specs, 1):
        try:
            specs.append(expand_one(mini, domain_cfg))
        except Exception as e:
            errors.append(f"  [{i}] {mini.get('episode_id','???')}: {e}")

    if errors:
        print(f"[expand] {len(errors)} errors:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
    print(f"[expand] expanded {len(specs)}/{len(mini_specs)} specs")

    out = {
        "description": args.description or f"User-authored suite "
                                            f"({len(specs)} episodes, "
                                            f"domain={domain_cfg.get('domain','?')})",
        "backend": "user_authored",
        "model": None,
        "specs": specs,
    }
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"[expand] wrote {args.out} ({len(specs)} specs)")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
