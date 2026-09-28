#!/usr/bin/env python3
"""
Usage:
  python build_filler_pool.py --output filler_pool.json
  python build_filler_pool.py --output filler_pool.json --max-per-source 10000
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def extract_longmemeval(max_sessions: int = 50000) -> List[Dict]:
    from huggingface_hub import hf_hub_download

    log.info("Downloading LongMemEval _s ...")
    fp = hf_hub_download(
        repo_id="xiaowu0162/longmemeval-cleaned",
        filename="longmemeval_s_cleaned.json",
        repo_type="dataset",
    )
    with open(fp) as f:
        data = json.load(f)
    log.info(f"  Loaded {len(data)} instances")

    sessions = []
    for inst_idx, inst in enumerate(data):
        for sess_idx, sess in enumerate(inst.get("haystack_sessions", [])):
            if not sess or len(sess) < 2:
                continue
            valid = all(
                isinstance(t, dict) and "role" in t and "content" in t
                and t["role"] in ("user", "assistant")
                and isinstance(t["content"], str) and t["content"].strip()
                for t in sess
            )
            if not valid:
                continue
            sessions.append({
                "source": "longmemeval_s",
                "session_id": f"lme_s_{inst_idx}_{sess_idx}",
                "dialogue": [{"role": t["role"], "content": t["content"]} for t in sess],
            })
            if len(sessions) >= max_sessions:
                log.info(f"  Reached max_sessions cap ({max_sessions})")
                return sessions
    log.info(f"  Extracted {len(sessions)} sessions from LongMemEval")
    return sessions


def extract_locomo(max_sessions: int = 50000) -> List[Dict]:
    from huggingface_hub import hf_hub_download

    log.info("Downloading LoCoMo ...")
    fp = hf_hub_download(
        repo_id="Aman279/Locomo",
        filename="locomo.csv",
        repo_type="dataset",
    )
    csv.field_size_limit(10 * 1024 * 1024) 

    sessions = []
    with open(fp) as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader):
            try:
                turns_data = json.loads(row["turns"])
            except (json.JSONDecodeError, KeyError):
                continue

            roles_list = turns_data.get("speaker_role", [])
            content_list = turns_data.get("utterance", []) or turns_data.get("turns", [])
            if not roles_list or not content_list or len(roles_list) != len(content_list):
                continue

            unique_speakers = list(dict.fromkeys(roles_list))
            if len(unique_speakers) < 2:
                continue
            speaker_to_role = {
                unique_speakers[0]: "user",
                unique_speakers[1]: "assistant",
            }

            full = []
            for sp, txt in zip(roles_list, content_list):
                if sp not in speaker_to_role:
                    continue
                if not isinstance(txt, str) or not txt.strip():
                    continue
                full.append({"role": speaker_to_role[sp], "content": txt.strip()})

            if len(full) < 2:
                continue

            chunk_size = 6
            for chunk_idx in range(0, len(full), chunk_size):
                chunk = full[chunk_idx : chunk_idx + chunk_size]
                if len(chunk) < 2:
                    continue
                if chunk[0]["role"] != "user":
                    chunk = chunk[1:] if len(chunk) > 1 else chunk
                if len(chunk) < 2:
                    continue
                sessions.append({
                    "source": "locomo",
                    "session_id": f"locomo_{row_idx}_{chunk_idx}",
                    "dialogue": chunk,
                })
                if len(sessions) >= max_sessions:
                    log.info(f"  Reached max_sessions cap ({max_sessions})")
                    return sessions
    log.info(f"  Extracted {len(sessions)} sessions from LoCoMo")
    return sessions


def filter_and_clean(sessions: List[Dict], min_turns: int = 2, max_turns: int = 20) -> List[Dict]:
    cleaned = []
    seen_first_turn = set()  
    for sess in sessions:
        dlg = sess["dialogue"]
        if not (min_turns <= len(dlg) <= max_turns):
            continue
        total_chars = sum(len(t["content"]) for t in dlg)
        if total_chars < 100:
            continue
        first_text = dlg[0]["content"][:200].strip().lower()
        if first_text in seen_first_turn:
            continue
        seen_first_turn.add(first_text)
        cleaned.append(sess)
    log.info(f"After cleaning: {len(cleaned)} sessions (kept {len(cleaned)/max(1,len(sessions))*100:.1f}%)")
    return cleaned


def main():
    parser = argparse.ArgumentParser(description="Build filler pool from memory benchmarks")
    parser.add_argument("--output", default="filler_pool.json", help="Output JSON path")
    parser.add_argument("--max-per-source", type=int, default=20000,
                        help="Max sessions to take from each source (default: 20000)")
    parser.add_argument("--sources", nargs="+", default=["longmemeval", "locomo"],
                        choices=["longmemeval", "locomo"],
                        help="Which sources to include")
    args = parser.parse_args()

    all_sessions = []

    if "longmemeval" in args.sources:
        all_sessions.extend(extract_longmemeval(args.max_per_source))

    if "locomo" in args.sources:
        all_sessions.extend(extract_locomo(args.max_per_source))

    log.info(f"Total raw sessions: {len(all_sessions)}")
    cleaned = filter_and_clean(all_sessions)

    from collections import Counter
    source_counts = Counter(s["source"] for s in cleaned)
    log.info("Pool composition:")
    for src, cnt in source_counts.most_common():
        log.info(f"  {src}: {cnt}")

    Path(args.output).write_text(json.dumps(cleaned, ensure_ascii=False))
    log.info(f"Wrote {len(cleaned)} sessions to {args.output}")
    log.info(f"File size: {Path(args.output).stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
