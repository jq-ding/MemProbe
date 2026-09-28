#!/usr/bin/env python3
"""Use an LLM (default: gemini-3-flash-preview) to propose a starter `domain_config.json` for a custom domain.
The output is written to `--out` and matches the format consumed by `expand_specs.py --domain-config`.

USAGE
-----
    export GEMINI_API_KEY=...
    python propose_facts_with_llm.py \\
        --domain "restaurant_reviews" \\
        --description "users discuss restaurants they visit, dishes they like, and reservations" \\
        --n-fact-types 8 \\
        --out my_suites/restaurant_reviews/domain_config.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import paths as _P  
_P.add_src_to_path()
from llm import call_llm, set_llm_backend  

SYSTEM_PROMPT = """You are designing a memory-evaluation benchmark called MemProbe.
For a given domain, you propose a registry of "fact types" — discrete attributes
about a user that can change over time. For each fact type you also propose
plausible distractor values, natural encoding-context phrases (how a user would
mention the value organically in chat), and one example initial/new value pair
(used as the starting episode).

Quality rules:
- Each fact type must be a SINGLE attribute that has ONE current value at a time
  (e.g. "favorite_dish": "Tom Yum", not "list of favorite dishes").
- Values must be concrete strings (named entities, short noun phrases, IDs,
  enum-like categories). NOT free-text descriptions.
- distractor_values should be SAME-CATEGORY alternatives that could plausibly
  be confused with the real value (used to generate near-miss filler sessions).
- encoding_contexts are 1-sentence descriptions of conversational situations in
  which the user naturally mentions the value. They should be VARIED so the
  same fact gets mentioned in different ways.
- initial/new value pair should differ MEANINGFULLY (a real update), not be
  near-paraphrases.

Output ONLY valid JSON, no prose, no markdown fences."""


USER_TEMPLATE = """Domain name: {domain}
Domain description: {description}

Propose exactly {n_fact_types} fact types for this domain.

Return a JSON object with this exact schema:

{{
  "domain": "{domain}",
  "description": "{description}",
  "style": "<1 short sentence describing the tone of dialogue in this domain>",
  "fact_types": {{
    "<snake_case_fact_type_name>": {{
      "readable":              "<human-readable name>",
      "encoding_contexts":     ["<context 1>", "<context 2>", "<context 3>", "<context 4>"],
      "distractor_values_pool":["<distractor 1>", "<distractor 2>", "<distractor 3>",
                                "<distractor 4>", "<distractor 5>"],
      "example_initial_value": "<a concrete value>",
      "example_new_value":     "<a concrete different value>"
    }},
    ...
  }}
}}

Output ONLY the JSON object — no prose, no markdown fences."""


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domain",      required=True, help="Short domain slug.")
    ap.add_argument("--description", required=True,
                    help="1-2 sentence description of the domain.")
    ap.add_argument("--n-fact-types", type=int, default=8)
    ap.add_argument("--out",         required=True, help="Output domain_config.json path.")
    ap.add_argument("--backend", default="gemini",
                    help="LLM backend (gemini / dashscope / anthropic / ...).")
    ap.add_argument("--model", default="gemini-3-flash-preview")
    args = ap.parse_args()

    set_llm_backend(args.backend)
    prompt = USER_TEMPLATE.format(
        domain=args.domain, description=args.description,
        n_fact_types=args.n_fact_types,
    )
    print(f"[propose] asking {args.model} for {args.n_fact_types} fact types "
          f"for domain='{args.domain}'...")
    raw = call_llm(SYSTEM_PROMPT, prompt, model=args.model,
                   temperature=0.7, max_tokens=4096)

    try:
        cfg = extract_json(raw)
    except json.JSONDecodeError as e:
        print(f"[propose] LLM output is not valid JSON: {e}", file=sys.stderr)
        print("---- raw output ----", file=sys.stderr)
        print(raw, file=sys.stderr)
        sys.exit(1)

    starter_minis = []
    for ft_name, ft in list(cfg.get("fact_types", {}).items()):
        ex_init = ft.pop("example_initial_value", None)
        ex_new = ft.pop("example_new_value", None)
        if ex_init and ex_new:
            starter_minis.append({"fact_type": ft_name,
                                  "initial_value": ex_init,
                                  "new_value":     ex_new})

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cfg, indent=2))
    print(f"[propose] wrote {out_path} ({len(cfg.get('fact_types', {}))} fact types)")

    starter_path = out_path.parent / "starter_minis.jsonl"
    if starter_minis:
        with open(starter_path, "w") as f:
            f.write("# Suggested initial/new value pairs (one per fact type). Copy useful\n")
            f.write("# entries into your mini_specs.jsonl, adding episode_id / paradigm /\n")
            f.write("# condition fields.\n")
            for m in starter_minis:
                f.write(json.dumps(m) + "\n")
        print(f"[propose] wrote {starter_path} ({len(starter_minis)} starter value pairs)")


if __name__ == "__main__":
    main()
