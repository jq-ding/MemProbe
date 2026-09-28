#!/usr/bin/env python3
"""
Usage:
  python populate_fillers.py \
      --episodes episodes_all.jsonl \
      --pool filler_pool.json \
      --specs latent_specs.json \
      --output episodes_filled.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
from pathlib import Path
from typing import Dict, List, Set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def session_text(session: Dict) -> str:
    return " ".join(t.get("content", "") for t in session.get("dialogue", []))


def is_placeholder(session: Dict) -> bool:
    if session.get("metadata", {}).get("source") == "placeholder":
        return True
    text = session_text(session).lower()
    return "[placeholder" in text


def compute_exclude_tokens(spec: Dict) -> Set[str]:
    tokens: Set[str] = set()
    for field in (spec.get("initial_value", ""), spec.get("new_value", ""),
                  spec.get("fact_type", "").replace("_", " ")):
        for w in re.findall(r"\w+", field.lower()):
            if len(w) >= 4 and w not in {
                "this", "that", "with", "from", "what", "when", "have",
                "been", "they", "them", "your", "these", "those", "into",
                "would", "could", "should", "today", "next", "last",
            }:
                tokens.add(w)
    return tokens


def is_safe_for_episode(session: Dict, exclude_tokens: Set[str]) -> bool:
    if not exclude_tokens:
        return True
    text = session_text(session).lower()
    for tok in exclude_tokens:
        if re.search(rf"\b{re.escape(tok)}\b", text):
            return False
    return True


def populate(
    episodes_path: str,
    pool_path: str,
    specs_path: str,
    output_path: str,
    seed: int = 42,
) -> None:
    log.info(f"Loading filler pool from {pool_path}")
    pool: List[Dict] = json.loads(Path(pool_path).read_text())
    log.info(f"  Pool size: {len(pool)} sessions")

    log.info(f"Loading specs from {specs_path}")
    specs_data = json.loads(Path(specs_path).read_text())
    spec_by_id = {s["episode_id"]: s for s in specs_data["specs"]}

    log.info(f"Loading episodes from {episodes_path}")
    episodes = []
    with open(episodes_path) as f:
        for line in f:
            line = line.strip()
            if line:
                episodes.append(json.loads(line))
    log.info(f"  Episodes: {len(episodes)}")

    total_replaced = 0
    total_placeholders = 0
    insufficient_pool_episodes = []

    for ep in episodes:
        eid = ep["episode_id"]
        spec = spec_by_id.get(eid)
        if spec is None:
            log.warning(f"  {eid}: no spec found, skipping")
            continue

        placeholder_indices = [
            i for i, s in enumerate(ep["sessions"])
            if s.get("session_type", "").startswith("filler_generic") and is_placeholder(s)
        ]
        if not placeholder_indices:
            continue

        total_placeholders += len(placeholder_indices)
        n_needed = len(placeholder_indices)

        exclude = compute_exclude_tokens(spec)

        ep_rng = random.Random(f"{seed}-{eid}")
        candidate_indices = list(range(len(pool)))
        ep_rng.shuffle(candidate_indices)

        chosen: List[Dict] = []
        for idx in candidate_indices:
            if len(chosen) >= n_needed:
                break
            cand = pool[idx]
            if is_safe_for_episode(cand, exclude):
                chosen.append(cand)

        if len(chosen) < n_needed:
            insufficient_pool_episodes.append((eid, n_needed, len(chosen)))
            extra_needed = n_needed - len(chosen)
            extra_pool = [pool[i] for i in candidate_indices if pool[i] not in chosen]
            chosen.extend(extra_pool[:extra_needed])

        for placeholder_idx, real in zip(placeholder_indices, chosen):
            ep["sessions"][placeholder_idx] = {
                "session_type": "filler_generic",
                "dialogue": real["dialogue"],
                "metadata": {
                    "source": real.get("source", "unknown"),
                    "session_id": real.get("session_id", ""),
                },
            }
            total_replaced += 1

    log.info(f"\nReplacement summary:")
    log.info(f"  Total placeholder fillers found:  {total_placeholders}")
    log.info(f"  Total replaced with real content: {total_replaced}")
    log.info(f"  Episodes with insufficient pool:   {len(insufficient_pool_episodes)}")
    if insufficient_pool_episodes[:5]:
        for eid, needed, got in insufficient_pool_episodes[:5]:
            log.info(f"    {eid}: needed {needed}, found {got} safe")

    with open(output_path, "w") as f:
        for ep in episodes:
            f.write(json.dumps(ep, ensure_ascii=False) + "\n")
    log.info(f"\nWrote {len(episodes)} populated episodes to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Populate filler_generic placeholders with real benchmark sessions")
    parser.add_argument("--episodes", default="episodes_all.jsonl", help="Input episodes JSONL")
    parser.add_argument("--pool", default="filler_pool.json", help="Filler pool JSON")
    parser.add_argument("--specs", default="latent_specs.json", help="Latent specs JSON")
    parser.add_argument("--output", default="episodes_filled.jsonl", help="Output episodes JSONL")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic sampling")
    args = parser.parse_args()
    populate(args.episodes, args.pool, args.specs, args.output, args.seed)


if __name__ == "__main__":
    main()
