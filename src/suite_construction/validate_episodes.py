#!/usr/bin/env python3
"""
python src/suite_construction/validate_episodes.py                      # 56 suite, per-episode checks
python src/suite_construction/validate_episodes.py --report             # + suite-level reports
python src/suite_construction/validate_episodes.py --episodes X.jsonl --specs Y.json --output report.json
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import paths as P 
P.add_src_to_path()

import argparse
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List


def count_mentions(text: str, value: str) -> int:
    if not value:
        return 0
    return len(re.findall(re.escape(value), text, re.IGNORECASE))


def get_all_text(session: Dict) -> str:
    parts = []
    for msg in session.get("dialogue", []):
        parts.append(msg.get("content", ""))
    return " ".join(parts)


def validate_episode(episode: Dict, spec: Dict) -> Dict:
    eid = episode["episode_id"]
    report = {
        "episode_id": eid,
        "errors": [],
        "warnings": [],
        "stats": {},
    }
    errors = report["errors"]
    warnings = report["warnings"]

    required_top = ["episode_id", "paradigm", "condition", "expected_behavior", "sessions", "probes"]
    for field in required_top:
        if field not in episode:
            errors.append(f"Missing top-level field: {field}")
    if "metadata" not in episode and "validation" not in episode:
        warnings.append("No metadata/validation block")

    sessions = episode.get("sessions", [])
    if not sessions:
        errors.append("No sessions found")
        return report

    type_counts = Counter(s["session_type"] for s in sessions)
    report["stats"]["session_types"] = dict(type_counts)
    report["stats"]["total_sessions"] = len(sessions)

    if type_counts.get("encoding", 0) == 0:
        errors.append("No encoding sessions")
    n_pert = sum(v for k, v in type_counts.items() if k.startswith("perturbation"))
    is_split = "perturbation_p1" in type_counts or "perturbation_p2" in type_counts
    if n_pert == 0:
        errors.append("No perturbation session")
    elif is_split and n_pert != 2:
        errors.append(f"Split episode should have exactly p1+p2 perturbation sessions, got {n_pert}")
    elif not is_split and n_pert > 1:
        errors.append(f"Multiple perturbation sessions: {n_pert}")

    perturbation_idx = None
    for i, s in enumerate(sessions):
        if s["session_type"].startswith("perturbation"):
            perturbation_idx = i
            break

    if perturbation_idx is not None:
        encoding_indices = [i for i, s in enumerate(sessions) if s["session_type"] == "encoding"]
        if encoding_indices and max(encoding_indices) >= perturbation_idx:
            errors.append("Encoding session(s) appear AFTER perturbation")

    filler_plan = spec.get("filler_plan", {})
    pre_plan = filler_plan.get("pre_perturbation", {})

    expected_pre_fillers = {
        "filler_weakly_related": pre_plan.get("weakly_related_background", 0),
        "filler_near_miss": pre_plan.get("near_miss", 0),
        "filler_confusable": pre_plan.get("confusable", 0),
        "filler_decoy_nonupdate": pre_plan.get("decoy_nonupdate", 0),
    }

    if perturbation_idx is not None:
        pre_sessions = sessions[:perturbation_idx]
        post_sessions = sessions[perturbation_idx + 1:]
    else:
        pre_sessions = sessions
        post_sessions = []

    actual_pre_fillers = Counter()
    for s in pre_sessions:
        if "filler" in s["session_type"]:
            actual_pre_fillers[s["session_type"]] += 1

    for ftype, expected_n in expected_pre_fillers.items():
        actual_n = actual_pre_fillers.get(ftype, 0)
        if actual_n != expected_n:
            warnings.append(
                f"Pre-perturbation {ftype}: expected {expected_n}, got {actual_n}"
            )

    report["stats"]["pre_filler_counts"] = dict(actual_pre_fillers)
    report["stats"]["post_filler_count"] = len([
        s for s in post_sessions if "filler" in s.get("session_type", "")
    ])

    turn_limits = {
        "filler_weakly_related": (2, 4),
        "filler_near_miss": (3, 5),
        "filler_confusable": (3, 5),
        "filler_decoy_nonupdate": (2, 4),
    }

    turn_stats = defaultdict(list)
    for s in sessions:
        stype = s["session_type"]
        if stype in turn_limits:
            user_turns = sum(1 for m in s.get("dialogue", []) if m.get("role") == "user")
            turn_stats[stype].append(user_turns)
            lo, hi = turn_limits[stype]
            if user_turns < lo or user_turns > hi:
                warnings.append(
                    f"{stype} (idx={s.get('metadata',{}).get('filler_idx','?')}): "
                    f"{user_turns} user turns, expected {lo}-{hi}"
                )

    report["stats"]["turn_counts"] = {k: v for k, v in turn_stats.items()}

    initial_value = spec.get("initial_value", "")
    new_value = spec.get("new_value", "")
    canonical_initial = spec.get("canonical_initial", initial_value)
    canonical_new = spec.get("canonical_new", new_value)
    distractors = spec.get("distractor_values", [])

    mention_counts = {
        "initial_value": {"total": 0, "by_type": defaultdict(int), "canonical": canonical_initial},
        "new_value": {"total": 0, "by_type": defaultdict(int), "canonical": canonical_new},
    }
    for d in distractors:
        mention_counts[f"distractor_{d}"] = {"total": 0, "by_type": defaultdict(int)}

    for s in sessions:
        text = get_all_text(s)
        stype = s["session_type"]

        for val_name, val in [("initial_value", canonical_initial), ("new_value", canonical_new)]:
            c = count_mentions(text, val)
            mention_counts[val_name]["total"] += c
            mention_counts[val_name]["by_type"][stype] += c

        for d in distractors:
            key = f"distractor_{d}"
            c = count_mentions(text, d)
            mention_counts[key]["total"] += c
            mention_counts[key]["by_type"][stype] += c

    for key in mention_counts:
        mention_counts[key]["by_type"] = dict(mention_counts[key]["by_type"])

    report["stats"]["mention_counts"] = mention_counts

    new_in_fillers = sum(
        v for k, v in mention_counts["new_value"]["by_type"].items()
        if "filler" in k
    )
    new_in_perturbation = mention_counts["new_value"]["by_type"].get("perturbation", 0)
    if new_in_fillers > 0 and new_in_perturbation > 0:
        ratio = new_in_fillers / max(new_in_perturbation, 1)
        if ratio > 3:
            warnings.append(
                f"HIGH_CONFUSABILITY: new_value appears {new_in_fillers}x in fillers "
                f"vs {new_in_perturbation}x in perturbation (ratio={ratio:.1f})"
            )
            report["stats"]["high_confusability"] = True
        else:
            report["stats"]["high_confusability"] = False

    gold = spec.get("gold", {})
    expected_behavior = episode.get("expected_behavior", "")

    canonical_init = spec.get("canonical_initial", initial_value)

    if expected_behavior == "should_preserve":
        if gold.get("has_changed", False):
            errors.append("expected_behavior=should_preserve but gold.has_changed=True")
        gcv = str(gold.get("current_value", "")).strip().lower(); cin = str(canonical_init).strip().lower()
        if gcv != cin and not (cin and (cin in gcv or gcv in cin)):
            errors.append(
                f"should_preserve but gold.current_value={gold.get('current_value')} "
                f"!= canonical_initial={canonical_init}"
            )
    elif expected_behavior == "should_update":
        if gold.get("current_value") == canonical_init and gold.get("has_changed", False):
            errors.append("should_update + has_changed but current_value still equals initial")

    probes = episode.get("probes", [])
    if not probes:
        errors.append("No probes found")
    else:
        probe_types = [p["probe_type"] for p in probes]
        if "current_value" not in probe_types:
            errors.append("Missing current_value probe")
        report["stats"]["probe_types"] = probe_types

    for i, s in enumerate(sessions):
        if not s.get("dialogue"):
            errors.append(f"Session {i} ({s['session_type']}) has empty dialogue")
        elif len(s["dialogue"]) < 2:
            warnings.append(f"Session {i} ({s['session_type']}) has only {len(s['dialogue'])} messages")

    return report


def first_user_msg(session: Dict) -> str:
    for m in session.get("dialogue", []):
        if m.get("role") == "user":
            return m.get("content", "")
    return ""


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def report_distribution_and_mentions(episodes: List[Dict], specs_by_id: Dict):
    print("=" * 80)
    print("CHECK 1-2: SESSION DISTRIBUTION & MENTION COUNTS")
    print("=" * 80)

    print(f"\n{'EID':<12} {'Para':<14} {'Cond':<22} {'Enc':>4} {'NM':>4} "
          f"{'Conf':>4} {'Dec':>4} {'WR':>4} {'Pert':>4} {'Post':>4} {'Tot':>4}")
    print("-" * 90)

    for ep in episodes:
        eid = ep["episode_id"]
        sessions = ep["sessions"]
        tc = Counter(s["session_type"] for s in sessions)

        pert_idx = next((i for i, s in enumerate(sessions) if s["session_type"] == "perturbation"), len(sessions))
        post_fillers = sum(1 for s in sessions[pert_idx + 1:] if "filler" in s.get("session_type", ""))

        print(f"{eid:<12} {ep['paradigm']:<14} {ep['condition']:<22} "
              f"{tc.get('encoding', 0):>4} {tc.get('filler_near_miss', 0):>4} "
              f"{tc.get('filler_confusable', 0):>4} {tc.get('filler_decoy_nonupdate', 0):>4} "
              f"{tc.get('filler_weakly_related', 0):>4} {tc.get('perturbation', 0):>4} "
              f"{post_fillers:>4} {len(sessions):>4}")

    print(f"\n\n{'EID':<12} {'init_val':>10} {'new_val':>10} "
          f"{'nv_enc':>8} {'nv_pert':>8} {'nv_fill':>8} {'nv_ratio':>8}  distractors")
    print("-" * 100)

    for ep in episodes:
        eid = ep["episode_id"]
        spec = specs_by_id.get(eid, ep.get("latent_spec", {}))
        ci = spec.get("canonical_initial", "")
        cn = spec.get("canonical_new", "")
        distractors = spec.get("distractor_values", [])

        init_total = 0
        new_total = 0
        new_by_type = defaultdict(int)
        dist_counts = {d: 0 for d in distractors}

        for s in ep["sessions"]:
            text = get_all_text(s)
            stype = s["session_type"]
            init_total += count_mentions(text, ci)
            c = count_mentions(text, cn)
            new_total += c
            new_by_type[stype] += c
            for d in distractors:
                dist_counts[d] += count_mentions(text, d)

        nv_enc = new_by_type.get("encoding", 0)
        nv_pert = new_by_type.get("perturbation", 0)
        nv_fill = sum(v for k, v in new_by_type.items() if "filler" in k)
        ratio = f"{nv_fill / max(nv_pert, 1):.1f}x" if nv_pert > 0 else "n/a"

        dist_str = "  ".join(f"{d}={c}" for d, c in dist_counts.items())
        print(f"{eid:<12} {init_total:>10} {new_total:>10} "
              f"{nv_enc:>8} {nv_pert:>8} {nv_fill:>8} {ratio:>8}  {dist_str}")


_UPDATE_PHRASES = [
    r"switch(?:ed|ing)?\s+to\b",
    r"chang(?:ed|ing)\s+to\b",
    r"updat(?:ed|ing)\s+to\b",
    r"mov(?:ed|ing)\s+to\b",
    r"migrat(?:ed|ing)\s+to\b",
    r"now\s+(?:us(?:es?|ing)|on|at|running)\b",
    r"adopt(?:ed|ing)\b",
    r"replac(?:ed|ing)\b",
    r"transitioned?\s+to\b",
    r"went\s+(?:with|to)\b",
    r"took\s+over\b",
]

_NEGATION_CONTEXT = [
    "decided not", "chose not", "didn't", "did not", "won't", "will not",
    "staying with", "keeping", "sticking with", "rolled back", "reverted",
    "but ultimately", "considered but", "ended up keeping", "remains",
    "still using", "still on", "no change", "unchanged",
]


def report_update_phrases(episodes: List[Dict], specs_by_id: Dict):
    print("\n\n" + "=" * 80)
    print("CHECK 4: UPDATE-LIKE PHRASE DETECTOR (preserve cases)")
    print("=" * 80)

    total_flags = 0
    total_preserve = 0

    for ep in episodes:
        eid = ep["episode_id"]
        if ep.get("expected_behavior") != "should_preserve":
            continue
        total_preserve += 1

        spec = specs_by_id.get(eid, {})
        cn = spec.get("canonical_new", "")

        flags = []
        for si, s in enumerate(ep["sessions"]):
            stype = s["session_type"]
            for mi, msg in enumerate(s.get("dialogue", [])):
                content = msg.get("content", "")
                content_lower = content.lower()

                for pat in _UPDATE_PHRASES:
                    for m in re.finditer(pat, content_lower):
                        after = content_lower[m.start():m.start() + 120]
                        has_new_val = cn and cn.lower() in after

                        window_start = max(0, m.start() - 100)
                        window = content_lower[window_start:m.start() + 120]
                        has_negation = any(neg in window for neg in _NEGATION_CONTEXT)

                        if has_new_val and not has_negation:
                            flags.append({
                                "session_idx": si,
                                "session_type": stype,
                                "role": msg.get("role", "?"),
                                "phrase": m.group(),
                                "context": content[max(0, m.start()-30):m.start()+80].strip(),
                                "new_value": cn,
                            })

        if flags:
            total_flags += len(flags)
            print(f"\n  {eid}: {len(flags)} leaked update phrases")
            for f in flags:
                print(f"    [{f['session_type']}#{f['session_idx']}] {f['role']}: "
                      f"\"{f['phrase']}\" → \"{f['context'][:60]}...\"")
        else:
            print(f"  {eid}: OK")

    print(f"\n  Preserve episodes: {total_preserve}, Total flags: {total_flags}")
    if total_flags == 0:
        print("  No leaked update phrases in preserve episodes.")


def report_duplicates(episodes: List[Dict]):
    print("\n\n" + "=" * 80)
    print("CHECK 3: DUPLICATE PHRASE / REPEATED OPENING DETECTOR")
    print("=" * 80)

    SIMILARITY_THRESHOLD = 0.65
    total_flags = 0

    for ep in episodes:
        eid = ep["episode_id"]
        flags = []

        by_type = defaultdict(list)
        for s in ep["sessions"]:
            if "filler" in s.get("session_type", ""):
                by_type[s["session_type"]].append(s)

        for stype, sessions in by_type.items():
            openings = []
            for s in sessions:
                msg = first_user_msg(s)
                openings.append((s.get("metadata", {}).get("filler_idx", "?"), msg))

            for i in range(len(openings)):
                for j in range(i + 1, len(openings)):
                    idx_a, msg_a = openings[i]
                    idx_b, msg_b = openings[j]
                    if not msg_a or not msg_b:
                        continue
                    sim = similarity(msg_a[:120], msg_b[:120])
                    if sim >= SIMILARITY_THRESHOLD:
                        flags.append({
                            "type": stype.replace("filler_", ""),
                            "idx_pair": (idx_a, idx_b),
                            "similarity": sim,
                            "opening_a": msg_a[:80],
                            "opening_b": msg_b[:80],
                        })

        if flags:
            total_flags += len(flags)
            print(f"\n  {eid}: {len(flags)} similar pairs found")
            for f in flags:
                print(f"    {f['type']} [{f['idx_pair'][0]}↔{f['idx_pair'][1]}] "
                      f"sim={f['similarity']:.2f}")
                print(f"      A: {f['opening_a']}...")
                print(f"      B: {f['opening_b']}...")
        else:
            print(f"\n  {eid}: OK (no similar openings)")

    print(f"\n  Total flags: {total_flags}")
    if total_flags == 0:
        print("  All filler openings are sufficiently diverse.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episodes", default=str(P.EPISODES56))
    ap.add_argument("--specs", default=str(P.SPECS56))
    ap.add_argument("--output", default=None, help="write the per-episode JSON report here")
    ap.add_argument("--report", action="store_true", help="also print the suite-level reports")
    ap.add_argument("--quiet", action="store_true", help="only print the totals")
    args = ap.parse_args()

    episodes = [json.loads(l) for l in open(args.episodes) if l.strip()]
    specs_by_id = {s["episode_id"]: s for s in json.loads(Path(args.specs).read_text())["specs"]}

    all_reports, total_errors, total_warnings = [], 0, 0
    for ep in episodes:
        spec = specs_by_id.get(ep["episode_id"])
        if not spec:
            print(f"  {ep['episode_id']}: SKIP (no matching spec)"); continue
        rep = validate_episode(ep, spec); all_reports.append(rep)
        total_errors += len(rep["errors"]); total_warnings += len(rep["warnings"])
        if not args.quiet:
            status = "PASS" if not rep["errors"] else "FAIL"
            print(f"  {ep['episode_id']:<12} {status}" + (f" ({len(rep['warnings'])} warnings)" if rep["warnings"] else ""))
            for e in rep["errors"]: print(f"    ERROR: {e}")
    print("=" * 70)
    print(f"Total: {len(all_reports)} episodes, {total_errors} errors, {total_warnings} warnings")
    if args.output:
        Path(args.output).write_text(json.dumps(all_reports, indent=2, ensure_ascii=False)); print(f"report -> {args.output}")
    if args.report:
        report_distribution_and_mentions(episodes, specs_by_id)
        report_duplicates(episodes)
        report_update_phrases(episodes, specs_by_id)


if __name__ == "__main__":
    main()
