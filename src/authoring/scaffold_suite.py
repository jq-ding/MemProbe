#!/usr/bin/env python3
"""Create a new suite skeleton for a custom domain.
USAGE
-----
    python scaffold_suite.py --name restaurant_reviews --out ./my_suites/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


README_TEMPLATE = """# MemProbe suite: {name}

Auto-scaffolded by `authoring/scaffold_suite.py`. This is a **starter
skeleton** — edit the files below to define your custom domain.

## Files

| File | Purpose | Status |
|---|---|---|
| `domain_config.json` | Per-fact-type defaults (canonicals, distractors, encoding contexts). | **EDIT ME** |
| `mini_specs.jsonl`   | One JSON object per line; each defines one episode. | **EDIT ME** |
| `latent_specs.json`  | (Generated) Full spec output from `expand_specs.py`. | generated |
| `episodes.jsonl`     | (Generated) Realized sessions/probes from `realize_episodes.py`. | generated |

## Quickstart

```bash
# 0. (optional) ask an LLM to propose fact types + value pairs for your domain
python ../authoring/propose_facts_with_llm.py \\
    --domain "{name}" \\
    --description "describe your domain in 1-2 sentences" \\
    --out domain_config.json

# 1. Hand-edit domain_config.json and mini_specs.jsonl

# 2. Expand mini specs into full latent_specs
python ../authoring/expand_specs.py \\
    --mini-specs mini_specs.jsonl \\
    --domain-config domain_config.json \\
    --out latent_specs.json

# 3. Validate (catches missing/inconsistent fields BEFORE you spend LLM tokens)
python ../authoring/validate_suite.py latent_specs.json

# 4. Realize episodes (calls an LLM per session — costs real money)
python ../suite_construction/realize_episodes.py --filler-mode pool \\
    --specs latent_specs.json \\
    --backend gemini \\
    --output episodes.jsonl

# 5. Validate the realized episodes
python ../authoring/validate_suite.py episodes.jsonl

# 6. Run baselines
python ../eval/run_eval.py --system full_context naive_rag --episodes episodes.jsonl --specs latent_specs.json \\
    --only full_context naive_rag
```

## Paradigms × conditions (cheat-sheet)

- **interference** — competing similar facts. Conditions:
  `authoritative_update` (should_update), `decoy_no_update` (should_preserve).
- **misinformation** — wrong/conflicting evidence. Conditions:
  `user_explicit` (should_update), `assistant_noise`, `third_party_noise`,
  `stale_tool` (all should_preserve).
- **consolidation** — repeated reinforcement. Conditions: `high`, `low`
  (both should_update), `high_weak_challenge`, `low_weak_challenge`
  (both should_preserve).
- **reconsolidation** — updates after reactivating an old memory.
  Conditions: `reactivated`, `direct` (both should_update),
  `reactivated_weak`, `direct_weak` (both should_preserve).

See `../authoring/AUTHORING_GUIDE.md` for the full conceptual model.
"""

DOMAIN_CONFIG_TEMPLATE = {
    "domain": "{NAME}",
    "description": "Fill in: 1-2 sentence description of what this domain represents.",
    "style": "Fill in: tone the dialogue should use (e.g. 'casual chat', 'professional', 'technical').",
    "fact_types": {
        "example_fact_type": {
            "readable": "example fact type",
            "encoding_contexts": [
                "user asks for X around the value",
                "user plans an activity involving the value",
                "user references the value while comparing notes"
            ],
            "distractor_values_pool": [
                "alt_value_1", "alt_value_2", "alt_value_3",
                "alt_value_4", "alt_value_5"
            ]
        }
    }
}

MINI_SPECS_TEMPLATE = [
    {"episode_id": "{NAME_UC}-INT-01", "paradigm": "interference", "condition": "authoritative_update",
     "domain": "{NAME}", "fact_type": "example_fact_type",
     "initial_value": "first value", "new_value": "second value"},
    {"episode_id": "{NAME_UC}-MIS-01", "paradigm": "misinformation", "condition": "assistant_noise",
     "domain": "{NAME}", "fact_type": "example_fact_type",
     "initial_value": "first value", "new_value": "incorrect value"},
    {"episode_id": "{NAME_UC}-CON-01", "paradigm": "consolidation", "condition": "high",
     "domain": "{NAME}", "fact_type": "example_fact_type",
     "initial_value": "first value", "new_value": "later value"},
    {"episode_id": "{NAME_UC}-REC-01", "paradigm": "reconsolidation", "condition": "reactivated",
     "domain": "{NAME}", "fact_type": "example_fact_type",
     "initial_value": "first value", "new_value": "updated value"},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True,
                    help="Short domain slug (e.g. 'restaurant_reviews'). "
                         "Used for the directory name and as the domain field.")
    ap.add_argument("--out", default=".",
                    help="Parent directory under which to create <name>/.")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite existing directory.")
    args = ap.parse_args()

    name = args.name
    name_uc = name.upper().replace("-", "_")
    out = Path(args.out).resolve() / name
    if out.exists() and not args.force:
        print(f"[scaffold] {out} already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)
    out.mkdir(parents=True, exist_ok=True)

    (out / "README.md").write_text(README_TEMPLATE.format(name=name))

    cfg = json.loads(json.dumps(DOMAIN_CONFIG_TEMPLATE).replace("{NAME}", name))
    (out / "domain_config.json").write_text(json.dumps(cfg, indent=2))

    lines = []
    lines.append("# One JSON object per line. Required fields: episode_id, paradigm,")
    lines.append("# condition, domain, fact_type, initial_value, new_value.")
    lines.append("# Optional: canonical_initial, canonical_new, distractor_values,")
    lines.append("# encoding_contexts, length_tier, group_id.")
    for row in MINI_SPECS_TEMPLATE:
        s = json.dumps(row).replace("{NAME}", name).replace("{NAME_UC}", name_uc)
        lines.append(s)
    (out / "mini_specs.jsonl").write_text("\n".join(lines) + "\n")

    print(f"[scaffold] created {out}")
    print(f"  - README.md          (next steps)")
    print(f"  - domain_config.json (EDIT: fact types, value pools, encoding contexts)")
    print(f"  - mini_specs.jsonl   (EDIT: one row per episode)")
    print()
    print(f"Next: read {out}/README.md")


if __name__ == "__main__":
    main()
